import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QEvent, QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QMouseEvent
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QDialog

from snapforge.document import Annotation, Document
from snapforge.settings import SettingsStore
from snapforge.window import MainWindow

APP = QApplication.instance() or QApplication([])


class EditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.window = MainWindow(SettingsStore(Path(self.temp.name) / "settings.json"))
        image = QImage(640, 400, QImage.Format.Format_ARGB32); image.fill(QColor("white"))
        self.window.show()
        self.window.set_document(image)
        APP.processEvents()
        self.canvas = self.window.canvas

    def tearDown(self):
        self.canvas.shutdown()
        self.window.force_close = True
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()
        self.temp.cleanup()

    def mouse(self, typ, point, button=Qt.MouseButton.LeftButton, buttons=Qt.MouseButton.LeftButton):
        local = QPointF(*point) * self.canvas.zoom + self.canvas.offset
        event = QMouseEvent(typ, local, local, button, buttons, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(self.canvas, event)

    def draw(self, tool, a=(40, 50), b=(240, 180)):
        self.window.choose_tool(tool)
        self.mouse(QEvent.Type.MouseButtonPress, a)
        self.mouse(QEvent.Type.MouseMove, b, Qt.MouseButton.NoButton)
        self.mouse(QEvent.Type.MouseButtonRelease, b, buttons=Qt.MouseButton.NoButton)

    def test_mouse_draw_select_move_resize_erase_undo(self):
        self.draw("blur")
        self.assertEqual(len(self.window.doc.layers), 1)
        self.window.choose_tool("select")
        self.mouse(QEvent.Type.MouseButtonPress, (100, 100))
        self.mouse(QEvent.Type.MouseMove, (120, 130), Qt.MouseButton.NoButton)
        self.mouse(QEvent.Type.MouseButtonRelease, (120, 130), buttons=Qt.MouseButton.NoButton)
        layer = self.window.doc.layers[0]
        self.assertEqual(layer.points, [(60, 80), (260, 210)])
        r = layer.bounds(); margin = 4 / self.canvas.zoom
        self.mouse(QEvent.Type.MouseButtonPress, (r.right() + margin, r.bottom() + margin))
        self.mouse(QEvent.Type.MouseMove, (350, 270), Qt.MouseButton.NoButton)
        self.mouse(QEvent.Type.MouseButtonRelease, (350, 270), buttons=Qt.MouseButton.NoButton)
        self.assertEqual(layer.bounds().bottomRight(), QPointF(350, 270))
        self.draw("eraser", (150, 150), (150, 150))
        self.assertEqual(len(self.window.doc.layers), 0)
        self.window.undo()
        self.assertEqual(len(self.window.doc.layers), 1)

    def test_live_vectors_and_all_drag_tools(self):
        for tool in ("pen", "arrow", "line", "rect", "ellipse", "highlight", "blur", "pixel", "redact"):
            with self.subTest(tool=tool):
                self.draw(tool)
                self.assertEqual(self.window.doc.layers[-1].tool, tool)
        self.assertEqual(len(self.window.doc.layers), 9)

    def test_layer_controls_and_properties(self):
        self.draw("rect")
        self.draw("arrow")
        self.window.choose_tool("select")
        layer = self.window.doc.layers[0]
        self.canvas.select(layer)
        self.window.set_color("#ff0000")
        self.window.stroke_spin.setValue(12)
        self.assertEqual((layer.color, layer.width), ("#ff0000", 12))
        self.window.reorder(1)
        self.assertEqual(self.window.doc.layers[-1].id, layer.id)
        self.window.layers.item(0).setCheckState(Qt.CheckState.Unchecked)
        self.assertFalse(layer.visible)
        self.window.undo()
        self.assertTrue(self.window.doc.layers[-1].visible)

    def test_clipboard_contains_rendered_redaction(self):
        self.draw("redact")
        self.window.copy_image()
        image = APP.clipboard().image()
        self.assertEqual(image.size(), self.window.doc.image.size())
        self.assertEqual(image.pixelColor(80, 80), QColor("black"))

    def test_zoom_anchor_stays_fixed(self):
        anchor = QPointF(280, 210)
        before = self.canvas.image_point(anchor)
        self.canvas.set_zoom(2, anchor)
        after = self.canvas.image_point(anchor)
        self.assertLess((before - after).manhattanLength(), .0001)

    def test_save_preview_and_filename_flow(self):
        self.draw("redact")
        target = Path(self.temp.name) / "çıktı.png"
        with patch("snapforge.window.ExportPreview.exec", return_value=QDialog.DialogCode.Accepted), \
             patch("snapforge.window.QFileDialog.getSaveFileName", return_value=(str(target), "PNG (*.png)")):
            self.assertTrue(self.window.save())
        self.assertFalse(self.window.doc.dirty)
        self.assertEqual(QImage(str(target)).pixelColor(80, 80), QColor("black"))
        self.assertEqual(SettingsStore(self.window.store.path).value.save_dir, str(target.parent))

    def test_save_failure_keeps_unsaved_document(self):
        target = str(Path(self.temp.name) / "failure.png")
        with patch("snapforge.window.ExportPreview.exec", return_value=QDialog.DialogCode.Accepted), \
             patch("snapforge.window.QFileDialog.getSaveFileName", return_value=(target, "PNG (*.png)")), \
             patch("snapforge.window.save_image", side_effect=OSError("disk full")), \
             patch.object(self.window, "show_error") as error:
            self.assertFalse(self.window.save())
            error.assert_called_once()
        self.assertTrue(self.window.doc.dirty)

    def test_preferences_do_not_mutate_selected_layer(self):
        self.draw("rect")
        self.window.choose_tool("select")
        layer = self.window.doc.layers[0]
        self.canvas.select(layer)
        self.window.store.value.stroke = 16
        self.window.apply_preferences()
        self.assertEqual(layer.width, 4)
        self.assertEqual(self.canvas.stroke, 16)

    def test_rapid_render_requests_latest_wins(self):
        image = self.window.doc.image
        spy = QSignalSpy(self.canvas.renderer.ready)
        for x in range(20):
            self.canvas.renderer.request(image, [Annotation("redact", [(x, 0), (x + 10, 100)])])
        for _ in range(100):
            QTest.qWait(20)
            if spy.count(): break
        self.assertGreater(spy.count(), 0)
        result = spy.at(spy.count() - 1)[0]
        self.assertEqual(result.pixelColor(20, 20), QColor("black"))
        self.assertEqual(result.pixelColor(1, 20), QColor("white"))


if __name__ == "__main__": unittest.main()
