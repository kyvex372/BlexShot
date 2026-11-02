"""Compact, modeless control centre for a tray-first screenshot workflow."""
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QKeySequence, QPixmap
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QFileDialog,
                              QFrame, QGridLayout, QHBoxLayout, QKeySequenceEdit, QLabel, QLineEdit,
                              QListWidget, QListWidgetItem, QPushButton, QScrollArea,
                              QSlider, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from .icons import icon
from .controls import Toggle, ShortcutRecorder, TitleBar, Segmented
from .hotkeys import parse_hotkey
from .platform import resource_path


def text(value, name=None):
    label = QLabel(value)
    if name:
        label.setObjectName(name)
    label.setWordWrap(True)
    return label


class SettingsDialog(QDialog):
    apply_requested = Signal()
    recording_changed = Signal(bool)
    capture_requested = Signal(str)
    editor_requested = Signal()

    def __init__(self, preferences, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BlexShot · Yönetim")
        self.setObjectName("management")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setModal(False)
        self.resize(720, 520)
        self.setMinimumSize(640, 480)
        self.original = preferences; self.loading = True
        outer = QVBoxLayout(self); outer.setContentsMargins(1, 1, 1, 1); outer.setSpacing(0)
        outer.addWidget(TitleBar(self))
        header = QFrame(); header.setObjectName("managementHeader")
        brand = QHBoxLayout(header); brand.setContentsMargins(20, 10, 20, 10); brand.setSpacing(9)
        logo = QLabel(); logo.setFixedSize(28, 28)
        logo.setPixmap(QPixmap(str(resource_path("app.png")))); logo.setScaledContents(True)
        brand.addWidget(logo); brand.addWidget(text("BlexShot", "controlBrand")); brand.addStretch()
        editor = QPushButton("Editör"); editor.setObjectName("quiet"); editor.setIcon(icon("pen"))
        editor.clicked.connect(self.editor_requested.emit); brand.addWidget(editor)
        capture = QPushButton("Yeni yakalama"); capture.setObjectName("primary"); capture.setIcon(icon("capture"))
        capture.clicked.connect(lambda: self.capture_requested.emit("region")); brand.addWidget(capture)
        outer.addWidget(header)
        self.nav = QListWidget(); self.nav.setObjectName("controlNavigation")
        self.nav.setFlow(QListWidget.Flow.LeftToRight); self.nav.setWrapping(False)
        self.nav.setFixedHeight(43); self.nav.setIconSize(QSize(16, 16))
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setProperty("control_navigation", True)
        for title, name in [("Genel", "screen"), ("Kısayollar", "capture"),
                            ("Görüntü ve kayıt", "folder"), ("Düzenleme", "pen")]:
            item = QListWidgetItem(icon(name), title); item.setData(Qt.ItemDataRole.UserRole, name)
            self.nav.addItem(item)
        outer.addWidget(self.nav)
        self.pages = QStackedWidget()
        for page in (self.general_page(), self.shortcuts_page(), self.output_page(), self.editor_page()):
            self.pages.addWidget(page)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex); self.nav.setCurrentRow(0)
        outer.addWidget(self.pages, 1)
        footer = QFrame(); footer.setObjectName("controlFooter")
        actions = QHBoxLayout(footer); actions.setContentsMargins(20, 10, 20, 10); actions.setSpacing(8)
        self.error = text("Hazır.", "muted"); actions.addWidget(self.error, 1)
        hide = QPushButton("Gizle"); hide.setObjectName("quiet"); hide.clicked.connect(self.hide); actions.addWidget(hide)
        self.save_button = QPushButton("Kaydet"); self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self.apply_requested.emit); actions.addWidget(self.save_button)
        outer.addWidget(footer)
        self.load(preferences)
        self._connect_changes()

    def page(self, title, subtitle):
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget(); content.setObjectName("controlContent")
        layout = QVBoxLayout(content); layout.setContentsMargins(20, 16, 20, 16); layout.setSpacing(10)
        heading = text(title); heading.setObjectName("controlTitle")
        heading.setToolTip(subtitle); layout.addWidget(heading)
        scroll.setWidget(content)
        return scroll, layout

    def card(self, layout):
        frame = QFrame(); frame.setObjectName("controlCard")
        content = QVBoxLayout(frame); content.setContentsMargins(14, 12, 14, 12); content.setSpacing(10)
        layout.addWidget(frame)
        return content

    def row(self, layout, title, widget, detail=None):
        row = QHBoxLayout(); row.setSpacing(16)
        labels = QVBoxLayout(); labels.setSpacing(3)
        labels.addWidget(text(title))
        if detail: labels.addWidget(text(detail, "controlFootnote"))
        row.addLayout(labels, 1); row.addWidget(widget)
        widget.setAccessibleName(title)
        layout.addLayout(row)

    def general_page(self):
        page, layout = self.page("Genel", "Yakalama ve uygulama tercihleri.")
        quick = self.card(layout)
        quick.addWidget(text("Hızlı yakalama", "cardTitle"))
        buttons = QHBoxLayout(); buttons.setSpacing(8)
        for title, mode in [("Alan seç", "region"), ("Tüm ekranlar", "full"), ("Aktif pencere", "window-delay")]:
            button = QPushButton(title)
            if mode == "region": button.setObjectName("primary")
            button.clicked.connect(lambda checked=False, m=mode: self.capture_requested.emit(m)); buttons.addWidget(button)
        quick.addLayout(buttons)
        quick.addWidget(text("Sol tık: alan yakala  ·  Sağ tık: işlem menüsü", "controlFootnote"))
        options = self.card(layout)
        self.theme = Segmented(); self.theme.addItem("Gündüz", "light"); self.theme.addItem("Gece", "dark"); self.theme.setMinimumWidth(115)
        self.row(options, "Görünüm", self.theme)
        self.checks = {}
        toggles = QGridLayout(); toggles.setHorizontalSpacing(22); toggles.setVerticalSpacing(4)
        for i,(key,title) in enumerate([("startup","Windows ile başlat"),("tray","Tepside çalış"),
                                       ("notifications","Bildirimler"),("animations","Animasyonlar")]):
            check=Toggle(title); self.checks[key]=check; toggles.addWidget(check,i//2,i%2)
        options.addLayout(toggles)
        layout.addStretch()
        return page

    def shortcuts_page(self):
        page, layout = self.page("Klavye kısayolları", "Bir atamaya tıklayın, ardından kullanmak istediğiniz tuşa basın.")
        card = self.card(layout); self.keys = []
        for title, detail in [("Alan yakalama", "Ekrandan istediğiniz bölgeyi seçin."),
                              ("Tüm ekranlar", "Bağlı monitörlerin tamamını yakalayın."),
                              ("Aktif pencere", "O anda öndeki pencereyi yakalayın.")]:
            edit = ShortcutRecorder(); edit.setFixedWidth(166); edit.setMinimumHeight(32)
            edit.recording_changed.connect(self.recording_changed.emit)
            self.row(card, title, edit, detail); self.keys.append(edit)
        note = text("PgUp/PgDown, Home/End, Insert/Delete, yön tuşları, harfler ve birleşimler desteklenir. Windows tarafından ayrılmış veya kullanımda olan birleşimler kaydedilemez.", "muted")
        layout.addWidget(note); layout.addStretch()
        return page

    def output_page(self):
        page, layout = self.page("Görüntü ve kayıt", "Biçimi, dosya boyutunu ve kayıt konumunu belirleyin.")
        card = self.card(layout)
        self.format = Segmented(); self.format.addItems(["PNG", "JPG", "WEBP"]); self.format.setMinimumWidth(115)
        self.row(card, "Görüntü biçimi", self.format)
        self.lossless = Toggle("WebP için kayıpsız sıkıştırma")
        card.addWidget(self.lossless)
        quality_row = QHBoxLayout(); quality_row.addWidget(text("Kayıt kalitesi")); quality_row.addStretch()
        self.quality_label = text("%98"); self.quality_label.setObjectName("qualityValue"); quality_row.addWidget(self.quality_label)
        card.addLayout(quality_row)
        self.quality = QSlider(Qt.Orientation.Horizontal); self.quality.setRange(1, 100); self.quality.setAccessibleName("Kayıt kalitesi")
        card.addWidget(self.quality)
        range_row = QHBoxLayout(); range_row.addWidget(text("Küçük dosya", "controlFootnote")); range_row.addStretch(); range_row.addWidget(text("Yüksek kalite", "controlFootnote")); card.addLayout(range_row)
        self.quality_hint = text("", "muted"); card.addWidget(self.quality_hint)
        self.format.currentTextChanged.connect(self.update_quality)
        self.lossless.toggled.connect(self.update_quality)
        self.quality.valueChanged.connect(self.update_quality)
        folder = self.card(layout); folder.addWidget(text("KAYIT KLASÖRÜ", "section"))
        folder_row = QHBoxLayout(); folder_row.setSpacing(8)
        self.folder = QLineEdit(); self.folder.setAccessibleName("Kayıt klasörü")
        browse = QPushButton("Seç…"); browse.clicked.connect(self.browse)
        folder_row.addWidget(self.folder, 1); folder_row.addWidget(browse); folder.addLayout(folder_row)
        layout.addStretch()
        return page

    def editor_page(self):
        page, layout = self.page("Düzenleme tercihleri", "Yeni çizimlerde kullanılacak başlangıç değerleri.")
        card = self.card(layout)
        self.color_value = "#f59e0b"
        self.color = QPushButton(); self.color.setMinimumWidth(115); self.color.clicked.connect(self.pick_color)
        self.row(card, "Çizim rengi", self.color)
        self.stroke = QSpinBox(); self.stroke.setRange(1, 40); self.stroke.setSuffix(" px"); self.stroke.setMinimumWidth(115)
        self.row(card, "Kalem kalınlığı", self.stroke)
        self.blur = QSpinBox(); self.blur.setRange(1, 80); self.blur.setMinimumWidth(115)
        self.row(card, "Blur yoğunluğu", self.blur)
        layout.addWidget(text("Seçtiğiniz alanın üzerinde, yüzen araç çubuğuyla anında düzenleyin.", "muted")); layout.addStretch()
        return page

    def load(self, preferences):
        self.loading = True
        self.original = preferences
        self.theme.setCurrentIndex(1 if preferences.theme == "dark" else 0)
        for edit, key in zip(self.keys, (preferences.capture_key, preferences.fullscreen_key, preferences.window_key)):
            edit.setKeySequence(QKeySequence(key))
        self.folder.setText(preferences.save_dir)
        self.format.setCurrentText(preferences.image_format)
        self.quality.setValue(preferences.quality)
        self.lossless.setChecked(preferences.webp_lossless)
        self.color_value = preferences.color; self.color.setText(preferences.color)
        self.stroke.setValue(preferences.stroke); self.blur.setValue(preferences.blur)
        for key, check in self.checks.items(): check.setChecked(getattr(preferences, key))
        self.update_quality()
        self.loading = False
        self.save_button.setEnabled(False)
        self.error.setText("Tercihleriniz güncel.")
        self.error.setStyleSheet("")

    def _connect_changes(self):
        for combo in (self.theme, self.format): combo.currentIndexChanged.connect(self.mark_changed)
        for edit in self.keys: edit.keySequenceChanged.connect(self.mark_changed)
        self.folder.textChanged.connect(self.mark_changed)
        self.quality.valueChanged.connect(self.mark_changed)
        self.lossless.toggled.connect(self.mark_changed)
        self.stroke.valueChanged.connect(self.mark_changed); self.blur.valueChanged.connect(self.mark_changed)
        for check in self.checks.values(): check.toggled.connect(self.mark_changed)

    def mark_changed(self, *_):
        if self.loading: return
        self.save_button.setEnabled(True)
        self.error.setStyleSheet("")
        self.error.setText("Kaydedilmemiş değişiklikler var.")

    def update_quality(self, *_):
        fmt = self.format.currentText()
        self.lossless.setVisible(fmt == "WEBP")
        adjustable = fmt == "JPG" or (fmt == "WEBP" and not self.lossless.isChecked())
        self.quality.setEnabled(adjustable)
        self.quality_label.setText(f"%{self.quality.value()}" if adjustable else "Kayıpsız")
        self.quality_hint.setText("Kalite yalnızca kaydedilen dosyaya uygulanır. Pano ve görüntü boyutları korunur." if adjustable
                                  else "PNG kayıpsızdır. Kaliteyi ayarlamak için JPG veya kayıplı WebP seçin." if fmt == "PNG"
                                  else "Kayıpsız mod tüm ayrıntıları korur. Kaydırıcı için kayıpsız sıkıştırmayı kapatın.")

    def browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Kayıt klasörü", self.folder.text())
        if folder: self.folder.setText(folder)

    def pick_color(self):
        value = QColorDialog.getColor(QColor(self.color_value), self, "Çizim rengi")
        if value.isValid():
            self.color_value = value.name(); self.color.setText(value.name()); self.mark_changed()

    def preferences(self):
        folder = self.folder.text().strip()
        if not folder or not Path(folder).is_absolute(): raise ValueError("Kayıt için tam bir klasör yolu seçin.")
        sequences = [edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText) for edit in self.keys]
        parsed = [parse_hotkey(value) for value in sequences]
        if len(set(parsed)) != len(parsed): raise ValueError("Aynı tuşu birden fazla yakalama işlemine atayamazsınız.")
        return replace(self.original, theme=self.theme.currentData(),
                       capture_key=self.keys[0].keySequence().toString(QKeySequence.SequenceFormat.PortableText),
                       fullscreen_key=self.keys[1].keySequence().toString(QKeySequence.SequenceFormat.PortableText),
                       window_key=self.keys[2].keySequence().toString(QKeySequence.SequenceFormat.PortableText),
                       save_dir=folder, image_format=self.format.currentText(), quality=self.quality.value(),
                       webp_lossless=self.lossless.isChecked(), color=self.color_value,
                       stroke=self.stroke.value(), blur=self.blur.value(), **{k: v.isChecked() for k, v in self.checks.items()})

    def show_error(self, message):
        self.error.setStyleSheet("color: #ef8c9e;")
        self.error.setText(message)

    def saved(self, preferences):
        self.load(preferences)
        self.error.setText("Ayarlar kaydedildi.")

    def closeEvent(self, event):
        for recorder in self.keys: recorder.stop_recording()
        self.hide()
        event.ignore()
