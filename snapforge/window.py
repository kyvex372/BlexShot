from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QImage, QImageReader, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QButtonGroup, QColorDialog, QComboBox, QDialog, QFileDialog,
                              QFrame, QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                              QMainWindow, QMenu, QMessageBox, QPushButton, QScrollArea, QSlider, QSpinBox,
                              QSplitter, QStackedWidget, QVBoxLayout, QWidget)

from .canvas import Canvas
from .dialogs import ExportPreview
from .document import Document, TOOLS, PRIVACY_TOOLS
from .icons import icon
from .imaging import render, save_image
from .platform import resource_path
from .widgets import FloatingTools, ToolButton


def label(text, name=None):
    result = QLabel(text)
    if name:
        result.setObjectName(name)
    return result


class MainWindow(QMainWindow):
    capture_requested = Signal(str)
    settings_requested = Signal()
    quit_requested = Signal()
    notify = Signal(str)

    def __init__(self, store):
        super().__init__()
        self.store = store
        self.doc = None
        self.force_close = False
        self.syncing = False
        self.setWindowTitle("BlexShot")
        self.resize(1320, 860)
        self.setMinimumSize(960, 680)
        self.setWindowIcon(QPixmap(str(resource_path("app.png"))))
        self.shortcuts = []
        self.tool_buttons = {}
        self._build()
        self._shortcuts()
        self.apply_preferences()

    def _build(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = QFrame(); header.setObjectName("header")
        row = QHBoxLayout(header); row.setContentsMargins(24, 15, 24, 15); row.setSpacing(12)
        mark = QLabel(); mark.setPixmap(QPixmap(str(resource_path("app.png"))).scaled(36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        row.addWidget(mark)
        wordmark = label("BlexShot", None); wordmark.setStyleSheet("font-size: 21px; font-weight: 700;")
        row.addWidget(wordmark)
        badge = label("PRO"); badge.setStyleSheet("color: #d1dbe2; background: #303b43; border-radius: 4px; padding: 3px 6px; font-size: 10px; font-weight: 700;")
        row.addWidget(badge)
        row.addSpacing(20)
        self.doc_name = label("Çalışma alanı", "muted"); row.addWidget(self.doc_name)
        row.addStretch()
        new = QPushButton("Yeni yakalama")
        new.setIcon(icon("capture")); new.setObjectName("primary")
        new.setProperty("icon_name", "capture")
        new.clicked.connect(lambda: self.capture_requested.emit("region"))
        menu = QMenu(self)
        menu.addAction("Alan seç", lambda: self.capture_requested.emit("region"))
        menu.addAction("Tüm ekranlar", lambda: self.capture_requested.emit("full"))
        menu.addAction("Aktif pencere · 3 sn", lambda: self.capture_requested.emit("window-delay"))
        dropdown = ToolButton("down", "Diğer yakalama seçenekleri")
        dropdown.setMenu(menu); dropdown.setPopupMode(ToolButton.ToolButtonPopupMode.InstantPopup)
        row.addWidget(new); row.addWidget(dropdown)
        row.addWidget(ToolButton("folder", "Görüntü aç · Ctrl+O", self.open_image))
        row.addWidget(ToolButton("settings", "Ayarlar", self.settings_requested.emit))
        layout.addWidget(header)
        self.pages = QStackedWidget()
        self.pages.addWidget(self._welcome())
        self.pages.addWidget(self._editor())
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)
        self.statusBar().setSizeGripEnabled(True)
        self.statusBar().showMessage("Hazır")
        self.key_status = label("Print Screen  ·  Yakala", "muted")
        self.statusBar().addPermanentWidget(self.key_status)
        self.floating = FloatingTools(self)
        for name in ("pen", "arrow", "line", "rect", "ellipse", "text", "blur", "pixel"):
            button = ToolButton(name, TOOLS[name][0], lambda checked=False, t=name: self.choose_tool(t), checkable=True)
            self.floating.layout.addWidget(button)
            self.tool_buttons.setdefault(name, []).append(button)
        self.float_color = ToolButton("color", "Çizim rengi", self.pick_color)
        self.floating.layout.addWidget(self.float_color)
        self.float_undo = ToolButton("undo", "Geri al · Ctrl+Z", self.undo)
        self.floating.layout.addWidget(self.float_undo)
        self.floating.layout.addWidget(ToolButton("copy", "Kopyala · Ctrl+C", self.copy_image))
        self.floating.layout.addWidget(ToolButton("save", "Kaydet · Ctrl+S", self.save))
        self.choose_tool("arrow")

    def _welcome(self):
        page = QWidget()
        layout = QVBoxLayout(page); layout.setContentsMargins(64, 38, 64, 32); layout.setSpacing(16)
        layout.addStretch(1)
        layout.addWidget(label("YAKALA. ANLAT. PAYLAŞ.", "eyebrow"))
        title = label("Bir ekran görüntüsünden\ndaha fazlası.", "title")
        title.setStyleSheet("font-size: 44px; font-weight: 700;")
        layout.addWidget(title)
        description = label("Önemli noktaları işaretleyin, özel bilgileri gizleyin.\nFikrinizi tek bir görüntüyle anlatın.", "muted")
        description.setStyleSheet("font-size: 16px;")
        layout.addWidget(description)
        layout.addSpacing(20)
        cards = QHBoxLayout(); cards.setSpacing(16)
        for name, title, description, key, mode in [
            ("capture", "Alan seç", "Tam ihtiyacınız olan bölge.", "Print Screen", "region"),
            ("screen", "Tüm ekranlar", "Çalışma alanınızın bütünü.", "Ctrl + Print Screen", "full"),
            ("window", "Aktif pencere", "3 saniye içinde pencereye geçin.", "Alt + Print Screen", "window-delay"),
        ]:
            card = QFrame(); card.setObjectName("card")
            column = QVBoxLayout(card); column.setContentsMargins(22, 24, 22, 22); column.setSpacing(12)
            pic = QLabel(); pic.setPixmap(icon(name, "#d2dce3", 32).pixmap(32, 32)); column.addWidget(pic)
            heading = label(title); heading.setStyleSheet("font-size: 18px; font-weight: 600;"); column.addWidget(heading)
            desc = label(description, "muted"); desc.setWordWrap(True); column.addWidget(desc)
            column.addSpacing(12)
            button = QPushButton("Yakalamayı başlat")
            button.clicked.connect(lambda checked=False, m=mode: self.capture_requested.emit(m))
            column.addWidget(button)
            shortcut = label(key, "muted"); shortcut.setStyleSheet("font-size: 11px;"); column.addWidget(shortcut)
            cards.addWidget(card, 1)
        layout.addLayout(cards)
        layout.addSpacing(14)
        bottom = QHBoxLayout()
        bottom.addWidget(label("Zaten bir görüntünüz var mı?", "muted"))
        open_button = QPushButton("Dosyadan aç  ↗"); open_button.clicked.connect(self.open_image)
        bottom.addWidget(open_button); bottom.addStretch()
        layout.addLayout(bottom)
        layout.addStretch(2)
        layout.addWidget(label("YEREL VE ÖZEL     Görüntüleriniz bu bilgisayarda kalır.", "muted"))
        return page

    def _editor(self):
        page = QWidget()
        outer = QVBoxLayout(page); outer.setContentsMargins(16, 14, 16, 8); outer.setSpacing(12)
        top = QHBoxLayout()
        self.dimensions = label("", "section"); top.addWidget(self.dimensions)
        top.addStretch()
        self.undo_button = ToolButton("undo", "Geri al · Ctrl+Z", self.undo)
        self.redo_button = ToolButton("redo", "Yeniden yap · Ctrl+Y", self.redo)
        top.addWidget(self.undo_button); top.addWidget(self.redo_button)
        float_button = QPushButton("Yüzen araçlar"); float_button.clicked.connect(self.toggle_floating)
        top.addWidget(float_button)
        copy = QPushButton("Kopyala"); copy.setIcon(icon("copy")); copy.clicked.connect(self.copy_image)
        save = QPushButton("Kaydet…"); save.setIcon(icon("save")); save.setObjectName("primary"); save.clicked.connect(self.save)
        copy.setProperty("icon_name", "copy"); save.setProperty("icon_name", "save")
        top.addWidget(copy); top.addWidget(save); outer.addLayout(top)
        body = QHBoxLayout(); body.setSpacing(12)
        rail = QFrame(); rail.setObjectName("panel"); rail.setFixedWidth(70)
        rail_layout = QVBoxLayout(rail); rail_layout.setContentsMargins(10, 10, 10, 10); rail_layout.setSpacing(4)
        tool_scroll = QScrollArea(); tool_scroll.setWidgetResizable(True); tool_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tool_body = QWidget(); tools_layout = QVBoxLayout(tool_body); tools_layout.setContentsMargins(0, 0, 0, 0); tools_layout.setSpacing(5)
        for name, (title, key) in TOOLS.items():
            button = ToolButton(name, f"{title} · {key}", lambda checked=False, t=name: self.choose_tool(t), checkable=True)
            self.tool_buttons.setdefault(name, []).append(button)
            tools_layout.addWidget(button)
        tools_layout.addStretch()
        tool_scroll.setWidget(tool_body); rail_layout.addWidget(tool_scroll)
        body.addWidget(rail)
        self.canvas = Canvas()
        self.canvas.selection_changed.connect(self.selection_changed)
        self.canvas.zoom_changed.connect(self.zoom_changed)
        self.canvas.error.connect(self.show_error)
        body.addWidget(self.canvas, 1)
        inspector = QFrame(); inspector.setObjectName("panel"); inspector.setFixedWidth(264)
        inspector_layout = QVBoxLayout(inspector); inspector_layout.setContentsMargins(0, 0, 0, 0)
        inspector_scroll = QScrollArea(); inspector_scroll.setWidgetResizable(True)
        inspector_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inspector_content = QWidget(); inspector_content.setMinimumHeight(610)
        panel = QVBoxLayout(inspector_content); panel.setContentsMargins(18, 16, 18, 12); panel.setSpacing(8)
        inspector_scroll.setWidget(inspector_content); inspector_layout.addWidget(inspector_scroll)
        panel.addWidget(label("ARAÇ ÖZELLİKLERİ", "section"))
        self.tool_title = label("Ok"); self.tool_title.setStyleSheet("font-size: 21px; font-weight: 600;"); panel.addWidget(self.tool_title)
        color_row = QHBoxLayout(); color_row.addWidget(label("Renk")); color_row.addStretch()
        self.color_button = QPushButton("#f59e0b"); self.color_button.clicked.connect(self.pick_color); color_row.addWidget(self.color_button)
        panel.addLayout(color_row)
        swatches = QHBoxLayout(); swatches.setSpacing(5)
        for color in ("#f59e0b", "#54c7ec", "#f87171", "#fbbf24", "#34d399", "#ffffff"):
            button = QPushButton(); button.setFixedSize(28, 26); button.setToolTip(color); button.setAccessibleName(f"Renk {color}")
            button.setStyleSheet(f"background: {color}; border: 2px solid #42465a; border-radius: 7px;")
            button.clicked.connect(lambda checked=False, c=color: self.set_color(c)); swatches.addWidget(button)
        panel.addLayout(swatches)
        self.stroke_spin = self._spin(panel, "Çizgi kalınlığı", 1, 160, 4, " px", "width")
        self.opacity_spin = self._spin(panel, "Opaklık", 5, 100, 100, " %", "opacity")
        self.font_spin = self._spin(panel, "Yazı boyutu", 10, 180, 28, " px", "font_size")
        self.blur_spin = self._spin(panel, "Blur yoğunluğu", 1, 80, 18, "", "strength")
        self.hint = label("İki nokta arasında sürükleyin.", "muted"); self.hint.setWordWrap(True); self.hint.setMaximumHeight(64); panel.addWidget(self.hint)
        panel.addSpacing(8); panel.addWidget(label("KATMANLAR", "section"))
        self.layers = QListWidget(); self.layers.setMinimumHeight(100); self.layers.setMaximumHeight(144)
        self.layers.itemClicked.connect(self.layer_clicked); self.layers.itemChanged.connect(self.layer_visibility)
        panel.addWidget(self.layers, 1)
        layer_actions = QHBoxLayout()
        self.up_button = ToolButton("up", "Katmanı öne getir", lambda: self.reorder(1))
        self.down_button = ToolButton("down", "Katmanı arkaya gönder", lambda: self.reorder(-1))
        self.delete_button = ToolButton("trash", "Seçili nesneyi sil", self.delete_selected)
        layer_actions.addWidget(self.up_button); layer_actions.addWidget(self.down_button); layer_actions.addStretch(); layer_actions.addWidget(self.delete_button)
        panel.addLayout(layer_actions)
        body.addWidget(inspector); outer.addLayout(body, 1)
        footer = QHBoxLayout()
        footer.addWidget(label("Tekerlek: yakınlaştır   ·   Space + sürükle: kaydır   ·   V: seç", "muted")); footer.addStretch()
        minus = QPushButton("−"); minus.setFixedWidth(36); minus.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.zoom / 1.2))
        plus = QPushButton("+"); plus.setFixedWidth(36); plus.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.zoom * 1.2))
        self.zoom_label = label("100%"); self.zoom_label.setMinimumWidth(46); self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fit = QPushButton("Sığdır"); fit.clicked.connect(self.canvas.fit)
        actual = QPushButton("1:1"); actual.clicked.connect(lambda: self.canvas.set_zoom(1))
        for w in (minus, self.zoom_label, plus, actual, fit): footer.addWidget(w)
        outer.addLayout(footer)
        return page

    def _spin(self, panel, title, low, high, value, suffix, prop):
        row = QHBoxLayout(); row.addWidget(label(title)); row.addStretch()
        spin = QSpinBox(); spin.setRange(low, high); spin.setValue(value); spin.setSuffix(suffix); spin.setFixedWidth(84)
        spin.setAccessibleName(title)
        spin.setKeyboardTracking(False); spin.valueChanged.connect(lambda v: self.change_property(prop, v))
        row.addWidget(spin); panel.addLayout(row)
        return spin

    def _shortcuts(self):
        for key, callback in [("Ctrl+O", self.open_image), ("Ctrl+S", self.save), ("Ctrl+C", self.copy_image),
                              ("Ctrl+Z", self.undo), ("Ctrl+Y", self.redo), ("Ctrl+Shift+Z", self.redo),
                              ("Ctrl+N", lambda: self.capture_requested.emit("region")),
                              ("Ctrl+0", self.canvas.fit), ("Ctrl+1", lambda: self.canvas.set_zoom(1)),
                              ("Ctrl+Q", self.quit_requested.emit)]:
            shortcut = QShortcut(QKeySequence(key), self); shortcut.activated.connect(callback); self.shortcuts.append(shortcut)
        for tool, (_, key) in TOOLS.items():
            shortcut = QShortcut(QKeySequence(key), self.canvas)
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(lambda t=tool: self.choose_tool(t)); self.shortcuts.append(shortcut)

    def apply_preferences(self):
        prefs = self.store.value
        self.syncing = True
        self.canvas.color, self.canvas.stroke, self.canvas.strength = prefs.color, prefs.stroke, prefs.blur
        self.color_button.setText(prefs.color)
        self.stroke_spin.setValue(prefs.stroke); self.blur_spin.setValue(prefs.blur)
        self.syncing = False
        if self.canvas.selected(): self.selection_changed(self.canvas.selected())
        self.key_status.setText(f"{prefs.capture_key}  ·  Yakala")
        for button in self.findChildren(ToolButton):
            button.animate = prefs.animations

    def choose_tool(self, name):
        if not hasattr(self, "canvas"):
            return
        self.canvas.set_tool(name)
        self.syncing = True
        self.color_button.setText(self.canvas.color)
        self.stroke_spin.setValue(round(self.canvas.stroke))
        self.opacity_spin.setValue(round(self.canvas.opacity * 100))
        self.font_spin.setValue(self.canvas.font_size)
        self.blur_spin.setValue(self.canvas.strength)
        self.syncing = False
        self.tool_title.setText(TOOLS[name][0])
        for key, buttons in self.tool_buttons.items():
            for button in buttons: button.setChecked(key == name)
        hints = {"select": "Nesneyi taşıyın. Köşelerden boyutlandırın. Metni çift tıklayarak düzenleyin.",
                 "blur": "Gizlenecek alanı sürükleyin. Köşeleri V ile yeniden boyutlandırın.",
                 "pixel": "Alan seçin. Yoğunluk piksel bloklarının boyutunu belirler.",
                 "redact": "Seçili alan tamamen siyahla kapatılır.", "eraser": "Üzerinden geçtiğiniz çizim nesnesini siler.",
                 "text": "Metin eklemek için görüntüye tıklayın.", "number": "Ardışık numaralar eklemek için tıklayın.",
                 "pan": "Görüntüyü sürükleyerek kaydırın."}
        self.hint.setText(hints.get(name, "Çizmek için görüntü üzerinde sürükleyin."))
        self.canvas.setFocus()
        self.update_property_enabled(name)

    def update_property_enabled(self, tool):
        self.opacity_spin.setEnabled(tool not in PRIVACY_TOOLS)
        self.blur_spin.setEnabled(tool in ("blur", "pixel"))
        self.font_spin.setEnabled(tool in ("text", "number"))
        self.stroke_spin.setEnabled(tool in ("pen", "highlight", "arrow", "line", "rect", "ellipse"))

    def set_document(self, image, name="Yeni yakalama", point=None, show_window=True):
        if self.doc:
            self.doc.changed.disconnect(self.refresh_document)
            self.doc.deleteLater()
        self.doc = Document(image, self)
        self.doc.changed.connect(self.refresh_document)
        self.canvas.set_document(self.doc)
        self.pages.setCurrentIndex(1)
        self.doc_name.setText(name)
        self.dimensions.setText(f"{image.width():,} × {image.height():,} PX   ·   YEREL GÖRÜNTÜ")
        self.refresh_document()
        if show_window:
            self.showNormal(); self.raise_(); self.activateWindow()
        QTimer.singleShot(0, self.canvas.fit)
        if point and show_window:
            self.floating.place(point + QPoint(12, 20)); self.floating.show()
        if show_window: self.canvas.setFocus()

    def refresh_document(self):
        if not self.doc:
            return
        self.setWindowTitle(f"{'● ' if self.doc.dirty else ''}BlexShot — {self.doc.image.width()} × {self.doc.image.height()}")
        self.undo_button.setEnabled(bool(self.doc.undo_states)); self.float_undo.setEnabled(bool(self.doc.undo_states))
        self.redo_button.setEnabled(bool(self.doc.redo_states))
        self.syncing = True
        self.layers.clear()
        for i, layer in reversed(list(enumerate(self.doc.layers))):
            item = QListWidgetItem(icon(layer.tool), f"{TOOLS[layer.tool][0]}  {i + 1:02}")
            item.setData(Qt.ItemDataRole.UserRole, layer.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if layer.visible else Qt.CheckState.Unchecked)
            self.layers.addItem(item)
            if layer.id == self.canvas.selected_id: self.layers.setCurrentItem(item)
        if not self.doc.layers:
            item = QListWidgetItem("Henüz çizim yok"); item.setFlags(Qt.ItemFlag.NoItemFlags); self.layers.addItem(item)
        self.syncing = False
        selected = self.canvas.selected()
        for button in (self.delete_button, self.up_button, self.down_button): button.setEnabled(selected is not None)

    def selection_changed(self, layer):
        if layer:
            self.syncing = True
            self.color_button.setText(layer.color)
            self.stroke_spin.setValue(round(layer.width)); self.opacity_spin.setValue(round(layer.opacity * 100))
            self.font_spin.setValue(layer.font_size); self.blur_spin.setValue(layer.strength)
            self.tool_title.setText(TOOLS[layer.tool][0])
            self.syncing = False
            self.update_property_enabled(layer.tool)
        self.refresh_document()

    def layer_clicked(self, item):
        layer = self.doc.layer(item.data(Qt.ItemDataRole.UserRole))
        self.choose_tool("select"); self.canvas.select(layer)

    def layer_visibility(self, item):
        if not self.syncing and self.doc:
            layer = self.doc.layer(item.data(Qt.ItemDataRole.UserRole))
            if layer:
                before = deepcopy(self.doc.layers)
                layer.visible = item.checkState() == Qt.CheckState.Checked
                self.doc.commit(before)

    def change_property(self, name, value):
        if self.syncing:
            return
        value = value / 100 if name == "opacity" else value
        setattr(self.canvas, "stroke" if name == "width" else name, value)
        layer = self.canvas.selected()
        if layer:
            before = deepcopy(self.doc.layers)
            setattr(layer, name, value)
            self.doc.commit(before)

    def set_color(self, value):
        self.canvas.color = value
        self.color_button.setText(value)
        self.float_color.setIcon(icon("color", value))
        layer = self.canvas.selected()
        if layer:
            before = deepcopy(self.doc.layers); layer.color = value; self.doc.commit(before)

    def pick_color(self):
        color = QColorDialog.getColor(QColor(self.canvas.selected().color if self.canvas.selected() else self.canvas.color), self, "Çizim rengi")
        if color.isValid(): self.set_color(color.name())

    def reorder(self, step):
        layer = self.canvas.selected()
        if layer:
            before = deepcopy(self.doc.layers)
            i = self.doc.layers.index(layer); j = max(0, min(len(self.doc.layers) - 1, i + step))
            self.doc.layers[i], self.doc.layers[j] = self.doc.layers[j], self.doc.layers[i]
            self.doc.commit(before)

    def delete_selected(self):
        if self.doc and self.canvas.selected(): self.doc.remove(self.canvas.selected_id)

    def undo(self):
        if self.doc:
            self.doc.undo()
            if self.canvas.selected(): self.selection_changed(self.canvas.selected())

    def redo(self):
        if self.doc:
            self.doc.redo()
            if self.canvas.selected(): self.selection_changed(self.canvas.selected())

    def zoom_changed(self, value):
        self.zoom_label.setText(f"{value * 100:.0f}%")

    def toggle_floating(self):
        if self.floating.isVisible(): self.floating.hide()
        else:
            self.floating.place(self.canvas.mapToGlobal(QPoint(20, 20))); self.floating.show()

    def can_replace(self):
        if not self.doc or not self.doc.dirty:
            return True
        answer = QMessageBox.question(self, "Kaydedilmemiş görüntü", "Bu görüntüyü değiştirmeden önce kaydetmek ister misiniz?",
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                      QMessageBox.StandardButton.Save)
        return self.save() if answer == QMessageBox.StandardButton.Save else answer == QMessageBox.StandardButton.Discard

    def open_image(self):
        if not self.can_replace(): return
        name, _ = QFileDialog.getOpenFileName(self, "Görüntü aç", self.store.value.save_dir, "Görüntüler (*.png *.jpg *.jpeg *.webp *.bmp)")
        if name:
            reader = QImageReader(name); reader.setAutoTransform(True)
            image = reader.read()
            if image.isNull(): self.show_error(f"Görüntü açılamadı: {reader.errorString()}")
            else: self.set_document(image, Path(name).name)

    def copy_image(self):
        if not self.doc: return
        try:
            QApplication.clipboard().setImage(render(self.doc.image, self.doc.layers))
            self.statusBar().showMessage("Görüntü panoya kopyalandı. Ctrl+V ile yapıştırın.", 5000)
            self.notify.emit("Düzenlenen görüntü panoya kopyalandı.")
        except Exception as exc: self.show_error(f"Panoya kopyalanamadı: {exc}")

    def save(self):
        if not self.doc: return False
        self.floating.hide()
        try:
            image = render(self.doc.image, self.doc.layers)
            if ExportPreview(image, self).exec() != QDialog.DialogCode.Accepted: return False
            extension = self.store.value.image_format.lower()
            filename = f"BlexShot_{datetime.now():%Y-%m-%d_%H-%M-%S_%f}.{extension}"
            filters = {"PNG": "PNG (*.png)", "JPG": "JPEG (*.jpg *.jpeg)", "WEBP": "WebP (*.webp)"}
            path, selected = QFileDialog.getSaveFileName(self, "Görüntüyü kaydet", str(Path(self.store.value.save_dir) / filename),
                                                        ";;".join(filters.values()), filters[self.store.value.image_format])
            if not path: return False
            fmt = next(k for k, v in filters.items() if v == selected)
            target = Path(path)
            valid = {"PNG": (".png",), "JPG": (".jpg", ".jpeg"), "WEBP": (".webp",)}
            if target.suffix.lower() not in valid[fmt]:
                target = target.with_suffix(valid[fmt][0])
                if target.exists() and QMessageBox.question(self, "Dosya mevcut", f"{target.name} üzerine yazılsın mı?") != QMessageBox.StandardButton.Yes:
                    return False
            save_image(image, target, fmt, quality=self.store.value.quality, webp_lossless=self.store.value.webp_lossless)
            self.doc.mark_saved()
            try:
                self.store.save(replace(self.store.value, save_dir=str(target.parent), image_format=fmt))
            except OSError as exc:
                self.show_error(f"Görüntü kaydedildi; klasör tercihi saklanamadı: {exc}")
            self.doc_name.setText(target.name)
            self.statusBar().showMessage(f"Kaydedildi · {target}", 8000)
            self.notify.emit(f"Görüntü kaydedildi: {target.name}")
            return True
        except Exception as exc:
            self.show_error(f"Görüntü kaydedilemedi: {exc}")
            return False

    def show_error(self, message):
        QMessageBox.warning(self, "BlexShot", message)

    def closeEvent(self, event):
        if self.force_close:
            self.floating.hide(); event.accept(); return
        if self.store.value.tray and QApplication.instance().property("tray_available"):
            self.floating.hide(); self.hide(); event.ignore()
            self.notify.emit("BlexShot tepside çalışıyor. Kısayolunuzla yakalayabilirsiniz.")
        else:
            event.ignore(); self.quit_requested.emit()

    def hideEvent(self, event):
        if hasattr(self, "floating"): self.floating.hide()
        super().hideEvent(event)
