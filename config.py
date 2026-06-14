import os
from pathlib import Path

CODEX_HOME = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
STATE_DB = CODEX_HOME / "state_5.sqlite"
AUTH_JSON = CODEX_HOME / "auth.json"

USAGE_LIMIT_HOURS = 5.0
USAGE_API_URL = "https://chatgpt.com/backend-api/codex/usage"
REFRESH_INTERVAL_SECONDS = 60
ICON_SIZE = 22

COLORS = {
    "high": (0.22, 0.80, 0.22),
    "medium": (0.90, 0.75, 0.05),
    "low": (0.90, 0.20, 0.15),
}
HIGH_THRESHOLD = 0.50
MEDIUM_THRESHOLD = 0.25
