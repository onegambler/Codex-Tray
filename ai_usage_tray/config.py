import os
from pathlib import Path

APP_NAME = "AI Usage Tray"
APP_SLUG = "ai-usage-tray"

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / APP_SLUG
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", "~/.cache")).expanduser() / APP_SLUG

CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_FILE = CACHE_DIR / "usage-cache.json"
LOG_FILE = CACHE_DIR / f"{APP_SLUG}.log"

CODEX_HOME = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
CODEX_STATE_DB = CODEX_HOME / "state_5.sqlite"
CODEX_AUTH_JSON = CODEX_HOME / "auth.json"
CODEX_USAGE_API_URL = "https://chatgpt.com/backend-api/codex/usage"

OPENCODE_DATA_DIR = Path.home() / ".local/share/opencode"
OPENCODE_AUTH_JSON = OPENCODE_DATA_DIR / "auth.json"
OPENCODE_DB = OPENCODE_DATA_DIR / "opencode.db"

REFRESH_INTERVAL_SECONDS = 60
ICON_SIZE = 22

HIGH_THRESHOLD = 0.50
MEDIUM_THRESHOLD = 0.25

PROVIDER_COLORS = {
    "codex": (0.35, 0.58, 1.0),
    "opencode-go": (1.0, 0.48, 0.12),
}

THRESHOLD_COLORS = {
    "high": (0.22, 0.80, 0.22),
    "medium": (0.90, 0.75, 0.05),
    "low": (0.90, 0.20, 0.15),
}

OPENCODE_GO_LIMITS = {
    "5h": 12.0,
    "weekly": 30.0,
    "monthly": 60.0,
}
