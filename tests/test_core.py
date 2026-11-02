import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from snapforge.capture import CaptureSession, DesktopFrame
from snapforge.document import Annotation, Document
from snapforge.hotkeys import parse_hotkey
from snapforge.imaging import from_array, render, save_image, to_array
from snapforge.settings import Preferences, SettingsStore

APP = QApplication.instance() or QApplication([])


def fixture(width=240, height=160):
    rng = np.random.default_rng(42)
    a = rng.integers(0, 256, (height, width, 4), dtype=np.uint8)
    a[:, :, 3] = 255
    return from_array(a)


class RenderingTests(unittest.TestCase):
    def test_qimage_array_owns_memory(self):
        source = np.zeros((31, 27, 4), dtype=np.uint8)
        source[:, :, 3] = 255
        image = from_array(source)
        source[:] = 255
        self.assertEqual(image.pixelColor(3, 3), QColor(0, 0, 0, 255))
        self.assertEqual(to_array(image).shape, (31, 27, 4))

    def test_all_vector_tools_change_pixels(self):
        image = QImage(240, 160, QImage.Format.Format_ARGB32)
        image.fill(QColor("white"))
        for tool in ("pen", "line", "arrow", "rect", "ellipse", "highlight", "number", "text", "redact"):
            with self.subTest(tool=tool):
                annotation = Annotation(tool, [(40, 40), (150, 110)], color="#5030ab", text="Gizli bilgi", font_size=22)
                self.assertFalse(np.array_equal(to_array(render(image, [annotation])), to_array(image)))

    def test_blur_and_pixel_are_local_and_visible(self):
        image = fixture()
        original = to_array(image)
        for tool in ("blur", "pixel"):
            with self.subTest(tool=tool):
                result = to_array(render(image, [Annotation(tool, [(30, 40), (120, 100)], strength=12)]))
                self.assertTrue(np.array_equal(result[:40], original[:40]))
                self.assertTrue(np.array_equal(result[100:], original[100:]))
                self.assertLess(result[45:95, 35:115, :3].var(), original[45:95, 35:115, :3].var() * .1)
                self.assertTrue(np.array_equal(to_array(image), original))

    def test_reversed_outside_and_empty_privacy_rects(self):
        image = fixture()
        layers = [Annotation("blur", [(80, 80), (-40, -10)]), Annotation("pixel", [(1000, 1000), (1200, 1200)]),
                  Annotation("blur", [(5, 5), (5, 5)])]
        result = render(image, layers)
        self.assertEqual(result.size(), image.size())
        self.assertEqual(result.pixelColor(120, 120), image.pixelColor(120, 120))

    def test_redaction_is_opaque_despite_opacity_property(self):
        image = fixture()
        out = render(image, [Annotation("redact", [(10, 10), (100, 100)], opacity=.05)])
        self.assertEqual(out.pixelColor(50, 50), QColor("black"))

    def test_hidden_layers_and_order(self):
        image = fixture()
        box = Annotation("redact", [(10, 10), (90, 90)], visible=False)
        self.assertTrue(np.array_equal(to_array(render(image, [box])), to_array(image)))
        box.visible = True
        line = Annotation("line", [(10, 40), (90, 40)], color="#ff0000", width=10)
        self.assertEqual(render(image, [line, box]).pixelColor(50, 40), QColor("black"))
        self.assertEqual(render(image, [box, line]).pixelColor(50, 40), QColor("red"))

    def test_exports_and_unicode_paths(self):
        image = fixture(75, 47)
        with tempfile.TemporaryDirectory() as folder:
            for ext in ("png", "jpg", "webp"):
                path = Path(folder) / "Türkçe görüntü" / f"çıktı.{ext}"
                save_image(image, path)
                with Image.open(path) as loaded:
                    self.assertEqual(loaded.size, (75, 47))
                    if ext != "jpg":
                        np.testing.assert_array_equal(np.asarray(loaded.convert("RGBA")), to_array(image))

    def test_invalid_export_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "file.txt"
            path.write_text("keep")
            with self.assertRaises(ValueError): save_image(fixture(), path)
            self.assertEqual(path.read_text(), "keep")


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.doc = Document(fixture())

    def test_add_move_resize_delete_undo_redo(self):
        layer = Annotation("blur", [(10, 10), (80, 70)])
        self.doc.add(layer)
        before = deepcopy(self.doc.layers)
        layer.translate(20, -5)
        self.doc.commit(before)
        self.doc.undo()
        self.assertEqual(self.doc.layers[0].points, [(10, 10), (80, 70)])
        self.doc.redo()
        self.assertEqual(self.doc.layers[0].points, [(30, 5), (100, 65)])
        before = deepcopy(self.doc.layers)
        self.doc.layers[0].points[-1] = (200, 150)
        self.doc.commit(before)
        self.doc.remove(layer.id)
        self.assertEqual(len(self.doc.layers), 0)
        self.doc.undo()
        self.assertEqual(self.doc.layers[0].points[-1], (200, 150))

    def test_redo_branch_cleared_and_history_bounded(self):
        for _ in range(85): self.doc.add(Annotation("number", [(5, 5)]))
        self.assertEqual(len(self.doc.undo_states), 80)
        self.doc.undo()
        self.doc.add(Annotation("text", [(10, 10)], text="new"))
        self.assertEqual(self.doc.redo_states, [])

    def test_dirty_state_tracks_export_and_undo(self):
        self.assertTrue(self.doc.dirty)
        self.doc.mark_saved()
        self.assertFalse(self.doc.dirty)
        self.doc.add(Annotation("rect", [(4, 4), (50, 50)]))
        self.assertTrue(self.doc.dirty)
        self.doc.undo()
        self.assertFalse(self.doc.dirty)


class CaptureMathTests(unittest.TestCase):
    def test_negative_origin_crop(self):
        image = fixture(240, 160)
        frame = DesktopFrame(image, QRect(-120, -80, 240, 160), [])
        cropped = frame.crop(QRect(-100, -70, 60, 40))
        np.testing.assert_array_equal(to_array(cropped), to_array(image)[10:50, 20:80])

    def test_selection_cross_origin_resize_and_clamp(self):
        frame = DesktopFrame(fixture(500, 300), QRect(-200, -100, 500, 300), [])
        session = CaptureSession(frame)
        session.press(QPoint(-80, -60), 8)
        session.move(QPoint(80, 60))
        self.assertEqual(session.rect, QRect(QPoint(-80, -60), QPoint(80, 60)))
        session.mode = ""
        session.press(session.rect.bottomRight(), 8)
        session.move(QPoint(180, 120))
        self.assertEqual(session.rect.bottomRight(), QPoint(180, 120))
        session.mode = ""
        session.press(QPoint(40, 30), 8)
        session.move(QPoint(1000, 1000))
        self.assertTrue(frame.bounds.contains(session.rect))


class SettingsTests(unittest.TestCase):
    def test_atomic_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ayarlar.json"
            store = SettingsStore(path)
            prefs = Preferences(color="#abcdef", blur=29, capture_key="Ctrl+Shift+S")
            store.save(prefs)
            self.assertEqual(SettingsStore(path).value, prefs)
            self.assertEqual(list(Path(folder).glob("*.tmp")), [])

    def test_corrupt_and_wrong_types(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text("[oops", encoding="utf-8")
            self.assertTrue(SettingsStore(path).load_error)
            path.write_text('{"stroke": 900, "blur": -2, "tray": "yes", "theme": "unknown"}', encoding="utf-8")
            prefs = SettingsStore(path).value
            self.assertEqual((prefs.stroke, prefs.blur, prefs.tray, prefs.theme), (40, 1, True, "light"))

    def test_hotkey_parser(self):
        self.assertEqual(parse_hotkey("Print"), (0x4000, 0x2c))
        self.assertEqual(parse_hotkey("Ctrl+Shift+F12"), (0x4006, 0x7b))
        with self.assertRaises(ValueError): parse_hotkey("")
        self.assertEqual(parse_hotkey("A"), (0x4000, 0x41))
        self.assertEqual(parse_hotkey("PgUp"), (0x4000, 0x21))


if __name__ == "__main__":
    unittest.main()
