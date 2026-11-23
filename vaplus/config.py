"""VA+ settings and the write-only Venice key, kept in ComfyUI/user/default/va_plus (outside workflows and comfy.settings.json)."""
import json
import os
from pathlib import Path

DEFAULTS = {"enabled": True, "model": "deepseek-v4-1-flash-1017-uncensored", "web_search": True, "show_cost": True}
FALLBACK_MODEL = "venice-uncensored-1-2"


def default_root() -> Path:
    import folder_paths

    return Path(folder_paths.get_user_directory()) / "default" / "va_plus"


def _write(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.config_path = self.root / "config.json"
        self.secrets_path = self.root / "secrets.json"

    def load(self) -> dict:
        saved = _read(self.config_path)
        return {k: saved[k] if isinstance(saved.get(k), type(v)) and saved[k] != "" else v for k, v in DEFAULTS.items()}

    def save(self, update: dict) -> dict:
        cfg = self.load()
        for k, v in (update or {}).items():
            if k in DEFAULTS and isinstance(v, type(DEFAULTS[k])) and v != "":
                cfg[k] = v
        _write(self.config_path, cfg)
        return cfg

    def set_key(self, key: str) -> None:
        key = (key or "").strip()
        if key:
            _write(self.secrets_path, {"venice_api_key": key})
        elif self.secrets_path.exists():
            self.secrets_path.unlink()

    def get_key(self):
        key = _read(self.secrets_path).get("venice_api_key")
        return key if isinstance(key, str) and key else (os.environ.get("VENICE_API_KEY") or None)

    def has_key(self) -> bool:
        return bool(self.get_key())
