from copy import deepcopy
import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPainterPathStroker, QPen
from PySide6.QtWidgets import QWidget, QInputDialog

from .document import Annotation, RECT_TOOLS, PRIVACY_TOOLS
from .imaging import draw_annotation
from .rendering import RenderQueue


class Canvas(QWidget):
    selection_changed = Signal(object)
    zoom_changed = Signal(float)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(250, 240)
        self.doc = None
        self.tool = "arrow"
        self.color = "#f59e0b"
        self.stroke = 4
        self.opacity = 1.0
        self.font_size = 28
        self.strength = 18
        self.zoom = 1.0
        self.offset = QPointF()
        self.selected_id = None
        self.draft = None
        self.display = None
        self.preview = None
        self.drag = ""
        self.before = None
        self.start = QPointF()
        self.last = QPointF()
        self.original = None
        self.space = False
        self.fitted = True
        self.renderer = RenderQueue(self)
        self.renderer.ready.connect(self._rendered)
        self.renderer.failed.connect(self.error)
        self.preview_renderer = RenderQueue(self)
        self.preview_renderer.ready.connect(self._preview_ready)
        self.preview_renderer.failed.connect(self.error)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(70)
        self.preview_timer.timeout.connect(self._request_preview)

    def set_document(self, doc):
        if self.doc:
            self.doc.changed.disconnect(self.document_changed)
        self.doc = doc
        self.doc.changed.connect(self.document_changed)
        self.display = doc.image
        self.draft = self.preview = None
        self.preview_renderer.invalidate()
        self.selected_id = None
        self.fit()
        self.document_changed()

    def document_changed(self):
        if not self.doc:
            return
        if self.selected_id and not self.doc.layer(self.selected_id):
            self.select(None)
        self.renderer.request(self.doc.image, self.doc.layers)
        self.update()

    def _rendered(self, image):
        self.display = image
        self.update()

    def _preview_ready(self, image):
        if self.draft and self.draft.tool in ("blur", "pixel"):
            self.preview = image
            self.update()

    def _request_preview(self):
        if self.draft and self.draft.tool in ("blur", "pixel"):
            self.preview_renderer.request(self.doc.image, [*self.doc.layers, self.draft])

    def fit(self):
        if self.doc:
            self.zoom = max(.02, min((self.width() - 80) / self.doc.image.width(), (self.height() - 80) / self.doc.image.height(), 1.0))
            self.offset = QPointF((self.width() - self.doc.image.width() * self.zoom) / 2,
                                  (self.height() - self.doc.image.height() * self.zoom) / 2)
            self.fitted = True
            self.zoom_changed.emit(self.zoom)
            self.update()

    def set_zoom(self, value, anchor=None):
        anchor = anchor or QPointF(self.rect().center())
        point = self.image_point(anchor)
        self.zoom = max(.02, min(8.0, value))
        self.offset = anchor - point * self.zoom
        self.fitted = False
        self.zoom_changed.emit(self.zoom)
        self.update()

    def image_point(self, point):
        return (point - self.offset) / self.zoom

    def bounded(self, point):
        return QPointF(max(0, min(point.x(), self.doc.image.width())), max(0, min(point.y(), self.doc.image.height())))

    def select(self, layer):
        self.selected_id = layer.id if layer else None
        self.selection_changed.emit(layer)
        self.update()

    def selected(self):
        return self.doc.layer(self.selected_id) if self.doc else None

    def set_tool(self, tool):
        self.tool = tool
        self.setCursor(Qt.CursorShape.OpenHandCursor if tool == "pan" else Qt.CursorShape.ArrowCursor if tool == "select" else Qt.CursorShape.CrossCursor)
        if tool != "select":
            self.select(None)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#111416"))
        p.setPen(QColor("#232a2f"))
        for x in range(12, self.width(), 24):
            for y in range(12, self.height(), 24):
                p.drawPoint(x, y)
        if not self.doc:
            return
        p.translate(self.offset)
        p.scale(self.zoom, self.zoom)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, self.zoom < 1)
        self.paint_document(p)

    def paint_document(self, p):
        """Paint image-coordinate content, also used by desktop capture overlays."""
        if not self.doc:
            return
        p.fillRect(QRectF(5 / self.zoom, 7 / self.zoom, self.doc.image.width(), self.doc.image.height()), QColor(0, 0, 0, 90))
        p.setClipRect(self.doc.image.rect())
        p.drawImage(0, 0, self.preview if self.preview is not None and self.draft else self.display or self.doc.image)
        if self.draft:
            if self.draft.tool in ("blur", "pixel"):
                p.setPen(QPen(QColor("#b6d1df"), 1 / self.zoom, Qt.PenStyle.DashLine))
                p.drawRect(self.draft.bounds())
            else:
                draw_annotation(p, self.draft)
        p.setClipping(False)
        layer = self.selected()
        if layer:
            r = layer.bounds().adjusted(-4 / self.zoom, -4 / self.zoom, 4 / self.zoom, 4 / self.zoom)
            p.setPen(QPen(QColor("#d7e1e8"), 1 / self.zoom, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r)
            if layer.tool in RECT_TOOLS:
                p.setBrush(QColor("#dce6ec"))
                for pt in [r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()]:
                    p.drawRect(QRectF(pt.x() - 4 / self.zoom, pt.y() - 4 / self.zoom, 8 / self.zoom, 8 / self.zoom))

    def hit_test(self, point):
        for layer in reversed(self.doc.layers):
            if not layer.visible:
                continue
            tolerance = max(7 / self.zoom, layer.width / 2 + 3)
            if layer.tool in ("pen", "highlight", "line", "arrow"):
                path = QPainterPath(QPointF(*layer.points[0]))
                if len(layer.points) == 1:
                    if (QPointF(*layer.points[0]) - point).manhattanLength() < tolerance:
                        return layer
                for xy in layer.points[1:]:
                    path.lineTo(QPointF(*xy))
                stroker = QPainterPathStroker()
                stroker.setWidth(tolerance * 2)
                if stroker.createStroke(path).contains(point):
                    return layer
            elif layer.bounds().adjusted(-tolerance, -tolerance, tolerance, tolerance).contains(point):
                return layer
        return None

    def mousePressEvent(self, event):
        self.setFocus()
        if not self.doc:
            return
        self.last = event.position()
        if event.button() == Qt.MouseButton.MiddleButton or self.tool == "pan" or self.space:
            self.drag = "pan"
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        point = self.image_point(event.position())
        if not QRectF(self.doc.image.rect()).adjusted(-8 / self.zoom, -8 / self.zoom, 8 / self.zoom, 8 / self.zoom).contains(point):
            self.select(None)
            return
        self.start = self.bounded(point)
        layer = self.selected()
        if self.tool == "select":
            if layer and layer.tool in RECT_TOOLS:
                r = layer.bounds().adjusted(-4 / self.zoom, -4 / self.zoom, 4 / self.zoom, 4 / self.zoom)
                corners = [r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()]
                for i, corner in enumerate(corners):
                    if (point - corner).manhattanLength() < 14 / self.zoom:
                        self.drag = f"resize{i}"
                        self.before = deepcopy(self.doc.layers)
                        self.original = deepcopy(layer)
                        return
            layer = self.hit_test(point)
            self.select(layer)
            if layer:
                self.before = deepcopy(self.doc.layers)
                self.original = deepcopy(layer)
                self.drag = "move"
            return
        if self.tool == "eraser":
            self.before = deepcopy(self.doc.layers)
            self.drag = "erase"
            self.erase_at(point)
            return
        p = (self.start.x(), self.start.y())
        self.draft = Annotation(self.tool, [p, p], self.color, self.stroke, self.opacity, self.font_size, self.strength)
        if self.tool == "highlight":
            self.draft.width = max(18, self.stroke * 4)
        if self.tool in ("pen", "highlight"):
            self.draft.points = [p]
        if self.tool == "text":
            text, accepted = QInputDialog.getMultiLineText(self, "Metin ekle", "Görüntü üzerinde görünecek metin:")
            if accepted and text.strip():
                self.draft.text = text.strip()
                self.doc.add(self.draft)
            self.draft = None
        elif self.tool == "number":
            self.draft.number = max((x.number for x in self.doc.layers if x.tool == "number"), default=0) + 1
            self.doc.add(self.draft)
            self.draft = None
        else:
            self.drag = "draw"
        self.update()

    def erase_at(self, point):
        layer = self.hit_test(point)
        if layer:
            self.doc.layers.remove(layer)
            self.document_changed()

    def mouseMoveEvent(self, event):
        if not self.doc or not self.drag:
            return
        if self.drag == "pan":
            self.offset += event.position() - self.last
            self.last = event.position()
            self.fitted = False
            self.update()
            return
        point = self.bounded(self.image_point(event.position()))
        if self.drag == "draw" and self.draft:
            xy = (point.x(), point.y())
            if self.tool in ("pen", "highlight"):
                prev = QPointF(*self.draft.points[-1])
                if (point - prev).manhattanLength() > .75 / self.zoom:
                    self.draft.points.append(xy)
            else:
                self.draft.points[-1] = xy
            if self.tool in ("blur", "pixel") and not self.preview_timer.isActive():
                self.preview_timer.start()
            self.update()
        elif self.drag == "move":
            layer = self.selected()
            if layer:
                delta = point - self.start
                layer.points = [(x + delta.x(), y + delta.y()) for x, y in self.original.points]
                self.document_changed()
        elif self.drag.startswith("resize"):
            layer = self.selected()
            if layer:
                r = self.original.bounds()
                opposite = [r.bottomRight(), r.bottomLeft(), r.topRight(), r.topLeft()][int(self.drag[-1])]
                layer.points = [(opposite.x(), opposite.y()), (point.x(), point.y())]
                self.document_changed()
        elif self.drag == "erase":
            self.erase_at(point)

    def mouseReleaseEvent(self, event):
        if not self.doc:
            return
        if self.drag in ("draw", "move") or self.drag.startswith("resize"):
            self.mouseMoveEvent(event)
        if self.draft:
            r = self.draft.bounds()
            if self.draft.tool in ("pen", "highlight") or r.width() > 1 or r.height() > 1:
                if self.draft.tool not in RECT_TOOLS or (r.width() > 1 and r.height() > 1):
                    self.doc.add(self.draft)
            self.draft = self.preview = None
            self.preview_timer.stop()
            self.preview_renderer.invalidate()
        elif self.before is not None and self.drag != "pan":
            self.doc.commit(self.before)
        self.before = None
        self.drag = ""
        self.update()

    def mouseDoubleClickEvent(self, event):
        if self.doc and self.tool == "select":
            layer = self.hit_test(self.image_point(event.position()))
            if layer and layer.tool == "text":
                text, ok = QInputDialog.getMultiLineText(self, "Metni düzenle", "Metin", layer.text)
                if ok and text.strip():
                    before = deepcopy(self.doc.layers)
                    layer.text = text.strip()
                    self.doc.commit(before)

    def wheelEvent(self, event):
        self.set_zoom(self.zoom * (1.15 if event.angleDelta().y() > 0 else 1 / 1.15), event.position())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.space = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif event.key() == Qt.Key.Key_Escape:
            self.draft = self.preview = None
            self.preview_renderer.invalidate()
            if self.before is not None:
                self.doc.layers = self.before
                self.document_changed()
            self.before = None
            self.drag = ""
            self.select(None)
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.selected():
            self.doc.remove(self.selected_id)
        elif event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down) and self.selected():
            before = deepcopy(self.doc.layers)
            step = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            dx = step * ((event.key() == Qt.Key.Key_Right) - (event.key() == Qt.Key.Key_Left))
            dy = step * ((event.key() == Qt.Key.Key_Down) - (event.key() == Qt.Key.Key_Up))
            self.selected().translate(dx, dy)
            self.doc.commit(before)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.space = False
            self.set_tool(self.tool)

    def resizeEvent(self, event):
        if self.fitted:
            self.fit()

    def shutdown(self):
        self.renderer.shutdown()
        self.preview_renderer.shutdown()
