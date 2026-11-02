"""Ocean: airy light surfaces, ink typography and vivid teal/coral accents."""
from PySide6.QtGui import QColor, QPalette


def apply_theme(app,name="light"):
    dark=name=="dark"
    bg,surface,raised=("#14242d","#1c303b","#27424f") if dark else ("#f1f6f9","#ffffff","#eaf1f5")
    text,muted,border=("#eef8fa","#adc6d1","#36515f") if dark else ("#15354a","#617e91","#dce8ef")
    accent="#10ad9c" if dark else "#008f83"
    palette=QPalette()
    for role,value in [(QPalette.ColorRole.Window,bg),(QPalette.ColorRole.Base,surface),(QPalette.ColorRole.AlternateBase,raised),
                       (QPalette.ColorRole.WindowText,text),(QPalette.ColorRole.Text,text),(QPalette.ColorRole.ButtonText,text),
                       (QPalette.ColorRole.Button,surface),(QPalette.ColorRole.Highlight,accent),(QPalette.ColorRole.HighlightedText,"#ffffff")]:
        palette.setColor(role,QColor(value))
    app.setPalette(palette)
    app.setStyleSheet(f"""
      QWidget {{ color:{text}; font-family:'Segoe UI';font-size:13px; }}
      QMainWindow,QDialog {{ background:{bg}; }}
      QLabel {{ background:transparent; }}
      QLabel#muted,QLabel#controlFootnote {{ color:{muted};font-size:12px; }}
      QLabel#eyebrow {{ color:{accent};font-size:10px;font-weight:700;letter-spacing:1.2px; }}
      QLabel#section {{ color:{muted};font-size:10px;font-weight:700;letter-spacing:1px; }}
      QLabel#controlTitle,QLabel#title {{ font-size:21px;font-weight:650;letter-spacing:-0.5px; }}
      QLabel#controlBrand {{ font-size:18px;font-weight:700; }}
      QLabel#cardTitle {{ font-size:14px;font-weight:600; }}
      QLabel#qualityValue {{ color:{accent};font-size:19px;font-weight:650; }}
      QFrame#panel,QFrame#card,QFrame#controlCard {{ background:{surface};border:1px solid {border};border-radius:10px; }}
      QDialog#management {{ background:{bg};border:1px solid {border}; }}
      QWidget#controlContent {{ background:{bg}; }}
      QFrame#controlSidebar {{ background:{surface};border-right:1px solid {border}; }}
      QFrame#controlFooter {{ background:{surface};border-top:1px solid {border}; }}
      QFrame#customTitleBar {{ background:{surface};border-bottom:1px solid {border}; }}
      QLabel#titleCaption {{ font-size:10px;color:{muted};font-weight:600;letter-spacing:1.4px; }}
      QPushButton,QToolButton {{ background:{surface};border:1px solid {border};border-radius:6px;padding:6px 10px; }}
      QPushButton:hover,QToolButton:hover {{ background:{raised};border-color:#62bdb7; }}
      QPushButton:pressed,QToolButton:pressed {{ background:#b6e7e0;color:#15354a; }}
      QPushButton:focus,QToolButton:focus {{ border:1px solid {accent}; }}
      QPushButton:checked,QToolButton:checked {{ background:{'#244f54' if dark else '#dcf4ee'};border-color:{accent};color:{text}; }}
      QPushButton#primary {{ background:{accent};color:#ffffff;border:1px solid {accent};font-weight:600;padding:6px 12px; }}
      QPushButton#primary:hover {{ background:#08a99a; }}
      QPushButton:disabled,QToolButton:disabled {{ background:{raised};color:{muted};border-color:{border}; }}
      QPushButton#quiet {{ background:transparent;border-color:transparent;color:{muted}; }}
      QPushButton#quiet:hover {{ background:{raised};color:{text}; }}
      QPushButton#windowControl {{ border:none;background:transparent;border-radius:5px;padding:5px; }}
      QPushButton#windowControl:hover {{ background:#f26057; }}
      QLineEdit,QSpinBox,QPlainTextEdit,QKeySequenceEdit,QComboBox {{ background:{surface};border:1px solid {border};border-radius:7px;padding:5px 8px;selection-background-color:{accent}; }}
      QLineEdit:focus,QSpinBox:focus,QPlainTextEdit:focus {{ border:1px solid {accent}; }}
      QSpinBox::up-button,QSpinBox::down-button {{ width:14px;border:none;background:{raised}; }}
      QPushButton#shortcutRecorder {{ background:{raised};border:1px solid {border};font-family:'Consolas';font-size:13px;font-weight:600;padding:7px 12px; }}
      QPushButton#shortcutRecorder[recording="true"] {{ background:{'#244f54' if dark else '#dcf4ee'};border:1px solid {accent};color:{text}; }}
      QFrame#segmented {{ background:{raised};border:1px solid {border};border-radius:9px; }}
      QPushButton#segment {{ background:transparent;border:none;padding:7px 12px;border-radius:6px;color:{muted}; }}
      QPushButton#segment:checked {{ background:{surface};color:{accent}; }}
      QListWidget {{ background:transparent;border:none;outline:none; }}
      QListWidget::item {{ padding:9px 14px;margin:0 3px;border-radius:6px; }}
      QListWidget#controlNavigation {{ background:{surface};padding:2px 16px;border-bottom:1px solid {border}; }}
      QFrame#managementHeader {{ background:{surface}; }}
      QListWidget::item:selected {{ background:{'#244f54' if dark else '#dcf4ee'};color:{text}; }}
      QListWidget::item:hover {{ background:{raised}; }}
      QScrollArea {{ border:none;background:transparent; }}
      QScrollBar:vertical {{ background:transparent;width:7px; }}
      QScrollBar::handle:vertical {{ background:#a4c0cd;border-radius:3px;min-height:30px; }}
      QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{ height:0; }}
      QSlider::groove:horizontal {{ height:5px;background:{border};border-radius:2px; }}
      QSlider::sub-page:horizontal {{ background:{accent};border-radius:2px; }}
      QSlider::handle:horizontal {{ background:{accent};width:13px;margin:-4px 0;border-radius:6px; }}
      QMenu {{ background:{surface};border:1px solid {border};padding:6px;border-radius:9px; }}
      QMenu::item {{ padding:10px 16px;border-radius:5px; }}
      QMenu::item:selected {{ background:{raised}; }}
      QMenu::separator {{ height:1px;background:{border};margin:5px; }}
      QToolTip {{ background:{text};color:{surface};padding:7px;border:none; }}
      QStatusBar {{ background:{surface};border-top:1px solid {border}; }}
      QFrame#inlineDock {{ background:{surface};border:1px solid #82c9c2;border-radius:10px; }}
      QFrame#inlineDock QPushButton {{ padding:5px 6px;font-size:12px; }}
      QFrame#inlineDock QMenu {{ font-size:13px; }}
      QLabel#dockTitle {{ font-size:14px;font-weight:650; }}
      QLabel#dockToolName {{ color:{accent};font-size:12px;font-weight:650; }}
      QFrame#dockProperties {{ background:{bg};border:1px solid {border};border-radius:10px; }}
      QFrame#dockProperties QSpinBox {{ padding:4px 6px;background:{surface}; }}
      QPushButton#dockGroup {{ background:{raised};border:none;font-size:12px;padding:6px 4px; }}
      QPushButton#dockSettings {{ padding:3px 7px;background:transparent;color:{muted};border-color:transparent; }}
      QPushButton#dockSettings:checked {{ background:{raised};color:{accent}; }}
      QPushButton#dockColor {{ border:none;background:transparent;text-align:left;padding:0;color:{muted}; }}
    """)
    from .icons import icon
    for widget in app.allWidgets():
        name=widget.property("icon_name")
        if name:widget.setIcon(icon(name))
        if widget.property("control_navigation"):
            for index in range(widget.count()):
                item=widget.item(index);item.setIcon(icon(item.data(256)))
