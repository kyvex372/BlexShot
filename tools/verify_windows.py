"""Native Windows integration check. Does not change startup or saved preferences."""
import ctypes
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snapforge.platform import enable_dpi_awareness
enable_dpi_awareness()
from PySide6.QtCore import QTimer, QRect, QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication, QWidget
from snapforge.capture import grab_desktop, CaptureSession
from snapforge.document import Annotation
from snapforge.hotkeys import Hotkeys
from snapforge.imaging import render, save_image, to_array
from snapforge.platform import foreground_rect, user32
from snapforge.settings import SettingsStore
from snapforge.theme import apply_theme
from snapforge.window import MainWindow

root = Path(__file__).resolve().parent.parent
output = root / "artifacts"
output.mkdir(exist_ok=True)
app = QApplication([]); app.setQuitOnLastWindowClosed(False); app.setStyle("Fusion"); apply_theme(app)
report = {}
window = MainWindow(SettingsStore(output / "native-settings.json"))


class Pattern(QWidget):
    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#16334f"))
        for x in range(0, self.width(), 12):
            for y in range(0, self.height(), 12):
                p.fillRect(x, y, 6, 6, QColor("#dbe9fb"))
        p.fillRect(0, 0, 60, 60, QColor("#ff0000"))


pattern = Pattern(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
pattern.setGeometry(80, 80, 640, 400)
pattern.show(); pattern.raise_(); pattern.activateWindow()
native_api = user32()
native_api.SetForegroundWindow.argtypes = [ctypes.c_void_p]
native_api.SetForegroundWindow(int(pattern.winId()))
session = None
calls = []
hotkeys = Hotkeys(app, [lambda: calls.append("region"), lambda: calls.append("full"), lambda: calls.append("window")])


def fail(exc):
    report["error"] = repr(exc)
    finish()


def start():
    global session
    try:
        report["screens"] = [{"name": s.name(), "geometry": [s.geometry().x(), s.geometry().y(), s.geometry().width(), s.geometry().height()], "dpr": s.devicePixelRatio()} for s in app.screens()]
        frame = grab_desktop()
        report["physical_bounds"] = [frame.bounds.x(), frame.bounds.y(), frame.bounds.width(), frame.bounds.height()]
        native = foreground_rect()
        assert native, "No foreground window"
        native_rect = ctypes.wintypes.RECT()
        assert native_api.GetWindowRect(int(pattern.winId()), ctypes.byref(native_rect))
        rect = QRect(native_rect.left, native_rect.top, native_rect.right - native_rect.left, native_rect.bottom - native_rect.top)
        captured = frame.crop(rect)
        report["foreground_rect"] = native
        report["fixture_rect"] = [rect.x(), rect.y(), rect.width(), rect.height()]
        report["fixture_color"] = captured.pixelColor(20, 20).name()
        assert captured.pixelColor(20, 20).red() > 240, "Physical/DIP coordinates do not match fixture"
        report["mss_and_active_window"] = True
        pattern.hide()
        session = CaptureSession(frame)
        session.show()
        session.rect = rect
        session.update()
        session.accepted.connect(accepted)
        QTimer.singleShot(120, session.finish)
    except Exception as exc: fail(exc)


def accepted(image, point):
    try:
        window.set_document(image, "native-capture-test")
        window.doc.add(Annotation("arrow", [(80, 80), (180, 120)], color="#ff0000", width=6))
        window.doc.add(Annotation("blur", [(200, 100), (400, 250)], strength=14))
        window.doc.add(Annotation("redact", [(420, 100), (550, 240)]))
        window.copy_image()
        image = app.clipboard().image()
        assert image.pixelColor(450, 150) == QColor("black")
        save_image(image, output / "native-export.png")
        assert QImage(str(output / "native-export.png")).size() == image.size()
        report["capture_select_annotate_clipboard_save"] = True
        try:
            hotkeys.configure(["Print", "Ctrl+Print", "Alt+Print"])
            report["default_hotkeys_available"] = True
        except OSError as exc:
            report["default_hotkeys_available"] = False
            report["hotkey_conflict"] = str(exc)
        hotkeys.clear()
        hotkeys.configure(["Ctrl+Shift+F10", "Ctrl+Shift+F11", "Ctrl+Shift+F12"])
        other = Hotkeys(app, [lambda: None] * 3)
        try:
            other.configure(["Ctrl+Shift+F10", "Alt+Shift+F11", "Alt+Shift+F12"])
            raise AssertionError("Hotkey conflict was not reported")
        except OSError:
            report["hotkey_conflict_detected"] = True
        finally:
            other.clear(); app.removeNativeEventFilter(other)
        tid = ctypes.windll.kernel32.GetCurrentThreadId()
        assert ctypes.windll.user32.PostThreadMessageW(tid, 0x0312, 0x5300, 0)
        QTimer.singleShot(200, verify_final)
    except Exception as exc: fail(exc)


def verify_final():
    try:
        assert calls == ["region"], f"Native WM_HOTKEY not delivered: {calls}"
        report["native_hotkey_dispatch"] = True
        screen = window.screen().availableGeometry()
        window.floating.place(QPoint(screen.right() + 500, screen.bottom() + 500))
        assert screen.contains(window.floating.geometry())
        report["floating_toolbar_clamped"] = True
        # Measure a 4K composite with a large Gaussian region (no synthetic claim about all PCs).
        large = QImage(3840, 2160, QImage.Format.Format_ARGB32); large.fill(QColor("#5276ab"))
        t = time.perf_counter()
        render(large, [Annotation("blur", [(300, 200), (2900, 1700)], strength=18)])
        report["4k_large_blur_ms"] = round((time.perf_counter() - t) * 1000, 1)
        report["passed"] = True
        finish()
    except Exception as exc: fail(exc)


def finish():
    hotkeys.clear()
    if session and not session.closed: session.close()
    pattern.close()
    window.canvas.shutdown()
    window.force_close = True; window.close()
    (output / "native-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    app.exit(0 if report.get("passed") else 1)


QTimer.singleShot(250, start)
QTimer.singleShot(15000, lambda: fail(TimeoutError("Native verification timed out")))
sys.exit(app.exec())
