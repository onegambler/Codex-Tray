import re
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

from ai_usage_tray.config import (
    OPENCODE_DB,
    OPENCODE_GO_LIMITS,
)
from ai_usage_tray.providers.base import BaseProvider, ProviderUsage, UsageWindow


class OpenCodeGoProvider(BaseProvider):
    id = "opencode-go"
    name = "OpenCode Go"
    default_icon_color = (1.0, 0.48, 0.12)

    DASHBOARD_URL_PREFIX = "https://opencode.ai/workspace/"
    DASHBOARD_URL_SUFFIX = "/go"
    USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"

    def is_configured(self) -> bool:
        return bool(self._workspace_id() and self._auth_cookie())

    def dashboard_url(self) -> str:
        wid = self._workspace_id()
        if wid:
            return f"{self.DASHBOARD_URL_PREFIX}{wid}{self.DASHBOARD_URL_SUFFIX}"
        return "https://opencode.ai/go"

    def settings_schema(self) -> list[dict]:
        return [
            {
                "key": "workspace_id",
                "label": "Workspace ID",
                "type": "text",
                "required": True,
                "help": "Open the OpenCode Go dashboard; the workspace ID is in the URL: /workspace/<id>/go",
            },
            {
                "key": "auth_cookie",
                "label": "Auth cookie",
                "type": "password",
                "required": True,
                "help": "Value of the 'auth' cookie from opencode.ai in your browser.",
            },
        ]

    def fetch_usage(self) -> ProviderUsage:
        usage = ProviderUsage(
            provider_id=self.id,
            provider_name=self.name,
        )

        if self.is_configured():
            try:
                scraped = self._scrape_dashboard()
                if scraped:
                    usage.windows = scraped
                    usage.last_refreshed = datetime.now(timezone.utc).strftime("%H:%M:%S")
                    return usage
            except Exception as e:
                # Fall back to local estimate if scraping fails.
                pass

        # Degraded local estimate.
        try:
            usage.windows = self._local_estimate()
            usage.note = "estimated from local sessions"
            usage.last_refreshed = datetime.now(timezone.utc).strftime("%H:%M:%S")
            return usage
        except Exception as e:
            usage.error = f"OpenCode Go usage unavailable: {e}"
            return usage

    def _workspace_id(self) -> str | None:
        return self.config.get("workspace_id", "").strip() or None

    def _auth_cookie(self) -> str | None:
        return self.config.get("auth_cookie", "").strip() or None

    def _scrape_dashboard(self) -> list[UsageWindow] | None:
        wid = self._workspace_id()
        cookie = self._auth_cookie()
        if not wid or not cookie:
            return None

        url = f"{self.DASHBOARD_URL_PREFIX}{urllib.parse.quote(wid)}{self.DASHBOARD_URL_SUFFIX}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.USER_AGENT,
                "Accept": "text/html",
                "Cookie": f"auth={cookie}",
            },
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        windows = self._parse_ssr_usage(html)
        if not windows:
            windows = self._parse_data_slot_usage(html)
        return windows

    def _parse_ssr_usage(self, html: str) -> list[UsageWindow]:
        """Parse SolidJS SSR hydration blobs for rolling/weekly/monthly usage."""
        windows = []
        now = int(datetime.now(timezone.utc).timestamp())

        number = r"-?\d+(?:\.\d+)?"
        for key, label in (
            ("rollingUsage", "5-hour rolling"),
            ("weeklyUsage", "Weekly"),
            ("monthlyUsage", "Monthly"),
        ):
            found = None
            pct_first = re.compile(
                rf"{key}:\$R\[\d+\]=\{{[^}}]*usagePercent:({number})[^}}]*resetInSec:({number})[^}}]*}}"
            )
            m = pct_first.search(html)
            if m:
                usage_pct = float(m.group(1))
                reset_sec = int(float(m.group(2)))
                found = UsageWindow(
                    label=label,
                    used_percent=max(0.0, min(100.0, usage_pct)),
                    remaining_percent=max(0.0, 100.0 - usage_pct),
                    reset_at=now + reset_sec,
                    limit_reached=usage_pct >= 100,
                )
            else:
                reset_first = re.compile(
                    rf"{key}:\$R\[\d+\]=\{{[^}}]*resetInSec:({number})[^}}]*usagePercent:({number})[^}}]*}}"
                )
                m = reset_first.search(html)
                if m:
                    reset_sec = int(float(m.group(1)))
                    usage_pct = float(m.group(2))
                    found = UsageWindow(
                        label=label,
                        used_percent=max(0.0, min(100.0, usage_pct)),
                        remaining_percent=max(0.0, 100.0 - usage_pct),
                        reset_at=now + reset_sec,
                        limit_reached=usage_pct >= 100,
                    )
            if found:
                windows.append(found)

        return windows

    def _parse_data_slot_usage(self, html: str) -> list[UsageWindow]:
        """Fallback: parse data-slot HTML markup."""
        windows = []
        now = int(datetime.now(timezone.utc).timestamp())
        chunks = html.split('data-slot="usage-item"')

        for chunk in chunks[1:]:
            label_match = re.search(r'data-slot="usage-label"[^>]*>([^<]+)', chunk)
            value_match = re.search(r'data-slot="usage-value"[^>]*>([^<]+)', chunk)
            reset_match = re.search(r'data-slot="reset-(?:time|now)"[^>]*>([^<]+)', chunk)
            if not label_match or not value_match:
                continue

            label_text = label_match.group(1).strip().lower()
            if "5h" in label_text or "5 hour" in label_text:
                label = "5-hour rolling"
            elif "week" in label_text:
                label = "Weekly"
            elif "month" in label_text:
                label = "Monthly"
            else:
                continue

            value_text = value_match.group(1).strip()
            try:
                used_pct = float(value_text.rstrip("%"))
            except ValueError:
                continue

            reset_sec = 0
            if reset_match:
                reset_sec = self._parse_human_duration(reset_match.group(1).strip())

            windows.append(
                UsageWindow(
                    label=label,
                    used_percent=max(0.0, min(100.0, used_pct)),
                    remaining_percent=max(0.0, 100.0 - used_pct),
                    reset_at=now + reset_sec if reset_sec else 0,
                    limit_reached=used_pct >= 100,
                )
            )

        return windows

    def _parse_human_duration(self, text: str) -> int:
        """Convert strings like '1 hour 56 minutes' or '6 days 2 hours' to seconds."""
        total = 0
        matches = re.findall(r"(\d+)\s*(day|days|hour|hours|minute|minutes|min|sec|second|seconds)", text)
        for value, unit in matches:
            n = int(value)
            if "day" in unit:
                total += n * 86400
            elif "hour" in unit:
                total += n * 3600
            elif "minute" in unit or unit == "min":
                total += n * 60
            elif "second" in unit:
                total += n
        return total

    def _local_estimate(self) -> list[UsageWindow]:
        """Estimate usage from local opencode.db session costs."""
        if not OPENCODE_DB.exists():
            raise RuntimeError("opencode.db not found")

        now = datetime.now(timezone.utc)
        five_hours_ago = now - timedelta(hours=5)
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        conn = sqlite3.connect(f"file:{OPENCODE_DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT cost, time_created, time_updated
            FROM session
            WHERE time_archived IS NULL
            """
        ).fetchall()
        conn.close()

        def ms_to_dt(ts):
            return datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)

        used_5h = 0.0
        used_week = 0.0
        used_month = 0.0

        for r in rows:
            cost = r["cost"] or 0.0
            created = ms_to_dt(r["time_created"])
            updated = ms_to_dt(r["time_updated"]) if r["time_updated"] else created

            if updated >= five_hours_ago:
                used_5h += cost
            if created >= week_start:
                used_week += cost
            if created >= month_start:
                used_month += cost

        windows = []
        for label, limit, used in (
            ("5-hour rolling", OPENCODE_GO_LIMITS["5h"], used_5h),
            ("Weekly", OPENCODE_GO_LIMITS["weekly"], used_week),
            ("Monthly", OPENCODE_GO_LIMITS["monthly"], used_month),
        ):
            pct = (used / limit * 100.0) if limit else 0.0
            pct = max(0.0, min(100.0, pct))
            windows.append(
                UsageWindow(
                    label=label,
                    used_percent=pct,
                    remaining_percent=max(0.0, 100.0 - pct),
                    reset_at=0,
                    limit_reached=pct >= 100,
                )
            )

        return windows
