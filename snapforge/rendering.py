"""One render in flight; pending frames coalesce during rapid mouse movement."""
from copy import deepcopy
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from .imaging import render


class RenderSignals(QObject):
    done = Signal(int, object, str)


class RenderJob(QRunnable):
    def __init__(self, generation, image, layers):
        super().__init__()
        self.generation, self.image, self.layers = generation, image, layers
        self.signals = RenderSignals()

    def run(self):
        try:
            self.signals.done.emit(self.generation, render(self.image, self.layers), "")
        except Exception as exc:
            self.signals.done.emit(self.generation, None, str(exc))


class RenderQueue(QObject):
    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.generation = 0
        self.pending = None
        self.active = None
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)

    def request(self, image, layers):
        self.generation += 1
        self.pending = (self.generation, image, deepcopy(layers))
        if self.active is None:
            self._start()

    def _start(self):
        self.active = RenderJob(*self.pending)
        self.pending = None
        self.active.signals.done.connect(self._done)
        self.pool.start(self.active)

    @Slot(int, object, str)
    def _done(self, generation, image, error):
        self.active = None
        if generation == self.generation:
            if error:
                self.failed.emit(error)
            else:
                self.ready.emit(image)
        if self.pending is not None:
            self._start()

    def shutdown(self):
        self.pending = None
        self.pool.waitForDone()

    def invalidate(self):
        self.generation += 1
        self.pending = None
