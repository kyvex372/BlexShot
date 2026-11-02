"""Editable annotation data and bounded, image-independent undo history."""
from copy import deepcopy
from dataclasses import dataclass, field
import uuid

from PySide6.QtCore import QObject, Signal, QRectF, QPointF

TOOLS = {
    "select": ("Seç / taşı", "V"), "pen": ("Serbest kalem", "P"),
    "arrow": ("Ok", "A"), "line": ("Çizgi", "L"),
    "rect": ("Dikdörtgen", "R"), "ellipse": ("Elips", "E"),
    "highlight": ("Vurgulayıcı", "H"), "text": ("Metin", "T"),
    "number": ("Numaralı işaret", "N"), "blur": ("Gaussian blur", "B"),
    "pixel": ("Pikselleştir", "X"), "redact": ("Siyah sansür", "K"),
    "eraser": ("Nesne silgisi", "D"), "pan": ("Görüntüyü kaydır", "G"),
}
PRIVACY_TOOLS = {"blur", "pixel", "redact"}
RECT_TOOLS = {"rect", "ellipse", *PRIVACY_TOOLS}


@dataclass
class Annotation:
    tool: str
    points: list = field(default_factory=list)
    color: str = "#f59e0b"
    width: float = 4
    opacity: float = 1.0
    font_size: int = 28
    strength: int = 18
    text: str = ""
    number: int = 1
    visible: bool = True
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def bounds(self):
        if not self.points:
            return QRectF()
        xs, ys = zip(*self.points)
        r = QRectF(QPointF(min(xs), min(ys)), QPointF(max(xs), max(ys)))
        if self.tool == "text":
            from PySide6.QtGui import QFont, QFontMetricsF
            font = QFont("Segoe UI")
            font.setPixelSize(self.font_size)
            font.setWeight(QFont.Weight.DemiBold)
            fm = QFontMetricsF(font)
            lines = self.text.splitlines() or [""]
            r = QRectF(self.points[0][0], self.points[0][1], max(fm.horizontalAdvance(s) for s in lines) + 6,
                       fm.lineSpacing() * len(lines))
        elif self.tool == "number":
            radius = max(16, self.font_size * .65)
            r = QRectF(xs[0] - radius, ys[0] - radius, radius * 2, radius * 2)
        return r

    def translate(self, dx, dy):
        self.points = [(x + dx, y + dy) for x, y in self.points]


class Document(QObject):
    changed = Signal()

    def __init__(self, image, parent=None):
        super().__init__(parent)
        self.image = image.copy()
        self.image.setDevicePixelRatio(1)
        self.layers = []
        self.undo_states = []
        self.redo_states = []
        self.saved_state = None  # a new capture has not been exported

    @property
    def dirty(self):
        return self.saved_state is None or self.layers != self.saved_state

    def mark_saved(self):
        self.saved_state = deepcopy(self.layers)
        self.changed.emit()

    def commit(self, before):
        if before == self.layers:
            return
        self.undo_states.append(before)
        self.undo_states = self.undo_states[-80:]
        self.redo_states.clear()
        self.changed.emit()

    def add(self, layer):
        before = deepcopy(self.layers)
        self.layers.append(layer)
        self.commit(before)

    def remove(self, ident):
        before = deepcopy(self.layers)
        self.layers = [x for x in self.layers if x.id != ident]
        self.commit(before)

    def undo(self):
        if self.undo_states:
            self.redo_states.append(deepcopy(self.layers))
            self.layers = self.undo_states.pop()
            self.changed.emit()

    def redo(self):
        if self.redo_states:
            self.undo_states.append(deepcopy(self.layers))
            self.layers = self.redo_states.pop()
            self.changed.emit()

    def layer(self, ident):
        return next((x for x in self.layers if x.id == ident), None)
