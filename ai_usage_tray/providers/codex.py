import json
import sqlite3
import urllib.request
from datetime import datetime, timezone, timedelta

from ai_usage_tray.config import (
    CODEX_AUTH_JSON,
    CODEX_STATE_DB,
    CODEX_USAGE_API_URL,
)
from ai_usage_tray.providers.base import BaseProvider, ProviderUsage, UsageWindow


class CodexProvider(BaseProvider):
    id = "codex"
    name = "Codex"
    default_icon_color = (0.35, 0.58, 1.0)

    def is_configured(self) -> bool:
        return CODEX_AUTH_JSON.exists()

    def dashboard_url(self) -> str:
        return "https://chatgpt.com/codex/settings/usage"

    def settings_schema(self) -> list[dict]:
        return []

    def fetch_usage(self) -> ProviderUsage:
        local = self._read_local_db()
        usage = ProviderUsage(
            provider_id=self.id,
            provider_name=self.name,
            total_tokens=local["total_tokens"],
            weekly_tokens=local["weekly_tokens"],
            session_count=local["thread_count"],
            sessions=local["sessions"],
        )

        api_data, api_error = self._fetch_api()
        if api_error:
            usage.error = api_error
            return usage

        rate_limit = api_data.get("rate_limit", {})
        usage.plan_type = api_data.get("plan_type", "unknown")

        primary = rate_limit.get("primary_window", {})
        used_pct = max(0.0, min(100.0, primary.get("used_percent", 0)))
        rem_pct = max(0.0, 100.0 - used_pct)
        reset_at = primary.get("reset_at", 0)
        usage.windows.append(
            UsageWindow(
                label="5-hour rolling",
                used_percent=used_pct,
                remaining_percent=rem_pct,
                reset_at=reset_at,
                limit_reached=used_pct >= 100,
            )
        )

        secondary = rate_limit.get("secondary_window", {})
        sec_used = max(0.0, min(100.0, secondary.get("used_percent", 0)))
        sec_rem = max(0.0, 100.0 - sec_used)
        sec_reset = secondary.get("reset_at", 0)
        usage.windows.append(
            UsageWindow(
                label="Weekly (7d rolling)",
                used_percent=sec_used,
                remaining_percent=sec_rem,
                reset_at=sec_reset,
                limit_reached=sec_used >= 100,
            )
        )

        usage.last_refreshed = datetime.now(timezone.utc).strftime("%H:%M:%S")
        return usage

    def _fetch_api(self) -> tuple[dict | None, str | None]:
        if not CODEX_AUTH_JSON.exists():
            return None, "auth.json not found"

        try:
            with open(CODEX_AUTH_JSON) as f:
                auth = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            return None, f"auth.json read error: {e}"

        token = auth.get("tokens", {}).get("access_token")
        if not token:
            return None, "no access_token in auth.json"

        req = urllib.request.Request(
            CODEX_USAGE_API_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "CodexCLI/0.138.0",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                return data, None
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:200]
            return None, f"API HTTP {e.code}: {body}"
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            return None, f"API error: {e}"

    def _read_local_db(self) -> dict:
        result = {
            "total_tokens": 0,
            "weekly_tokens": 0,
            "thread_count": 0,
            "sessions": [],
        }

        if not CODEX_STATE_DB.exists():
            return result

        try:
            conn = sqlite3.connect(str(CODEX_STATE_DB))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT created_at, updated_at, tokens_used, model, title
                FROM threads ORDER BY created_at DESC
                """
            ).fetchall()
            conn.close()
        except sqlite3.Error:
            return result

        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        total_tokens = 0
        weekly_tokens = 0
        sessions = []

        for r in rows:
            created_ts = r["created_at"]
            tokens = r["tokens_used"] or 0
            total_tokens += tokens
            created_dt = datetime.fromtimestamp(created_ts, tz=timezone.utc)

            if created_dt >= week_ago:
                weekly_tokens += tokens

            sessions.append({
                "title": (r["title"] or "Untitled")[:50],
                "tokens": tokens,
                "date": created_dt.strftime("%Y-%m-%d %H:%M"),
                "model": r["model"] or "unknown",
                "duration_m": round((r["updated_at"] - created_ts) / 60, 1),
            })

        return {
            "total_tokens": total_tokens,
            "weekly_tokens": weekly_tokens,
            "thread_count": len(rows),
            "sessions": sessions,
        }
