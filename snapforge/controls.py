"""Custom-painted settings controls and explicit shortcut recording."""
from PySide6.QtCore import Qt, Signal, QRectF, QPropertyAnimation, Property
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QPushButton, QFrame, QHBoxLayout, QLabel
from .hotkeys import parse_hotkey
from .icons import icon


class Segmented(QFrame):
    currentIndexChanged = Signal(int)
    currentTextChanged = Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent); self.items=[]; self.buttons=[]; self.index=-1
        self.setObjectName("segmented"); self.row=QHBoxLayout(self); self.row.setContentsMargins(3,3,3,3); self.row.setSpacing(3)
    def addItem(self,title,data=None):
        i=len(self.items);self.items.append((title,data));b=QPushButton(title);b.setObjectName("segment")
        b.setCheckable(True);b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(lambda checked=False,index=i:self.setCurrentIndex(index));self.buttons.append(b);self.row.addWidget(b)
        if self.index==-1:self.setCurrentIndex(0)
    def addItems(self,items):
        for title in items:self.addItem(title)
    def currentData(self):return self.items[self.index][1] if self.index>=0 else None
    def currentText(self):return self.items[self.index][0] if self.index>=0 else ""
    def setCurrentText(self,title):
        for i,(name,data) in enumerate(self.items):
            if title==name:self.setCurrentIndex(i);return
    def setCurrentIndex(self,index):
        if not 0<=index<len(self.items):return
        changed=self.index!=index;self.index=index
        for i,b in enumerate(self.buttons):b.setChecked(i==index)
        if changed:self.currentIndexChanged.emit(index);self.currentTextChanged.emit(self.currentText())


class Toggle(QAbstractButton):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setText(title); self.setCheckable(True); self.setMinimumHeight(32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(self.palette().windowText().color())
        p.drawText(self.rect().adjusted(0,0,-54,0), Qt.AlignmentFlag.AlignVCenter, self.text())
        x, y = self.width()-40, (self.height()-20)/2
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#009b8d" if self.isChecked() else "#b2c5cf"))
        p.drawRoundedRect(QRectF(x,y,36,20),10,10)
        p.setBrush(QColor("#ffffff")); p.drawEllipse(QRectF(x+(18 if self.isChecked() else 3),y+3,14,14))
        if self.hasFocus():
            p.setPen(QPen(QColor("#009b8d"),1)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(self.rect().adjusted(1,1,-1,-1),5,5)


class ShortcutRecorder(QPushButton):
    keySequenceChanged = Signal(object)
    recording_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sequence = QKeySequence(); self.recording = False; self.pending = None
        self.setObjectName("shortcutRecorder"); self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self.start_recording)
        self.setToolTip("Tıklayın, ardından atamak istediğiniz tuşa veya birleşime basın.")

    def setMaximumSequenceLength(self, count): pass

    def keySequence(self): return QKeySequence(self.sequence)

    def setKeySequence(self, sequence):
        self.sequence = QKeySequence(sequence)
        self.setText(self.sequence.toString(QKeySequence.SequenceFormat.NativeText) or "Atanmamış")
        self.keySequenceChanged.emit(self.keySequence())

    def start_recording(self):
        if self.recording: self.stop_recording(); return
        self.recording = True; self.pending = None
        self.recording_changed.emit(True)
        self.setProperty("recording", True); self.style().unpolish(self); self.style().polish(self)
        self.setText("Tuşlara basın…"); self.setFocus(); self.grabKeyboard()

    def stop_recording(self, commit=False):
        if not self.recording: return
        self.releaseKeyboard(); self.recording = False
        if commit and self.pending is not None: self.setKeySequence(self.pending)
        else: self.setText(self.sequence.toString(QKeySequence.SequenceFormat.NativeText) or "Atanmamış")
        self.pending = None
        self.setProperty("recording", False); self.style().unpolish(self); self.style().polish(self)
        self.recording_changed.emit(False)

    def keyPressEvent(self, event):
        if not self.recording: return super().keyPressEvent(event)
        if event.isAutoRepeat(): return
        if event.key() in (Qt.Key.Key_Control,Qt.Key.Key_Shift,Qt.Key.Key_Alt,Qt.Key.Key_Meta,Qt.Key.Key_AltGr): return
        candidate = QKeySequence(event.keyCombination())
        try: parse_hotkey(candidate.toString(QKeySequence.SequenceFormat.PortableText))
        except ValueError as exc:
            self.setText("Farklı bir tuş deneyin"); self.setToolTip(str(exc)); return
        self.pending = candidate
        self.setText(candidate.toString(QKeySequence.SequenceFormat.NativeText))

    def keyReleaseEvent(self, event):
        if self.recording and self.pending is not None and not event.isAutoRepeat(): self.stop_recording(True)
        else: super().keyReleaseEvent(event)

    def focusOutEvent(self, event):
        self.stop_recording(); super().focusOutEvent(event)

    def hideEvent(self, event):
        self.stop_recording(); super().hideEvent(event)


class TitleBar(QFrame):
    def __init__(self, window):
        super().__init__(window); self.window = window; self.anchor = None
        self.setObjectName("customTitleBar"); self.setFixedHeight(32)
        row=QHBoxLayout(self); row.setContentsMargins(18,0,6,0)
        title=QLabel("BLEXSHOT  /  CAPTURE STUDIO"); title.setObjectName("titleCaption")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row.addWidget(title); row.addStretch()
        for name, hint, action in [("minimize","Küçült",window.showMinimized),("close","Tepsiye küçült",window.close)]:
            b=QPushButton(); b.setObjectName("windowControl"); b.setIcon(icon(name)); b.setFixedSize(32,28)
            b.setToolTip(hint); b.setAccessibleName(hint); b.clicked.connect(action); row.addWidget(b)

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton: self.anchor=event.globalPosition().toPoint()-self.window.pos()
    def mouseMoveEvent(self,event):
        if self.anchor is not None: self.window.move(event.globalPosition().toPoint()-self.anchor)
    def mouseReleaseEvent(self,event): self.anchor=None
