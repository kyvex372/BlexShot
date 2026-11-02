import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import time
from unittest.mock import patch

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent, QMouseEvent, QPainter
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from snapforge.app import Controller
from snapforge.capture import DesktopFrame
from snapforge.document import Annotation
from snapforge.inline import InlineSession
from snapforge.settings import SettingsStore

APP = QApplication.instance() or QApplication([])


class InlineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SettingsStore(Path(self.temp.name) / "prefs.json")
        image = QImage(800, 600, QImage.Format.Format_ARGB32); image.fill(QColor("white"))
        self.frame = DesktopFrame(image, QRect(-200, -100, 800, 600),
                                  [{"left": -200, "top": -100, "width": 800, "height": 600}])
        self.session = InlineSession(self.frame, self.store)
        self.session.rect = QRect(-150, -50, 400, 250)
        self.session.finish()

    def tearDown(self):
        self.session.close(); self.session.deleteLater(); APP.processEvents()
        self.temp.cleanup()

    def wait_finished(self):
        until=time.monotonic()+5
        while not self.session.closed and time.monotonic()<until:
            APP.processEvents();time.sleep(.01)
        self.assertTrue(self.session.closed)

    def draw(self, tool, start=(30, 30), end=(200, 120)):
        self.session.choose_tool(tool)
        overlay = self.session.overlays[0]
        for typ, xy, button, buttons, handler in [
            (QEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, "press"),
            (QEvent.Type.MouseMove, end, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, "move"),
            (QEvent.Type.MouseButtonRelease, end, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, "release")]:
            physical = self.session.rect.topLeft() + QPoint(*xy)
            event = QMouseEvent(typ, QPointF(*xy), QPointF(*xy), button, buttons, Qt.KeyboardModifier.NoModifier)
            with patch("snapforge.inline.physical_point", return_value=physical):
                self.session.route_mouse(overlay, event, handler)

    def test_selection_becomes_inline_editor_without_closing_overlays(self):
        self.session.show(); APP.processEvents()
        self.assertTrue(self.session.editing)
        self.assertFalse(self.session.closed)
        self.assertEqual(self.session.doc.image.size().width(), 400)
        self.assertFalse(self.session.engine.isVisible())
        self.assertIsNotNone(self.session.toolbar)

    def test_physical_coordinates_draw_and_undo_in_place(self):
        self.draw("arrow")
        self.draw("blur", (100, 100), (220, 170))
        self.assertEqual([layer.tool for layer in self.session.doc.layers], ["arrow", "blur"])
        self.assertEqual(self.session.doc.layers[0].points, [(30, 30), (200, 120)])
        self.session.doc_undo(); self.assertEqual(len(self.session.doc.layers), 1)
        self.session.doc_redo(); self.assertEqual(len(self.session.doc.layers), 2)

    def test_copy_renders_layers_and_finishes(self):
        self.draw("redact")
        snapshots = []
        self.session.completed.connect(snapshots.append)
        self.session.key_press(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier))
        self.wait_finished()
        image = APP.clipboard().image()
        self.assertEqual(image.pixelColor(80, 80), QColor("black"))
        self.assertEqual((image.width(), image.height()), (400, 250))
        self.assertTrue(self.session.closed)
        self.assertEqual(snapshots[0]["destination"], "copy")

    def test_direct_save_and_cancel_keep_expected_lifecycle(self):
        self.draw("redact")
        self.session.save()
        self.assertIsNotNone(self.session.file_dialog)
        self.session.file_dialog.reject();APP.processEvents()
        self.assertFalse(self.session.closed)
        target=Path(self.temp.name)/"inline.png"
        self.session.start_export(str(target),"PNG")
        self.wait_finished()
        self.assertEqual(QImage(str(target)).pixelColor(80, 80), QColor("black"))

    def test_adjust_selection_preserves_global_annotation_position(self):
        self.draw("rect")
        previous = self.session.doc.layers[0].points[0]
        self.session.adjust_selection()
        self.session.rect.translate(-20, -10)
        self.session.finish()
        current = self.session.doc.layers[0].points[0]
        self.assertEqual(current, (previous[0] + 20, previous[1] + 10))

    def test_overlay_painting_keeps_selection_on_original_desktop(self):
        self.draw("redact")
        # Test the exact painter entry point used by every physical monitor.
        overlay = self.session.overlays[0]
        target = QImage(overlay.size(), QImage.Format.Format_ARGB32); target.fill(QColor("gray"))
        self.session.engine.display = self.session.doc.image
        from snapforge.imaging import render
        self.session.engine.display = render(self.session.doc.image, self.session.doc.layers)
        p = QPainter(target); self.session.paint_overlay(overlay, p); p.end()
        r = overlay.local_selection()
        self.assertEqual(target.pixelColor(round(r.left() + 80 / overlay.sx), round(r.top() + 80 / overlay.sy)), QColor("black"))

    def test_controller_does_not_open_main_window_after_copy(self):
        with patch.object(QSystemTrayIcon, "show"):
            controller = Controller(APP, self.store, enable_hotkeys=False)
        try:
            self.draw("rect")
            self.session.completed.connect(controller.complete_inline)
            self.session.copy()
            self.wait_finished()
            self.assertFalse(controller.window.isVisible())
            self.assertFalse(controller.capturing)
            self.assertEqual(len(controller.window.doc.layers), 1)
            self.assertFalse(controller.window.doc.dirty)
        finally:
            controller.hotkeys.clear(); APP.removeNativeEventFilter(controller.hotkeys)
            controller.tray.hide(); controller.window.canvas.shutdown()
            controller.window.force_close = True; controller.window.close(); controller.window.deleteLater()
            controller.deleteLater()

    def test_inline_text_and_color_use_no_modal_dialog(self):
        self.session.start_text(QPointF(40,50))
        self.session.toolbar.text_edit.setPlainText("Merhaba BlexShot")
        self.assertEqual(self.session.engine.draft.text,"Merhaba BlexShot")
        self.assertIsNone(APP.activeModalWidget())
        self.session.set_color("#2684ff")
        self.session.commit_text()
        self.assertEqual(self.session.doc.layers[-1].text,"Merhaba BlexShot")
        self.assertEqual(self.session.doc.layers[-1].color,"#2684ff")

    def test_compact_settings_toggle_and_text_auto_expand(self):
        toolbar = self.session.toolbar
        self.session.choose_tool("arrow")
        self.assertTrue(toolbar.properties.isHidden())
        toolbar.settings_button.click()
        self.assertFalse(toolbar.properties.isHidden())
        self.session.choose_tool("redact")
        self.assertTrue(toolbar.properties.isHidden())
        self.assertFalse(toolbar.settings_button.isEnabled())
        self.session.choose_tool("text")
        self.assertFalse(toolbar.properties.isHidden())
        self.assertFalse(toolbar.text_area.isHidden())
        toolbar.settings_button.click()
        self.assertTrue(toolbar.properties.isHidden())

    def test_export_runs_without_blocking_event_loop(self):
        from PySide6.QtCore import QTimer
        beats=[]
        def slow(image,layers):
            time.sleep(.2);return image.copy()
        with patch("snapforge.exporting.render",side_effect=slow):
            before=time.monotonic();self.session.copy()
            self.assertLess(time.monotonic()-before,.1)
            QTimer.singleShot(0,lambda:beats.append(True))
            APP.processEvents();self.assertTrue(beats)
            self.wait_finished()
