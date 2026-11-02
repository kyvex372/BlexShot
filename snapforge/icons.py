"""Resolution-independent SVG icons, painted directly at the target device DPI."""
from PySide6.QtCore import QByteArray, QSize
from PySide6.QtGui import QColor, QIcon, QIconEngine, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication
from .platform import resource_path

class SvgIconEngine(QIconEngine):
    def __init__(self,name,color=None):
        super().__init__(); self.name=name; self.color=color
    def clone(self): return SvgIconEngine(self.name,self.color)
    def paint(self,painter,rect,mode,state):
        color=QColor(self.color or QApplication.palette().color(QPalette.ColorRole.WindowText))

        if mode==QIcon.Mode.Disabled: color.setAlpha(85)
        path=resource_path("icons")/(self.name+".svg")
        if not path.exists(): path=resource_path("icons")/"rect.svg"
        data=path.read_text(encoding="utf-8").replace("currentColor",color.name())
        renderer=QSvgRenderer(QByteArray(data.encode()))
        painter.save(); painter.setOpacity(color.alphaF()); renderer.render(painter,rect); painter.restore()
    def pixmap(self,size,mode,state):
        pix=QPixmap(size); pix.fill(QColor(0,0,0,0))
        p=QPainter(pix); self.paint(p,pix.rect(),mode,state); p.end(); return pix
    def scaledPixmap(self,size,mode,state,scale):
        pix=self.pixmap(QSize(round(size.width()*scale),round(size.height()*scale)),mode,state)
        pix.setDevicePixelRatio(scale); return pix

def icon(name,color=None,size=24): return QIcon(SvgIconEngine(name,color))
