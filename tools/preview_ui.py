"""Render UI inspection artifacts with a synthetic (non-user) image fixture."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from snapforge.settings import SettingsStore
from snapforge.theme import apply_theme
from snapforge.document import Annotation
from snapforge.dialogs import SettingsDialog
from snapforge.window import MainWindow

root = Path(__file__).resolve().parent.parent
output = root / "artifacts"
output.mkdir(exist_ok=True)
app = QApplication([]); app.setStyle("Fusion"); apply_theme(app)
window = MainWindow(SettingsStore(output / "preview-settings.json"))
window.resize(1320, 860); window.show(); QTest.qWait(150)
window.grab().save(str(output / "welcome.png"))
image = QImage(1120, 700, QImage.Format.Format_ARGB32); image.fill(QColor("#f5f6fa"))
p = QPainter(image); p.setRenderHint(QPainter.RenderHint.Antialiasing)
p.fillRect(0, 0, 200, 700, QColor("#202638"))
p.setPen(QColor("#ffffff")); p.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold)); p.drawText(30, 55, "workspace.")
p.setFont(QFont("Segoe UI", 11))
for y, text in [(125, "Genel bakış"), (175, "Projeler"), (225, "Raporlar"), (275, "Ekip")]:
    if y == 125: p.fillRect(16, 96, 168, 44, QColor("#3a4160"))
    p.setPen(QColor("#cbd2e5")); p.drawText(32, y, text)
p.setPen(QColor("#24283b")); p.setFont(QFont("Segoe UI", 25, QFont.Weight.Bold)); p.drawText(240, 65, "Proje özeti")
p.setFont(QFont("Segoe UI", 11)); p.setPen(QColor("#747b90")); p.drawText(240, 99, "Bu haftaki ilerlemenize bir bakış.")
for x, title, number in [(240, "Tamamlanan görev", "128"), (526, "Aktif projeler", "12"), (812, "Ekip üyesi", "24")]:
    p.setPen(QPen(QColor("#e0e3ed"), 1)); p.setBrush(QColor("white")); p.drawRoundedRect(QRectF(x, 135, 262, 130), 12, 12)
    p.setPen(QColor("#777f95")); p.setFont(QFont("Segoe UI", 11)); p.drawText(x + 20, 169, title)
    p.setPen(QColor("#252a40")); p.setFont(QFont("Segoe UI", 27, QFont.Weight.Bold)); p.drawText(x + 20, 229, number)
p.setPen(QPen(QColor("#e0e3ed"), 1)); p.setBrush(QColor("white")); p.drawRoundedRect(QRectF(240, 290, 834, 260), 12, 12)
p.setPen(QColor("#252a40")); p.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold)); p.drawText(262, 327, "Haftalık ilerleme")
for y in (370, 420, 470, 520):
    p.setPen(QPen(QColor("#edf0f6"), 1)); p.drawLine(264, y, 1050, y)
path = QPainterPath(QPointF(270, 490))
for x, y in [(380, 450), (490, 465), (600, 405), (710, 430), (820, 360), (930, 390), (1040, 350)]: path.lineTo(x, y)
p.setPen(QPen(QColor("#8a6bda"), 3)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(path)
p.setFont(QFont("Segoe UI", 11)); p.setPen(QColor("#51596e")); p.drawText(260, 600, "İletişim: test@example.invalid     ·     Dahili referans: 4829-7160")
p.end()
window.set_document(image, "proje-ozeti.png")
for layer in [Annotation("rect", [(520, 130), (795, 268)], color="#a78bfa", width=4),
              Annotation("arrow", [(870, 115), (735, 169)], color="#a78bfa", width=5),
              Annotation("text", [(850, 75)], color="#7855c8", text="Odak noktası", font_size=26),
              Annotation("number", [(247, 310)], color="#8b6bd6", number=1, font_size=22),
              Annotation("blur", [(325, 575), (785, 612)], strength=12)]: window.doc.add(layer)
window.choose_tool("select"); window.canvas.select(window.doc.layers[-1])
for _ in range(120):
    app.processEvents()
    time.sleep(.01)
window.grab().save(str(output / "editor.png"))
window.resize(960, 680); QTest.qWait(200); window.grab().save(str(output / "editor-compact.png"))
dialog = SettingsDialog(window.store.value, window); dialog.show(); QTest.qWait(100); dialog.grab().save(str(output / "settings.png")); dialog.close()
apply_theme(app, "light"); QTest.qWait(100); window.grab().save(str(output / "editor-light.png"))
window.canvas.shutdown(); window.force_close = True; window.close()
print("UI inspection artifacts:", output)
