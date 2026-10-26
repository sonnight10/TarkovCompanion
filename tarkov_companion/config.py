"""Configuration persistante (dossier utilisateur)."""
from __future__ import annotations

import json
import re
import os
import threading
from pathlib import Path

from . import APP_NAME

ACCENTS = ("amber", "blue", "green", "violet", "red")

DEFAULTS = {
    "logs_dir": "",
    "screenshots_dir": "",
    "language": "fr",
    "api_url": "https://api.tarkov.dev/graphql",
    "follow_player": True,
    "show_trail": True,
    "show_objectives": True,
    "show_extracts": True,
    "show_todo": True,
    "faction": "pmc",
    "map_style": "schema",
    "theme": "dark",
    "accent": "amber",
    "ui_lang": "fr",
    "reminder_seconds": 0,
    "cleanup_screenshots": False,
    "check_updates": True,
    "update_repo": "sonnight10/TarkovCompanion",
    "reminder_style": "toast",
    "reminder_by_map": {},
}


def data_dir() -> Path:
    """Dossier de données de l'application (%APPDATA% sous Windows)."""
    base = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    path = Path(os.environ.get("TARKOV_COMPANION_HOME") or Path(base) / APP_NAME)
    path.mkdir(parents=True, exist_ok=True)
    return path


class Config:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "config.json")
        self._lock = threading.Lock()
        self._values = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._values.update({k: v for k, v in raw.items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass

    def save(self) -> None:
        with self._lock:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._values, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)

    def get(self, key: str):
        return self._values.get(key, DEFAULTS.get(key))

    def update(self, changes: dict) -> None:
        for key, value in changes.items():
            if key not in DEFAULTS or type(value) is not type(DEFAULTS[key]):
                continue
            if key == "faction" and value not in ("pmc", "scav"):
                continue
            if key == "map_style" and value not in ("schema", "detail"):
                continue
            if key == "theme" and value not in ("dark", "light"):
                continue
            if key == "accent" and value not in ACCENTS:
                continue
            if key == "ui_lang" and value not in ("fr", "en"):
                continue
            if key == "reminder_seconds" and not (value == 0 or 5 <= value <= 600):
                continue
            if key == "update_repo" and value and not re.match(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$", value):
                continue
            if key == "reminder_style" and value not in ("toast", "beep", "both"):
                continue
            if key == "reminder_by_map":
                value = {str(k)[:40]: v for k, v in value.items() if type(v) is int and (v == 0 or 5 <= v <= 600)}
                if len(value) > 40:
                    continue
            self._values[key] = value
        self.save()

    def as_dict(self) -> dict:
        return dict(self._values)
