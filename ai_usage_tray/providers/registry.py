from ai_usage_tray.providers.base import BaseProvider
from ai_usage_tray.providers.codex import CodexProvider
from ai_usage_tray.providers.opencode_go import OpenCodeGoProvider


PROVIDER_CLASSES: dict[str, type[BaseProvider]] = {
    "codex": CodexProvider,
    "opencode-go": OpenCodeGoProvider,
}


def list_provider_types() -> list[dict]:
    return [
        {"id": cls.id, "name": cls.name, "schema": cls().settings_schema()}
        for cls in PROVIDER_CLASSES.values()
    ]


def instantiate_provider(type_id: str, config: dict | None = None) -> BaseProvider:
    if type_id not in PROVIDER_CLASSES:
        raise ValueError(f"Unknown provider type: {type_id}")
    return PROVIDER_CLASSES[type_id](config or {})
