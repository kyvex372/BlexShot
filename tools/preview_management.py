"""Render the control centre and tray menu for visual inspection."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "windows" if os.name == "nt" else "offscreen")
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication
from snapforge.app import Controller
from snapforge.settings import SettingsStore
from snapforge.theme import apply_theme

root = Path(__file__).resolve().parent.parent
output = root / "artifacts"
output.mkdir(exist_ok=True)
app = QApplication([]); app.setStyle("Fusion"); app.setQuitOnLastWindowClosed(False); apply_theme(app)
controller = Controller(app, SettingsStore(output / "management-preview.json"), enable_hotkeys=False)
controller.settings()
dialog = controller.management
dialog.folder.setText(r"C:\Screenshots\BlexShot")


def settle():
    for _ in range(12):
        app.processEvents(); time.sleep(.01)


for index, name in enumerate(("general", "shortcuts", "output", "editor")):
    dialog.nav.setCurrentRow(index)
    if name == "output":
        dialog.format.setCurrentText("JPG"); dialog.quality.setValue(92)
    settle(); dialog.grab().save(str(output / f"management-{name}.png"))
dialog.nav.setCurrentRow(0); dialog.resize(640, 480); settle()
dialog.grab().save(str(output / "management-compact.png"))
controller.menu.popup(QPoint(300, 200)); settle(); controller.menu.grab().save(str(output / "tray-menu.png")); controller.menu.hide()
apply_theme(app, "light"); dialog.resize(720, 520); settle(); dialog.grab().save(str(output / "management-light.png"))
controller.hotkeys.clear(); controller.tray.hide(); dialog.hide(); controller.window.canvas.shutdown()
controller.window.force_close = True; controller.window.close()
print("Management previews:", output)
