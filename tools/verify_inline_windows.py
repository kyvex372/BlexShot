"""Native drag → in-place annotation → clipboard/save; no editor window."""
import json
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snapforge.platform import enable_dpi_awareness
enable_dpi_awareness()
from PySide6.QtCore import QPoint, QRect, QTimer, Qt
from PySide6.QtGui import QColor, QCursor, QFont, QImage, QPainter, QPen
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget, QFileDialog
from snapforge.app import Controller
from snapforge.capture import grab_desktop
from snapforge.settings import SettingsStore
from snapforge.theme import apply_theme

root = Path(__file__).resolve().parent.parent
output = root / "artifacts"; output.mkdir(exist_ok=True)
app = QApplication([]); app.setQuitOnLastWindowClosed(False); app.setStyle("Fusion"); apply_theme(app)
controller = Controller(app, SettingsStore(output / "inline-native-settings.json"), enable_hotkeys=False)
report = {}


class Pattern(QWidget):
    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#ededed"))
        p.fillRect(0, 0, self.width(), 50, QColor("#242a2e"))
        p.setPen(QColor("#eef1f4")); p.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold)); p.drawText(24, 32, "Proje notları")
        p.setPen(QColor("#20272b")); p.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold)); p.drawText(40, 110, "Geri bildirim, tam yerinde.")
        p.setFont(QFont("Segoe UI", 13)); p.setPen(QColor("#5d666d")); p.drawText(40, 148, "Önemli noktaları işaretleyin ve paylaşın.")
        p.setBrush(QColor("#ffffff")); p.setPen(QPen(QColor("#cdd2d5"), 1)); p.drawRoundedRect(40, 180, 600, 210, 10, 10)
        p.setPen(QColor("#252c31")); p.setFont(QFont("Segoe UI", 17, QFont.Weight.DemiBold)); p.drawText(60, 220, "Tasarım güncellemesi")
        p.setFont(QFont("Segoe UI", 12)); p.drawText(60, 260, "Durum: İncelemeye hazır")
        p.drawText(60, 295, "İletişim: test@example.invalid")
        p.drawText(60, 330, "İç referans: 4829–7160")


pattern = Pattern(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
pattern.setGeometry(80, 80, 1000, 720); pattern.show()


def finish(error=None):
    if error: report["error"] = repr(error)
    if controller.session:
        controller.session.close(); controller.session = None
    controller.window.canvas.shutdown(); controller.window.force_close = True; controller.window.close()
    controller.hotkeys.clear(); controller.tray.hide(); pattern.close()
    (output / "inline-native-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    app.exit(1 if error else 0)


def gesture(overlay, start, end, release=True):
    QCursor.setPos(overlay.mapToGlobal(start))
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    QCursor.setPos(overlay.mapToGlobal(end))
    QTest.mouseMove(overlay, end)
    if release: QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)


def select():
    try:
        session = controller.session
        overlay = next(o for o in session.overlays if o.monitor["left"] == 0 and o.monitor["top"] == 0)
        gesture(overlay, QPoint(120, 130), QPoint(760, 500))
        assert session.editing, "Mouse release did not start inline editing"
        assert not controller.window.isVisible(), "Main window opened after selection"
        assert not session.engine.isVisible(), "Input engine appeared as a child editor"
        report["automatic_inline_on_release"] = True
        report["monitor_count"] = len(session.overlays)
        report["selection_px"] = [session.rect.width(), session.rect.height()]
        session.choose_tool("arrow")
        gesture(overlay, QPoint(660, 190), QPoint(440, 240), release=False)
        assert session.engine.draft is not None, "No live annotation during drag"
        report["live_draft_while_dragging"] = True
        QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(440, 240))
        session.choose_tool("blur")
        gesture(overlay, QPoint(215, 345), QPoint(500, 395))
        session.choose_tool("redact")
        gesture(overlay, QPoint(215, 405), QPoint(405, 440))
        QTimer.singleShot(500, screenshot_and_copy)
    except Exception as exc: finish(exc)


def screenshot_and_copy():
    try:
        session = controller.session
        overlay = next(o for o in session.overlays if o.monitor["left"] == 0 and o.monitor["top"] == 0)
        # Only our own test window appears in this artifact.
        grab_desktop().crop(QRect(80, 80, 1000, 720)).save(str(output / "inline-desktop.png"))
        session.toolbar.grab().save(str(output / "inline-toolbar.png"))
        report["expected_size"]=[session.doc.image.width(),session.doc.image.height()]
        QTest.keyClick(overlay, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        QTimer.singleShot(100, verify_copy)
    except Exception as exc: finish(exc)


def verify_copy():
    try:
        if controller.session is not None:QTimer.singleShot(100,verify_copy);return
        assert not controller.window.isVisible(), "Main window opened after copying"
        image=app.clipboard().image()
        assert [image.width(),image.height()]==report["expected_size"]
        assert image.pixelColor(150,290)==QColor("black")
        report["ctrl_c_closes_without_main_window"]=True
        controller.capture("region");QTimer.singleShot(500,save_second_capture)
    except Exception as exc:finish(exc)


def save_second_capture():
    try:
        session = controller.session
        overlay = next(o for o in session.overlays if o.monitor["left"] == 0 and o.monitor["top"] == 0)
        gesture(overlay, QPoint(120, 130), QPoint(760, 500))
        session.choose_tool("redact")
        gesture(overlay, QPoint(215, 405), QPoint(405, 440))
        target = output / "inline-native-export.png"
        QTest.keyClick(overlay,Qt.Key.Key_S,Qt.KeyboardModifier.ControlModifier)
        dialog=session.file_dialog
        assert dialog is not None and dialog.isVisible()
        report["visible_nonblocking_save_dialog"]=True
        dialog.setOption(QFileDialog.Option.DontConfirmOverwrite,True)
        dialog.selectFile(str(target));dialog.accept()
        QTimer.singleShot(100,verify_save)
    except Exception as exc:finish(exc)


def verify_save():
    try:
        if controller.session is not None:QTimer.singleShot(100,verify_save);return
        assert not controller.window.isVisible()
        assert QImage(str(output/"inline-native-export.png")).pixelColor(150,290)==QColor("black")
        report["ctrl_s_saves_without_main_window"]=True;report["passed"]=True;finish()
    except Exception as exc:finish(exc)


QTimer.singleShot(200, lambda: controller.capture("region"))
QTimer.singleShot(750, select)
QTimer.singleShot(15000, lambda: finish(TimeoutError("Native inline test timed out")))
sys.exit(app.exec())
