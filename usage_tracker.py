import json
import sqlite3
import urllib.request
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field

from config import STATE_DB, AUTH_JSON, USAGE_LIMIT_HOURS, USAGE_API_URL


@dataclass
class UsageStats:
    total_tokens: int = 0
    weekly_tokens: int = 0
    remaining_hours: float = USAGE_LIMIT_HOURS
    used_percent: float = 0.0
    thread_count: int = 0
    sessions: list = field(default_factory=list)
    error: str | None = None
    plan_type: str | None = None
    primary_limit: bool = False
    secondary_limit: bool = False
    secondary_used: int = 0
    secondary_window_seconds: int = 604800
    reset_at: int = 0
    secondary_reset_at: int = 0
    last_refreshed: str | None = None


def fetch_api_usage() -> tuple[dict | None, str | None]:
    if not AUTH_JSON.exists():
        return None, "auth.json not found"

    try:
        with open(AUTH_JSON) as f:
            auth = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return None, f"auth.json read error: {e}"

    token = auth.get("tokens", {}).get("access_token")
    if not token:
        return None, "no access_token in auth.json"

    req = urllib.request.Request(
        USAGE_API_URL,
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


def read_local_db() -> dict:
    result = {
        "total_tokens": 0,
        "weekly_tokens": 0,
        "thread_count": 0,
        "sessions": [],
    }

    if not STATE_DB.exists():
        return result

    try:
        conn = sqlite3.connect(str(STATE_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.execute("""
            SELECT created_at, updated_at, tokens_used, model, title
            FROM threads ORDER BY created_at DESC
        """)
        rows = cur.fetchall()
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


def read_usage() -> UsageStats:
    stats = UsageStats()
    local = read_local_db()
    stats.total_tokens = local["total_tokens"]
    stats.weekly_tokens = local["weekly_tokens"]
    stats.thread_count = local["thread_count"]
    stats.sessions = local["sessions"]

    api_data, api_error = fetch_api_usage()

    if api_error:
        stats.error = api_error
        return stats

    rate_limit = api_data.get("rate_limit", {})
    stats.plan_type = api_data.get("plan_type", "unknown")

    primary = rate_limit.get("primary_window", {})
    used_pct = primary.get("used_percent", 0)
    stats.used_percent = max(0, min(used_pct, 100))
    stats.remaining_hours = USAGE_LIMIT_HOURS * (1 - stats.used_percent / 100)
    stats.reset_at = primary.get("reset_at", 0)
    stats.primary_limit = stats.used_percent >= 100

    stats.last_refreshed = datetime.now(timezone.utc).strftime("%H:%M:%S")

    secondary = rate_limit.get("secondary_window", {})
    stats.secondary_used = secondary.get("used_percent", 0)
    stats.secondary_window_seconds = secondary.get("limit_window_seconds", 604800)
    stats.secondary_reset_at = secondary.get("reset_at", 0)
    stats.secondary_limit = stats.secondary_used >= 100

    return stats
