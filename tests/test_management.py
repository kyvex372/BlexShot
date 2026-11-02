import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from snapforge.app import Controller
from snapforge.imaging import from_array, save_image
from snapforge.management import SettingsDialog
from snapforge.settings import Preferences, SettingsStore

APP = QApplication.instance() or QApplication([])


class ManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        with patch.object(QSystemTrayIcon, "show"):
            self.controller = Controller(APP, SettingsStore(Path(self.temp.name) / "prefs.json"), enable_hotkeys=False)

    def tearDown(self):
        controller = self.controller
        controller.hotkeys.clear()
        APP.removeNativeEventFilter(controller.hotkeys)
        controller.window.canvas.shutdown()
        if controller.management:
            controller.management.hide(); controller.management.deleteLater()
        controller.window.force_close = True; controller.window.close(); controller.window.deleteLater()
        controller.tray.hide(); controller.deleteLater(); APP.processEvents()
        self.temp.cleanup()

    def test_left_click_captures_right_click_preserves_menu(self):
        with patch.object(self.controller, "capture") as capture:
            self.controller.tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
            capture.assert_called_once_with("region")
            self.controller.tray_activated(QSystemTrayIcon.ActivationReason.Context)
            self.assertEqual(capture.call_count, 1)
        self.assertIs(self.controller.tray.contextMenu(), self.controller.menu)
        titles = [action.text() for action in self.controller.menu.actions()]
        self.assertIn("Yönetim ve ayarlar", titles)
        self.assertIn("Çıkış", titles)

    def test_modeless_management_hides_for_capture_and_restores_on_cancel(self):
        self.controller.settings(); APP.processEvents()
        dialog = self.controller.management
        self.assertFalse(dialog.isModal())
        self.assertIsNone(APP.activeModalWidget())
        with patch("snapforge.app.QTimer.singleShot"):
            self.controller.capture("region")
        self.assertTrue(self.controller.capturing)
        self.assertFalse(dialog.isVisible())
        self.controller.cancel_capture()
        self.assertTrue(dialog.isVisible())

    def test_quality_save_and_persistent_shortcut(self):
        self.controller.settings()
        dialog = self.controller.management
        dialog.format.setCurrentText("JPG"); dialog.quality.setValue(73)
        dialog.keys[0].setKeySequence(QKeySequence("Ctrl+Shift+F8"))
        with patch.object(self.controller.hotkeys, "configure") as configure:
            self.controller.apply_settings()
            self.assertEqual(configure.call_args.args[0][0], "Ctrl+Shift+F8")
        saved = SettingsStore(self.controller.store.path).value
        self.assertEqual((saved.quality, saved.image_format, saved.capture_key), (73, "JPG", "Ctrl+Shift+F8"))
        self.assertFalse(dialog.save_button.isEnabled())
        self.assertTrue(dialog.isVisible())

    def test_conflicting_shortcut_does_not_save(self):
        self.controller.settings()
        dialog = self.controller.management
        dialog.keys[0].setKeySequence(QKeySequence("Ctrl+Shift+F8"))
        with patch.object(self.controller.hotkeys, "configure", side_effect=OSError("Kısayol kullanımda")):
            self.controller.apply_settings()
        self.assertEqual(self.controller.store.value.capture_key, "Print")
        self.assertFalse(self.controller.store.path.exists())
        self.assertIn("kullanımda", dialog.error.text())

    def test_lossless_formats_do_not_offer_lossy_slider(self):
        dialog = SettingsDialog(Preferences())
        self.assertFalse(dialog.quality.isEnabled())
        dialog.format.setCurrentText("JPG"); self.assertTrue(dialog.quality.isEnabled())
        dialog.format.setCurrentText("WEBP"); self.assertFalse(dialog.quality.isEnabled())
        dialog.lossless.setChecked(False); self.assertTrue(dialog.quality.isEnabled())
        dialog.deleteLater()

    def test_format_quality_changes_encoded_file_without_resizing(self):
        source = np.random.default_rng(9).integers(0, 256, (128, 192, 4), dtype=np.uint8)
        source[:, :, 3] = 255
        image = from_array(source)
        for fmt, ext in [("JPG", "jpg"), ("WEBP", "webp")]:
            low = Path(self.temp.name) / f"low.{ext}"
            high = Path(self.temp.name) / f"high.{ext}"
            save_image(image, low, fmt, quality=15, webp_lossless=False)
            save_image(image, high, fmt, quality=95, webp_lossless=False)
            self.assertLess(low.stat().st_size, high.stat().st_size)
            with Image.open(high) as result:
                self.assertEqual(result.size, (192, 128))
        png = Path(self.temp.name) / "lossless.png"
        save_image(image, png, quality=1)
        with Image.open(png) as result: np.testing.assert_array_equal(np.asarray(result.convert("RGBA")), source)
