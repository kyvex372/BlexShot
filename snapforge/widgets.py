from PySide6.QtCore import Property, QPropertyAnimation, QEasingCurve, Qt, QPoint, QSize
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QToolButton, QFrame, QHBoxLayout, QLabel

from .icons import icon


class ToolButton(QToolButton):
    def __init__(self, name, label, callback=None, parent=None, checkable=False):
        super().__init__(parent)
        self.setProperty("icon_name", name)
        self.setIcon(icon(name))
        self.setIconSize(QSize(21, 21))
        self.setFixedSize(40, 40)
        self.setToolTip(label)
        self.setAccessibleName(label)
        self.setCheckable(checkable)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._glow = 0.0
        self.animation = QPropertyAnimation(self, b"glow", self)
        self.animation.setDuration(140)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animate = True
        if callback:
            self.clicked.connect(callback)

    def get_glow(self):
        return self._glow

    def set_glow(self, value):
        self._glow = value
        self.update()

    glow = Property(float, get_glow, set_glow)

    def enterEvent(self, event):
        self.animation.stop()
        self.animation.setStartValue(self._glow)
        self.animation.setEndValue(1)
        if self.animate:
            self.animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.animation.stop()
        self.animation.setStartValue(self._glow)
        self.animation.setEndValue(0)
        if self.animate:
            self.animation.start()
        else:
            self.set_glow(0)
        super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._glow:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(QPen(QColor(180, 198, 210, round(self._glow * 90)), 1))
            p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 7, 7)


class FloatingTools(QFrame):
    def __init__(self, parent):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("panel")
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(8, 6, 8, 6)
        self.layout.setSpacing(3)
        self.grip = QLabel("⠿")
        self.grip.setToolTip("Araç çubuğunu sürükleyin")
        self.grip.setFixedWidth(18)
        self.grip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.layout.addWidget(self.grip)
        self.drag_offset = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self.drag_offset is not None:
            self.place(event.globalPosition().toPoint() - self.drag_offset)

    def mouseReleaseEvent(self, event):
        self.drag_offset = None

    def place(self, point):
        from PySide6.QtWidgets import QApplication
        screen = QApplication.screenAt(point) or self.parent().screen()
        bounds = screen.availableGeometry()
        self.adjustSize()
        self.move(QPoint(max(bounds.left(), min(point.x(), bounds.right() - self.width() + 1)),
                         max(bounds.top(), min(point.y(), bounds.bottom() - self.height() + 1))))
