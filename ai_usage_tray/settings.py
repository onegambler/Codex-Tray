import json
import os
from pathlib import Path

from ai_usage_tray.config import CONFIG_DIR, CONFIG_FILE, CODEX_AUTH_JSON


class Settings:
    def __init__(self):
        self._data: dict = {"providers": []}
        self._load()

    def _load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {"providers": []}
        else:
            self._data = {"providers": []}
            if CODEX_AUTH_JSON.exists():
                self._data["providers"].append({"type": "codex"})
            self._save()

    def _save(self):
        CONFIG_DIR.mkdir(parents=True, mode=0o700, exist_ok=True)
        tmp = CONFIG_FILE.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(self._data, f, indent=2)
            f.write("\n")
        os.chmod(tmp, 0o600)
        tmp.replace(CONFIG_FILE)

    @property
    def providers(self) -> list[dict]:
        return list(self._data.get("providers", []))

    def add_provider(self, type_id: str, config: dict):
        self._data["providers"].append({"type": type_id, **config})
        self._save()

    def remove_provider(self, index: int):
        providers = self._data.get("providers", [])
        if 0 <= index < len(providers):
            providers.pop(index)
            self._save()

    def update_provider(self, index: int, config: dict):
        providers = self._data.get("providers", [])
        if 0 <= index < len(providers):
            providers[index] = {**providers[index], **config}
            self._save()

    def provider_ids_from_env(self) -> set[str] | None:
        raw = os.environ.get("AI_USAGE_TRAY_PROVIDERS")
        if not raw:
            return None
        return {p.strip() for p in raw.split(",") if p.strip()}

    def active_provider_configs(self) -> list[dict]:
        env_filter = self.provider_ids_from_env()
        providers = self.providers
        if env_filter is not None:
            providers = [p for p in providers if p.get("type") in env_filter]
        return providers
