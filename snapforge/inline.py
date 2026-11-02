"""Edit directly on the frozen desktop, without opening the application editor."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRect, Qt, Signal, QTimer, QThreadPool
from PySide6.QtGui import QColor, QCursor, QMouseEvent, QPen
from PySide6.QtWidgets import (QApplication, QFileDialog)

from .canvas import Canvas
from .capture import CaptureSession, physical_point
from .document import Document, Annotation, TOOLS, PRIVACY_TOOLS
from .icons import icon


class InlineCanvas(Canvas):
    """Shared input/render engine; the monitor windows paint its content."""
    def __init__(self, session, parent):
        super().__init__(parent)
        self.session = session
        self.setMinimumSize(1, 1)
        # Parent monitor windows are shown later; never auto-show this input engine.
        self.hide()

    def fit(self):
        self.zoom = 1.0
        self.offset = QPointF()
        self.fitted = False

    def update(self, *args):
        super().update(*args)
        if hasattr(self, "session") and not self.session.closed:
            self.session.update()

    def wheelEvent(self, event):
        event.ignore()


from .palette import InlineToolbar
from .exporting import ExportTask


class InlineSession(CaptureSession):
    completed = Signal(object)

    def __init__(self, frame, store, parent=None):
        super().__init__(frame, parent)
        self.store = store
        self.editing = False
        self.auto_edit = True
        self.engine = InlineCanvas(self, self.overlays[0] if self.overlays else None)
        prefs = store.value
        self.engine.color, self.engine.stroke, self.engine.strength = prefs.color, prefs.stroke, prefs.blur
        self.engine.error.connect(self.show_error)
        self.doc = None
        self.document_rect = QRect()
        self.toolbar = None
        self.syncing = False
        self.text_draft = None
        self.text_layer_id = None
        self.busy = False
        self.file_dialog = None
        self.export_job = None

    def finish(self):
        """A selection becomes an on-screen editor, never an application window."""
        if self.closed or self.editing or self.rect.width() < 2 or self.rect.height() < 2:
            return
        image = self.frame.crop(self.rect)
        previous = self.doc
        self.doc = Document(image, self)
        if previous:
            self.doc.layers = deepcopy(previous.layers)
            delta = self.document_rect.topLeft() - self.rect.topLeft()
            for layer in self.doc.layers: layer.translate(delta.x(), delta.y())
        self.document_rect = QRect(self.rect)
        self.engine.set_document(self.doc)
        if previous: previous.deleteLater()
        self.editing = True
        if self.toolbar is None:
            self.toolbar = InlineToolbar(self, self.overlays[0] if self.overlays else None)
            self.engine.selection_changed.connect(self.selection_changed)
        self.doc.changed.connect(self.refresh)
        self.toolbar.dimensions.setText(f"{image.width()} × {image.height()}")
        self.choose_tool("arrow")
        point = QCursor.pos()
        current = next((o for o in self.overlays if o.geometry().contains(point)), self.overlays[0] if self.overlays else None)
        if current:
            r = current.local_selection()
            preferred = current.mapToGlobal(QPoint(round(r.right()+14), round(r.top())))
            self.toolbar.place(preferred)
            self.toolbar.show(); self.toolbar.raise_()
            current.activateWindow(); current.setFocus()
        self.refresh()

    def paint_overlay(self, overlay, painter):
        painter.save()
        r = overlay.local_selection()
        painter.setClipRect(r)
        painter.translate(r.topLeft())
        painter.scale(1 / overlay.sx, 1 / overlay.sy)
        self.engine.paint_document(painter)
        painter.restore()
        painter.setPen(QPen(QColor("#e0e5e9"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(r)

    def route_mouse(self, overlay, event, kind):
        if self.busy: return
        point = physical_point(event, overlay)
        # A Qt mouse grab continues delivering physical coordinates across screens.
        image_point = QPointF(point - self.rect.topLeft())
        if kind == "press" and self.engine.tool == "text" and event.button() == Qt.MouseButton.LeftButton:
            self.start_text(image_point); return
        if self.text_draft is not None: return
        if kind == "double" and self.engine.tool == "select":
            layer = self.engine.hit_test(image_point)
            if layer and layer.tool == "text": self.start_text(QPointF(*layer.points[0]), layer); return
        local = image_point * self.engine.zoom + self.engine.offset
        forwarded = QMouseEvent(event.type(), local, event.globalPosition(), event.button(), event.buttons(), event.modifiers())
        handler = {"press": self.engine.mousePressEvent, "move": self.engine.mouseMoveEvent,
                   "release": self.engine.mouseReleaseEvent, "double": self.engine.mouseDoubleClickEvent}[kind]
        handler(forwarded)

    def choose_tool(self, name):
        if self.busy: return
        self.commit_text()
        if self.toolbar and name == "text":
            self.toolbar.settings_open = True
        self.engine.set_tool(name)
        for overlay in self.overlays: overlay.setCursor(self.engine.cursor())
        if self.toolbar:
            for tool, button in self.toolbar.buttons.items(): button.setChecked(tool == name)
        self.selection_changed(None)

    def selection_changed(self, layer):
        if not self.toolbar: return
        tool = layer.tool if layer else self.engine.tool
        color = layer.color if layer else self.engine.color
        self.toolbar.color.setIcon(icon("color", color))
        self.toolbar.hex_color.setText(color)
        self.toolbar.text_area.setVisible(tool == "text")
        for widget in (self.toolbar.color,self.toolbar.swatches,self.toolbar.hex_color): widget.setVisible(tool not in PRIVACY_TOOLS)
        self.toolbar.active_tool.setText(TOOLS[tool][0])
        self.syncing = True
        self.toolbar.stroke.setValue(round(layer.width if layer else self.engine.stroke))
        self.toolbar.font.setValue(layer.font_size if layer else self.engine.font_size)
        self.toolbar.blur.setValue(layer.strength if layer else self.engine.strength)
        self.toolbar.opacity.setValue(round((layer.opacity if layer else self.engine.opacity) * 100))
        self.syncing = False
        self.toolbar.stroke.setEnabled(tool in ("pen", "arrow", "line", "rect", "ellipse", "highlight"))
        self.toolbar.font.setEnabled(tool in ("text", "number"))
        self.toolbar.blur.setEnabled(tool in ("blur", "pixel"))
        self.toolbar.opacity.setEnabled(tool not in PRIVACY_TOOLS)
        for name,control in [("width",self.toolbar.stroke),("font_size",self.toolbar.font),("strength",self.toolbar.blur),("opacity",self.toolbar.opacity)]:
            for widget in self.toolbar.property_widgets[name]: widget.setVisible(control.isEnabled())
        has_settings = tool not in ("select", "eraser", "redact")
        self.toolbar.settings_button.setEnabled(has_settings)
        self.toolbar.settings_button.setChecked(self.toolbar.settings_open and has_settings)
        self.toolbar.properties.setVisible(self.toolbar.settings_open and has_settings)
        QTimer.singleShot(0, self.reposition_toolbar)

    def reposition_toolbar(self):
        if not self.closed and self.toolbar and self.toolbar.isVisible():
            self.toolbar.place(self.toolbar.pos())

    def change_property(self, name, value):
        if self.syncing: return
        value = value / 100 if name == "opacity" else value
        setattr(self.engine, "stroke" if name == "width" else name, value)
        layer = self.engine.selected()
        if layer:
            before = deepcopy(self.doc.layers); setattr(layer, name, value); self.doc.commit(before)
        if self.text_draft is not None and name in ("font_size","opacity"):
            setattr(self.text_draft,name,value);self.engine.update()

    def set_color(self, value):
        color = QColor(value)
        if not color.isValid(): return
        self.engine.color = color.name()
        layer = self.engine.selected()
        if layer:
            before=deepcopy(self.doc.layers);layer.color=color.name();self.doc.commit(before)
        if self.text_draft is not None:self.text_draft.color=color.name();self.engine.update()
        self.selection_changed(layer)

    def pick_color(self):
        self.toolbar.hex_color.setFocus();self.toolbar.hex_color.selectAll()

    def start_text(self, point, layer=None):
        self.commit_text()
        self.choose_tool("text")
        self.text_layer_id=layer.id if layer else None
        self.text_draft=deepcopy(layer) if layer else Annotation("text",[(point.x(),point.y())],color=self.engine.color,font_size=self.engine.font_size,opacity=self.engine.opacity)
        if layer:self.engine.renderer.request(self.doc.image,[item for item in self.doc.layers if item.id!=layer.id])
        self.engine.draft=self.text_draft
        self.toolbar.text_edit.blockSignals(True);self.toolbar.text_edit.setPlainText(layer.text if layer else "");self.toolbar.text_edit.blockSignals(False)
        self.toolbar.text_edit.setFocus();self.toolbar.status.setText("Metni yazın; görüntü üzerinde canlı görünür.")

    def update_text(self):
        if self.text_draft is not None:
            self.text_draft.text=self.toolbar.text_edit.toPlainText();self.engine.update()

    def commit_text(self):
        if self.text_draft is None:return
        draft=self.text_draft; ident=self.text_layer_id
        self.text_draft=None;self.text_layer_id=None;self.engine.draft=None
        if draft.text.strip():
            layer=self.doc.layer(ident) if ident else None
            if layer:
                before=deepcopy(self.doc.layers);layer.text=draft.text;layer.color=draft.color;layer.font_size=draft.font_size;layer.opacity=draft.opacity;self.doc.commit(before)
            else:self.doc.add(draft)
        else:self.engine.document_changed()
        self.engine.update()

    def adjust_selection(self):
        if self.busy:return
        self.commit_text()
        self.editing = False
        self.engine.draft = self.engine.preview = None
        self.engine.select(None)
        self.toolbar.hide()
        for overlay in self.overlays: overlay.setCursor(Qt.CursorShape.CrossCursor)
        self.update()

    def refresh(self):
        if self.toolbar and self.doc:
            self.toolbar.undo.setEnabled(bool(self.doc.undo_states))
            self.toolbar.redo.setEnabled(bool(self.doc.redo_states))
        self.update()

    def doc_undo(self):
        if self.busy:return
        self.commit_text()
        if self.doc:
            self.doc.undo(); self.selection_changed(self.engine.selected())

    def doc_redo(self):
        if self.busy:return
        self.commit_text()
        if self.doc:
            self.doc.redo(); self.selection_changed(self.engine.selected())

    def key_press(self, event):
        key, mods = event.key(), event.modifiers()
        if self.busy:
            if key==Qt.Key.Key_Escape:self.cancel()
            return
        if mods & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_C: self.copy()
            elif key == Qt.Key.Key_S: self.save()
            elif key == Qt.Key.Key_Z:
                self.doc_redo() if mods & Qt.KeyboardModifier.ShiftModifier else self.doc_undo()
            elif key == Qt.Key.Key_Y: self.doc_redo()
            return
        if key == Qt.Key.Key_Escape:
            if self.text_draft is not None:
                self.text_draft=None;self.text_layer_id=None;self.engine.draft=None;self.engine.document_changed()
            elif self.engine.drag or self.engine.selected(): self.engine.keyPressEvent(event)
            else: self.cancel()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter): self.copy()
        elif key == Qt.Key.Key_Space: return
        else:
            tool = next((tool for tool, (_, shortcut) in TOOLS.items() if event.text().upper() == shortcut and tool != "pan"), None)
            if tool: self.choose_tool(tool)
            else: self.engine.keyPressEvent(event)

    def copy(self):
        self.start_export("copy")

    def save(self):
        if not self.doc or self.closed or self.busy:return
        if self.file_dialog is not None:self.file_dialog.raise_();self.file_dialog.activateWindow();return
        self.commit_text()
        prefs=self.store.value
        dialog=QFileDialog(self.toolbar,"Görüntüyü kaydet",prefs.save_dir)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog,True)
        dialog.setWindowFlags(dialog.windowFlags()|Qt.WindowType.WindowStaysOnTopHint)
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setNameFilters(["PNG (*.png)","JPEG (*.jpg *.jpeg)","WebP (*.webp)"])
        dialog.selectNameFilter({"PNG":"PNG (*.png)","JPG":"JPEG (*.jpg *.jpeg)","WEBP":"WebP (*.webp)"}[prefs.image_format])
        dialog.setDefaultSuffix(prefs.image_format.lower())
        dialog.selectFile(f"BlexShot_{datetime.now():%Y-%m-%d_%H-%M-%S_%f}.{prefs.image_format.lower()}")
        dialog.accepted.connect(self.save_dialog_accepted)
        dialog.rejected.connect(self.save_dialog_rejected)
        self.file_dialog=dialog;dialog.open();dialog.raise_();dialog.activateWindow()

    def save_dialog_rejected(self):
        dialog=self.file_dialog;self.file_dialog=None
        if dialog:dialog.deleteLater()

    def save_dialog_accepted(self):
        dialog=self.file_dialog
        if not dialog:return
        paths=dialog.selectedFiles();selected=dialog.selectedNameFilter()
        self.file_dialog=None;dialog.deleteLater()
        if not paths:return
        fmt="JPG" if selected.startswith("JPEG") else "WEBP" if selected.startswith("WebP") else "PNG"
        target=Path(paths[0]);valid={"PNG":(".png",),"JPG":(".jpg",".jpeg"),"WEBP":(".webp",)}
        if target.suffix.lower() not in valid[fmt]:
            corrected=target.with_suffix(valid[fmt][0])
            if corrected.exists():self.show_error("Bu adla bir dosya var. Farklı bir dosya adı seçin.");return
            target=corrected
        self.start_export(str(target),fmt)

    def start_export(self,destination,fmt="PNG"):
        if not self.doc or self.closed or self.busy:return
        self.commit_text();self.busy=True
        self.toolbar.set_busy(True,"Görüntü işleniyor…")
        prefs=self.store.value
        self.export_job=ExportTask(self.doc.image,self.doc.layers,destination,fmt,prefs.quality,prefs.webp_lossless)
        self.export_job.signals.done.connect(self.export_done)
        QThreadPool.globalInstance().start(self.export_job)

    def export_done(self,image,destination,error):
        if self.closed:return
        self.busy=False
        if error:self.toolbar.set_busy(False,"İşlem tamamlanamadı. Tekrar deneyebilirsiniz.");self.show_error(error);return
        if destination=="copy":QApplication.clipboard().setImage(image)
        else:
            try:
                fmt=Path(destination).suffix.lstrip(".").upper()
                self.store.save(replace(self.store.value,save_dir=str(Path(destination).parent),image_format="JPG" if fmt=="JPEG" else fmt))
            except OSError as exc:self.show_error(f"Görüntü kaydedildi; tercih saklanamadı: {exc}")
        self.complete(destination)

    def complete(self, destination):
        snapshot = {"image": self.doc.image.copy(), "layers": deepcopy(self.doc.layers), "destination": destination}
        self.close()
        self.completed.emit(snapshot)

    def show_error(self, message):
        if self.toolbar:
            self.toolbar.status.setText(message)
            self.toolbar.status.setToolTip(message)

    def close(self):
        if self.closed:return
        if self.file_dialog:
            self.file_dialog.reject();self.file_dialog=None
        self.engine.preview_timer.stop()
        self.engine.renderer.invalidate();self.engine.preview_renderer.invalidate()
        engine=self.engine
        engine.hide();engine.setParent(None)
        if self.toolbar:self.toolbar.hide();self.toolbar.deleteLater()
        super().close()
        # Hide immediately. Reclaim worker resources only after running kernels finish.
        timer=QTimer(engine);timer.setInterval(40)
        def release():
            if engine.renderer.pool.activeThreadCount()==0 and engine.preview_renderer.pool.activeThreadCount()==0:
                timer.stop();engine.shutdown();engine.deleteLater()
        timer.timeout.connect(release);timer.start()
