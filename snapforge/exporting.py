"""Capture export stays off the GUI thread, including PNG/WebP encoding."""
from copy import deepcopy
from PySide6.QtCore import QObject, QRunnable, Signal
from .imaging import render, save_image


class ExportSignals(QObject):
    done=Signal(object,str,str)


class ExportTask(QRunnable):
    def __init__(self,image,layers,destination="copy",fmt="PNG",quality=98,lossless=True):
        super().__init__();self.image=image;self.layers=deepcopy(layers);self.destination=str(destination)
        self.fmt=fmt;self.quality=quality;self.lossless=lossless;self.signals=ExportSignals()
    def run(self):
        try:
            image=render(self.image,self.layers)
            if self.destination!="copy":save_image(image,self.destination,self.fmt,self.quality,self.lossless)
            self.signals.done.emit(image,self.destination,"")
        except Exception as exc:self.signals.done.emit(None,self.destination,str(exc))
