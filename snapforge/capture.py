"""Frozen desktop capture, per-monitor overlays, physical-pixel selection."""
from dataclasses import dataclass

import mss
from PySide6.QtCore import QObject, QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from .platform import IS_WINDOWS, cursor_position


@dataclass
class DesktopFrame:
    image: QImage
    bounds: QRect
    monitors: list

    def crop(self, rect):
        r = rect.intersected(self.bounds)
        if r.isEmpty():
            raise ValueError("Seçim ekran sınırlarının dışında.")
        return self.image.copy(r.translated(-self.bounds.topLeft()))


def grab_desktop():
    with mss.mss() as capture:
        monitors = [dict(m) for m in capture.monitors]
        full = monitors[0]
        shot = capture.grab(full)
        image = QImage(shot.bgra, shot.width, shot.height, shot.width * 4, QImage.Format.Format_RGB32).copy()
        return DesktopFrame(image, QRect(full["left"], full["top"], full["width"], full["height"]), monitors[1:])


def physical_point(event, overlay):
    if IS_WINDOWS:
        x, y = cursor_position()
        return QPoint(x, y)
    p = event.position()
    return QPoint(overlay.monitor["left"] + round(p.x() * overlay.sx),
                  overlay.monitor["top"] + round(p.y() * overlay.sy))


def selection_handles(rect):
    return [rect.topLeft(), QPoint(rect.center().x(), rect.top()), rect.topRight(),
            QPoint(rect.right(), rect.center().y()), rect.bottomRight(),
            QPoint(rect.center().x(), rect.bottom()), rect.bottomLeft(), QPoint(rect.left(), rect.center().y())]


class CaptureSession(QObject):
    accepted = Signal(QImage, QPoint)
    cancelled = Signal()

    def __init__(self, frame, parent=None):
        super().__init__(parent)
        self.frame = frame
        self.rect = QRect()
        self.anchor = QPoint()
        self.initial = QRect()
        self.mode = ""
        self.handle = -1
        self.overlays = []
        self.closed = False
        screens = QApplication.screens()
        for monitor in frame.monitors:
            # Qt keeps native origins on Windows even when size is in DIPs.
            screen = min(screens, key=lambda s: abs(s.geometry().x() - monitor["left"]) + abs(s.geometry().y() - monitor["top"]))
            overlay = CaptureOverlay(self, monitor, screen)
            self.overlays.append(overlay)

    def show(self):
        for overlay in self.overlays:
            overlay.show()
            overlay.raise_()
        point = QCursor.pos()
        current = next((o for o in self.overlays if o.geometry().contains(point)), self.overlays[0])
        current.activateWindow()
        current.setFocus()

    def update(self):
        for overlay in self.overlays:
            overlay.update()

    def press(self, point, tolerance):
        self.anchor = point
        self.initial = QRect(self.rect)
        self.handle = next((i for i, p in enumerate(selection_handles(self.rect))
                            if not self.rect.isEmpty() and (p - point).manhattanLength() < tolerance), -1)
        if self.handle >= 0:
            self.mode = "resize"
        elif self.rect.contains(point):
            self.mode = "move"
        else:
            self.mode = "new"
            self.rect = QRect(point, point)
        self.update()

    def move(self, point):
        b = self.frame.bounds
        point = QPoint(max(b.left(), min(point.x(), b.right())), max(b.top(), min(point.y(), b.bottom())))
        if self.mode == "new":
            self.rect = QRect(self.anchor, point).normalized()
        elif self.mode == "move":
            r = self.initial.translated(point - self.anchor)
            r.moveLeft(max(b.left(), min(r.left(), b.right() - r.width() + 1)))
            r.moveTop(max(b.top(), min(r.top(), b.bottom() - r.height() + 1)))
            self.rect = r
        elif self.mode == "resize":
            r = QRect(self.initial)
            if self.handle in (0, 6, 7):
                r.setLeft(point.x())
            if self.handle in (2, 3, 4):
                r.setRight(point.x())
            if self.handle in (0, 1, 2):
                r.setTop(point.y())
            if self.handle in (4, 5, 6):
                r.setBottom(point.y())
            self.rect = r.normalized()
        self.update()

    def finish(self):
        if self.closed or self.rect.width() < 2 or self.rect.height() < 2:
            return
        image = self.frame.crop(self.rect)
        point = QCursor.pos()
        self.close()
        self.accepted.emit(image, point)

    def cancel(self):
        if not self.closed:
            self.close()
            self.cancelled.emit()

    def close(self):
        self.closed = True
        for overlay in self.overlays:
            overlay.close()
            overlay.deleteLater()
        self.overlays.clear()


class CaptureOverlay(QWidget):
    def __init__(self, session, monitor, screen):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.session = session
        self.monitor = monitor
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        self.sx = monitor["width"] / screen.geometry().width()
        self.sy = monitor["height"] / screen.geometry().height()
        r = QRect(monitor["left"], monitor["top"], monitor["width"], monitor["height"])
        self.background = session.frame.crop(r)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.confirm_rect = QRectF()
        self.cancel_rect = QRectF()

    def local_selection(self):
        r = self.session.rect
        return QRectF((r.x() - self.monitor["left"]) / self.sx, (r.y() - self.monitor["top"]) / self.sy,
                      r.width() / self.sx, r.height() / self.sy)

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawImage(self.rect(), self.background)
        p.fillRect(self.rect(), QColor(7, 10, 18, 125))
        if getattr(self.session, "editing", False):
            self.session.paint_overlay(self, p)
            return
        r = self.local_selection()
        self.confirm_rect = QRectF()
        self.cancel_rect = QRectF()
        if not self.session.rect.isEmpty():
            p.save()
            p.setClipRect(r)
            p.drawImage(self.rect(), self.background)
            p.restore()
            p.setPen(QPen(QColor("#d2dce3"), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r)
            p.setBrush(QColor("white"))
            for point in selection_handles(self.session.rect):
                x = (point.x() - self.monitor["left"]) / self.sx
                y = (point.y() - self.monitor["top"]) / self.sy
                p.drawRect(QRectF(x - 3, y - 3, 6, 6))
            if r.intersects(QRectF(self.rect())):
                x = max(12, min(r.x(), self.width() - 310))
                y = max(12, min(r.bottom() + 12, self.height() - 58))
                bar = QRectF(x, y, 296, 42)
                p.setPen(QColor("#46535c"))
                p.setBrush(QColor("#1d2327"))
                p.drawRoundedRect(bar, 10, 10)
                p.setPen(QColor("#edf1f4"))
                p.drawText(QRectF(x + 12, y, 135, 42), Qt.AlignmentFlag.AlignVCenter,
                           f"{self.session.rect.width()} × {self.session.rect.height()} px")
                self.confirm_rect = QRectF(x + 151, y + 6, 82, 30)
                self.cancel_rect = QRectF(x + 239, y + 6, 49, 30)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#526670"))
                p.drawRoundedRect(self.confirm_rect, 6, 6)
                p.setPen(QColor("white"))
                p.drawText(self.confirm_rect, Qt.AlignmentFlag.AlignCenter, "Düzenle ↵")
                p.drawText(self.cancel_rect, Qt.AlignmentFlag.AlignCenter, "Esc")
        else:
            banner = QRectF((self.width() - 480) / 2, 32, 480, 48)
            p.setPen(QColor("#46535c"))
            p.setBrush(QColor("#1d2327"))
            p.drawRoundedRect(banner, 12, 12)
            p.setPen(QColor("#f0f4f7"))
            p.drawText(banner, Qt.AlignmentFlag.AlignCenter, "Alan seçin   ·   Enter: düzenle   ·   Esc: iptal   ·   F: bu ekran")

    def mousePressEvent(self, event):
        if getattr(self.session, "editing", False):
            self.session.route_mouse(self, event, "press")
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.session.cancel()
        elif event.button() == Qt.MouseButton.LeftButton:
            if self.confirm_rect.contains(event.position()):
                self.session.finish()
            elif self.cancel_rect.contains(event.position()):
                self.session.cancel()
            else:
                self.session.press(physical_point(event, self), 12 * self.sx)

    def mouseMoveEvent(self, event):
        if getattr(self.session, "editing", False):
            self.session.route_mouse(self, event, "move")
            return
        if event.buttons() & Qt.MouseButton.LeftButton and self.session.mode:
            self.session.move(physical_point(event, self))

    def mouseReleaseEvent(self, event):
        if getattr(self.session, "editing", False):
            self.session.route_mouse(self, event, "release")
            return
        if event.button() == Qt.MouseButton.LeftButton and self.session.mode:
            self.session.move(physical_point(event, self))
        was_selecting = bool(self.session.mode)
        self.session.mode = ""
        if was_selecting and getattr(self.session, "auto_edit", False):
            self.session.finish()

    def mouseDoubleClickEvent(self, event):
        if getattr(self.session, "editing", False):
            self.session.route_mouse(self, event, "double")
            return
        if self.session.rect.contains(physical_point(event, self)):
            self.session.finish()

    def keyPressEvent(self, event):
        if getattr(self.session, "editing", False):
            self.session.key_press(event)
            return
        if event.key() == Qt.Key.Key_Escape:
            self.session.cancel()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.session.finish()
        elif event.key() == Qt.Key.Key_F:
            self.session.rect = QRect(self.monitor["left"], self.monitor["top"], self.monitor["width"], self.monitor["height"])
            self.session.finish()
