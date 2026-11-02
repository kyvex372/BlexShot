from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout

from .management import SettingsDialog

class ExportPreview(QDialog):
    def __init__(self, image, parent):
        super().__init__(parent)
        self.setWindowTitle("Kaydetmeden önce · Önizleme")
        self.resize(860, 640)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        label = QLabel(f"Dışa aktarma önizlemesi   ·   {image.width()} × {image.height()} px")
        label.setObjectName("section")
        layout.addWidget(label)
        area = QScrollArea()
        self.picture = QLabel()
        self.picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pixmap = QPixmap.fromImage(image)
        self.picture.setPixmap(self.pixmap.scaled(790, 470, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        area.setWidget(self.picture)
        area.setWidgetResizable(True)
        layout.addWidget(area, 1)
        controls = QHBoxLayout()
        actual = QCheckBox("Gerçek boyutta incele (%100)")
        actual.toggled.connect(lambda checked: self.picture.setPixmap(self.pixmap if checked else self.pixmap.scaled(790, 470, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))
        controls.addWidget(actual)
        controls.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Dosyaya kaydet…")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Düzenlemeye dön")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        controls.addWidget(buttons)
        layout.addLayout(controls)

