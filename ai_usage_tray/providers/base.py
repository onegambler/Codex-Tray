from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UsageWindow:
    label: str
    used_percent: float
    remaining_percent: float
    reset_at: int = 0
    limit_reached: bool = False


@dataclass
class ProviderUsage:
    provider_id: str
    provider_name: str
    windows: list[UsageWindow] = field(default_factory=list)
    error: Optional[str] = None
    note: Optional[str] = None
    last_refreshed: Optional[str] = None
    # Optional extras populated by some providers
    total_tokens: int = 0
    weekly_tokens: int = 0
    session_count: int = 0
    sessions: list[dict] = field(default_factory=list)
    plan_type: Optional[str] = None


class BaseProvider:
    id: str = ""
    name: str = ""
    default_icon_color: tuple = (0.5, 0.5, 0.5)

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def is_configured(self) -> bool:
        return True

    def fetch_usage(self) -> ProviderUsage:
        raise NotImplementedError

    def dashboard_url(self) -> str:
        return ""

    def settings_schema(self) -> list[dict]:
        """Fields shown in the Add Provider dialog.

        Each field is a dict: {key, label, type, required, secret?, help?}.
        Types: text, password.
        """
        return []
