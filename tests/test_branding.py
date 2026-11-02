from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from snapforge.settings import SettingsStore, Preferences


class BrandingTests(unittest.TestCase):
    def test_legacy_settings_migrate_without_losing_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = SettingsStore(root / "SnapForgePro" / "settings.json")
            old.save(Preferences(capture_key="Ctrl+Shift+F8", quality=71))
            with patch("snapforge.settings.data_dir", return_value=root / "BlexShot"):
                new = SettingsStore()
                self.assertEqual(new.value.capture_key, "Ctrl+Shift+F8")
                self.assertEqual(new.value.quality, 71)
                self.assertTrue(new.path.exists())
                self.assertTrue(old.path.exists())

    def test_logo_and_windows_icon_use_supplied_asset(self):
        root = Path(__file__).resolve().parent.parent / "resources"
        with Image.open(root / "brand-logo.png") as source, Image.open(root / "app.png") as app:
            self.assertEqual(app.mode, "RGBA")
            self.assertEqual(app.width, app.height)
            self.assertEqual(app.getpixel((0,0))[3], 0)
            self.assertEqual(app.getchannel("A").getextrema()[1], source.convert("RGBA").getchannel("A").getextrema()[1])
        with Image.open(root / "app.ico") as icon:
            self.assertTrue({(16,16), (32,32), (48,48), (256,256)} <= icon.ico.sizes())
