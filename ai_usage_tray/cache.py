import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from ai_usage_tray.config import CACHE_DIR, CACHE_FILE
from ai_usage_tray.providers.base import ProviderUsage, UsageWindow


def _usage_from_dict(data: dict) -> ProviderUsage:
    windows = [UsageWindow(**w) for w in data.get("windows", [])]
    return ProviderUsage(
        provider_id=data.get("provider_id", ""),
        provider_name=data.get("provider_name", ""),
        windows=windows,
        error=data.get("error"),
        note=data.get("note"),
        last_refreshed=data.get("last_refreshed"),
        total_tokens=data.get("total_tokens", 0),
        weekly_tokens=data.get("weekly_tokens", 0),
        session_count=data.get("session_count", 0),
        sessions=data.get("sessions", []),
        plan_type=data.get("plan_type"),
    )


def load_cache() -> list[ProviderUsage]:
    if not CACHE_FILE.exists():
        return []
    try:
        with open(CACHE_FILE) as f:
            data = json.load(f)
        if isinstance(data, dict):
            return [_usage_from_dict(item) for item in data.get("providers", [])]
        if isinstance(data, list):
            return [_usage_from_dict(item) for item in data]
    except (json.JSONDecodeError, OSError, TypeError):
        pass
    return []


def save_cache(usages: list[ProviderUsage]):
    CACHE_DIR.mkdir(parents=True, mode=0o700, exist_ok=True)
    payload = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "providers": [asdict(u) for u in usages],
    }
    tmp = CACHE_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    tmp.replace(CACHE_FILE)
