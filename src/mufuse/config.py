"""Small persistent user config (last-used headband) in the OS user-config directory."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from platformdirs import user_config_path


@dataclass
class UserConfig:
    last_device_name: str | None = None
    last_device_address: str | None = None


def config_path() -> Path:
    return user_config_path("mufuse", appauthor=False) / "config.json"


def load_config(path: Path | None = None) -> UserConfig:
    path = path or config_path()
    if not path.exists():
        return UserConfig()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return UserConfig(**{k: raw.get(k) for k in UserConfig.__dataclass_fields__})
    except (json.JSONDecodeError, TypeError):
        return UserConfig()


def save_config(config: UserConfig, path: Path | None = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
