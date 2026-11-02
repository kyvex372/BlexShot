"""A labelled capture palette, with an expandable, non-modal property editor."""
from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtWidgets import (QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                              QLayout, QMenu, QPlainTextEdit, QPushButton, QSlider, QSpinBox, QVBoxLayout)
from .document import TOOLS
from .icons import icon


class PropertyValue(QFrame):
    def __init__(self, session, title, minimum, maximum, value, prop):
        super().__init__(); layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0);layout.setSpacing(5)
        row=QHBoxLayout();row.addWidget(QLabel(title));row.addStretch()
        self.spin=QSpinBox();self.spin.setRange(minimum,maximum);self.spin.setValue(value)
        self.spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons);self.spin.setFixedWidth(60)
        self.spin.setKeyboardTracking(False);self.spin.setAccessibleName(title)
        row.addWidget(self.spin);layout.addLayout(row)
        self.slider=QSlider(Qt.Orientation.Horizontal);self.slider.setRange(minimum,maximum);self.slider.setValue(value)
        self.slider.setAccessibleName(title);layout.addWidget(self.slider)
        self.slider.valueChanged.connect(self.spin.setValue)
        self.spin.valueChanged.connect(self.slider.setValue)
        self.spin.valueChanged.connect(lambda number:session.change_property(prop,number))


class InlineToolbar(QFrame):
    def __init__(self, session, parent):
        super().__init__(parent,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint)
        self.session=session;self.drag_offset=None;self.setObjectName("inlineDock");self.setFixedWidth(260);self.settings_open=False
        root=QVBoxLayout(self);root.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize);root.setContentsMargins(10,9,10,10);root.setSpacing(7);root.addStrut(240)
        head=QHBoxLayout();name=QLabel("BlexShot");name.setObjectName("dockTitle")
        name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);head.addWidget(name);head.addStretch();self.dimensions=QLabel();self.dimensions.setObjectName("muted");head.addWidget(self.dimensions)
        close=self.action("", "close", session.cancel);close.setFixedSize(26,26);close.setToolTip("Yakalamayı iptal et · Esc")
        head.addWidget(close);root.addLayout(head)
        self.tools_area=QFrame();grid=QGridLayout(self.tools_area);grid.setContentsMargins(0,0,0,0);grid.setSpacing(5)
        self.buttons={}
        for index,(tool,title) in enumerate([("select","Seç / taşı"),("pen","Kalem"),("arrow","Ok"),("text","Metin")]):
            b=self.action(title,tool,lambda checked=False,t=tool:session.choose_tool(t));b.setCheckable(True)
            self.buttons[tool]=b;grid.addWidget(b,index//2,index%2)
        root.addWidget(self.tools_area)
        self.groups_area=QFrame();groups=QHBoxLayout(self.groups_area);groups.setContentsMargins(0,0,0,0);groups.setSpacing(5)
        for title,tools in [("Şekiller",["line","rect","ellipse","number"]),("Gizle",["blur","pixel","redact"]),
                            ("Diğer",["highlight","eraser"])]:
            b=QPushButton(title+" ▾");b.setObjectName("dockGroup");menu=QMenu(b)
            for tool in tools:
                action=menu.addAction(icon(tool),TOOLS[tool][0]);action.setCheckable(True)
                action.triggered.connect(lambda checked=False,t=tool:session.choose_tool(t));self.buttons[tool]=action
            if title=="Diğer":menu.addSeparator();menu.addAction(icon("capture"),"Seçim alanını düzelt",session.adjust_selection)
            b.setMenu(menu);groups.addWidget(b)
        root.addWidget(self.groups_area)
        self.active_tool=QLabel();self.active_tool.setObjectName("dockToolName")
        toolrow=QHBoxLayout();toolrow.addWidget(self.active_tool,1)
        self.settings_button=QPushButton("Ayarlar");self.settings_button.setObjectName("dockSettings")
        self.settings_button.setCheckable(True);self.settings_button.setToolTip("Seçili aracın renk ve boyut ayarları")
        self.settings_button.clicked.connect(self.toggle_settings);toolrow.addWidget(self.settings_button);root.addLayout(toolrow)
        self.properties=QFrame();self.properties.setObjectName("dockProperties")
        props=QVBoxLayout(self.properties);props.setContentsMargins(9,8,9,8);props.setSpacing(7)
        self.color=QPushButton("Renk");self.color.setObjectName("dockColor")
        self.color.clicked.connect(lambda:self.hex_color.setFocus());props.addWidget(self.color)
        swatches=QHBoxLayout();swatches.setSpacing(6)
        for color in ["#099b8c","#2684ff","#f26057","#ffb020","#142b3b","#ffffff"]:
            b=QPushButton();b.setFixedSize(25,22);b.setToolTip(color);b.setAccessibleName(f"Renk {color}")
            b.setStyleSheet(f"background:{color};border:1px solid #aebfc9;border-radius:6px;")
            b.clicked.connect(lambda checked=False,c=color:session.set_color(c));swatches.addWidget(b)
        self.swatches=QFrame();sw=QHBoxLayout(self.swatches);sw.setContentsMargins(0,0,0,0);sw.addLayout(swatches)
        props.addWidget(self.swatches)
        self.hex_color=QLineEdit();self.hex_color.setPlaceholderText("#099B8C");self.hex_color.setMaxLength(7)
        self.hex_color.setAccessibleName("Özel renk kodu");self.hex_color.editingFinished.connect(self.apply_hex);props.addWidget(self.hex_color)
        self.property_widgets={}
        for prop,title,low,high,value in [("width","Kalınlık · px",1,100,session.engine.stroke),
                                          ("font_size","Yazı boyutu · px",10,180,28),
                                          ("strength","Gizleme yoğunluğu",1,80,session.engine.strength),
                                          ("opacity","Opaklık · %",5,100,100)]:
            control=PropertyValue(session,title,low,high,value,prop);props.addWidget(control)
            self.property_widgets[prop]=(control,)
            setattr(self,{"width":"stroke","font_size":"font","strength":"blur","opacity":"opacity"}[prop],control.spin)
        self.text_area=QFrame();text=QVBoxLayout(self.text_area);text.setContentsMargins(0,0,0,0);text.setSpacing(6)
        self.text_edit=QPlainTextEdit();self.text_edit.setPlaceholderText("Önce görüntüye tıklayın, sonra buraya yazın…")
        self.text_edit.setFixedHeight(60);self.text_edit.setAccessibleName("Görüntüye eklenecek metin")
        self.text_edit.textChanged.connect(session.update_text);text.addWidget(self.text_edit)
        add=self.action("Metni uygula","text",session.commit_text);text.addWidget(add);props.addWidget(self.text_area)
        root.addWidget(self.properties)
        history=QHBoxLayout();self.undo=self.action("Geri al","undo",session.doc_undo);self.redo=self.action("İleri al","redo",session.doc_redo)
        history.addWidget(self.undo);history.addWidget(self.redo);root.addLayout(history)
        self.status=QLabel("Görüntünün üzerinde çizin.");self.status.setObjectName("muted");self.status.setWordWrap(True);root.addWidget(self.status)
        output=QHBoxLayout();self.copy_button=self.action("Kopyala","copy",session.copy);self.copy_button.setObjectName("primary")
        self.save_button=self.action("Kaydet","save",session.save);output.addWidget(self.copy_button);output.addWidget(self.save_button);root.addLayout(output)

    def toggle_settings(self, checked):
        self.settings_open=checked
        self.session.selection_changed(self.session.engine.selected())

    def action(self,title,name,callback):
        b=QPushButton(title);b.setIcon(icon(name));b.setIconSize(QSize(16,16));b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(callback);return b

    def apply_hex(self):
        from PySide6.QtGui import QColor
        color=QColor(self.hex_color.text())
        if color.isValid():self.session.set_color(color.name())
        else:self.status.setText("Geçerli bir renk kodu girin: #099B8C")

    def set_busy(self,busy,message=""):
        self.copy_button.setEnabled(not busy);self.save_button.setEnabled(not busy)
        self.tools_area.setEnabled(not busy);self.groups_area.setEnabled(not busy);self.properties.setEnabled(not busy)
        self.status.setText(message or "Görüntünün üzerinde çizin.")

    def place(self,point):
        screen=QApplication.screenAt(point) or self.parent().screen();bounds=screen.availableGeometry()
        self.adjustSize();self.move(max(bounds.left(),min(point.x(),bounds.right()-self.width()+1)),
                                   max(bounds.top(),min(point.y(),bounds.bottom()-self.height()+1)))

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and event.position().y()<48:
            self.drag_offset=event.globalPosition().toPoint()-self.pos()
    def mouseMoveEvent(self,event):
        if self.drag_offset is not None:self.place(event.globalPosition().toPoint()-self.drag_offset)
    def mouseReleaseEvent(self,event):self.drag_offset=None
    def keyPressEvent(self,event):self.session.key_press(event)
