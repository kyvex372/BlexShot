from dataclasses import asdict, dataclass, fields
import json
import logging
from pathlib import Path
import os
import re
import tempfile

from .platform import data_dir


@dataclass
class Preferences:
    theme: str = "light"
    ui_revision: int = 2
    capture_key: str = "Print"
    fullscreen_key: str = "Ctrl+Print"
    window_key: str = "Alt+Print"
    save_dir: str = str(Path.home() / "Pictures" / "BlexShot")
    image_format: str = "PNG"
    quality: int = 98
    webp_lossless: bool = True
    color: str = "#f59e0b"
    stroke: int = 4
    blur: int = 18
    startup: bool = False
    tray: bool = True
    notifications: bool = True
    animations: bool = True


class SettingsStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else data_dir() / "settings.json"
        self.value = Preferences()
        self.load_error = ""
        try:
            source_path = self.path
            if path is None and not source_path.exists():
                legacy = source_path.parent.parent / "SnapForgePro" / "settings.json"
                if legacy.exists(): source_path = legacy
            raw = json.loads(source_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Ayar dosyası bir JSON nesnesi olmalı.")
            for f in fields(Preferences):
                if f.name in raw and type(raw[f.name]) is type(getattr(self.value, f.name)):
                    setattr(self.value, f.name, raw[f.name])
            if raw.get("ui_revision", 0) < 2:
                self.value.theme = "light"
                self.value.ui_revision = 2
            if self.value.theme not in ("dark", "light"):
                self.value.theme = "light"
            if self.value.image_format not in ("PNG", "JPG", "WEBP"):
                self.value.image_format = "PNG"
            self.value.stroke = max(1, min(40, self.value.stroke))
            self.value.blur = max(1, min(80, self.value.blur))
            self.value.quality = max(1, min(100, self.value.quality))
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", self.value.color):
                self.value.color = "#f59e0b"
            if self.value.color.lower() == "#a78bfa":
                self.value.color = "#f59e0b"
            if source_path != self.path:
                self.save()
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError) as exc:
            self.load_error = str(exc)
            logging.warning("Settings load: %s", exc)

    def save(self, value=None):
        candidate = value or self.value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix="settings-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(asdict(candidate), stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
            self.value = candidate
        finally:
            if os.path.exists(name):
                os.unlink(name)
