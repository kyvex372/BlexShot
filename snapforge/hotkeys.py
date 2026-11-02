import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QTimer, Qt
from PySide6.QtGui import QKeySequence

from .platform import IS_WINDOWS, user32


def parse_hotkey(sequence):
    seq = QKeySequence(sequence)
    if seq.count() != 1 or seq.isEmpty():
        raise ValueError("Tek bir tuş birleşimi seçin.")
    combo = seq[0]
    key = combo.key()
    mapping = {
        Qt.Key.Key_Print:0x2C, Qt.Key.Key_Space:0x20, Qt.Key.Key_Pause:0x13,
        Qt.Key.Key_PageUp:0x21, Qt.Key.Key_PageDown:0x22, Qt.Key.Key_Home:0x24, Qt.Key.Key_End:0x23,
        Qt.Key.Key_Insert:0x2D, Qt.Key.Key_Delete:0x2E, Qt.Key.Key_Left:0x25, Qt.Key.Key_Up:0x26,
        Qt.Key.Key_Right:0x27, Qt.Key.Key_Down:0x28, Qt.Key.Key_Escape:0x1B, Qt.Key.Key_Tab:0x09,
        Qt.Key.Key_Backspace:0x08, Qt.Key.Key_Return:0x0D, Qt.Key.Key_Enter:0x0D,
        Qt.Key.Key_CapsLock:0x14, Qt.Key.Key_NumLock:0x90, Qt.Key.Key_ScrollLock:0x91,
        Qt.Key.Key_Menu:0x5D, Qt.Key.Key_VolumeMute:0xAD, Qt.Key.Key_VolumeDown:0xAE,
        Qt.Key.Key_VolumeUp:0xAF, Qt.Key.Key_MediaPlay:0xB3, Qt.Key.Key_MediaStop:0xB2,
        Qt.Key.Key_MediaPrevious:0xB1, Qt.Key.Key_MediaNext:0xB0,
    }
    vk = mapping.get(key)
    mods = combo.keyboardModifiers()
    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z or Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        vk = int(key)
        if mods & Qt.KeyboardModifier.KeypadModifier and Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            vk = 0x60 + int(key) - int(Qt.Key.Key_0)
    elif Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
        vk = 0x70 + int(key) - int(Qt.Key.Key_F1)
    if mods & Qt.KeyboardModifier.KeypadModifier:
        vk = {Qt.Key.Key_Plus:0x6B,Qt.Key.Key_Minus:0x6D,Qt.Key.Key_Asterisk:0x6A,
              Qt.Key.Key_Slash:0x6F,Qt.Key.Key_Period:0x6E}.get(key,vk)
    if vk is None and IS_WINDOWS and 0x20 <= int(key) <= 0xFFFF:
        lib = user32()
        lib.GetKeyboardLayout.restype = wintypes.HANDLE
        lib.VkKeyScanExW.argtypes = [wintypes.WCHAR,wintypes.HANDLE]
        lib.VkKeyScanExW.restype = ctypes.c_short
        translated = lib.VkKeyScanExW(chr(int(key)), lib.GetKeyboardLayout(0))
        if translated != -1: vk = translated & 0xff
    if vk is None:
        raise ValueError("Bu tuş Windows global kısayolu olarak desteklenmiyor. Tek bir fiziksel tuş veya birleşim kullanın.")
    flags = 0x4000
    for qt, win in [(Qt.KeyboardModifier.AltModifier,1),(Qt.KeyboardModifier.ControlModifier,2),
                    (Qt.KeyboardModifier.ShiftModifier,4),(Qt.KeyboardModifier.MetaModifier,8)]:
        if mods & qt: flags |= win
    return flags, vk


class Hotkeys(QAbstractNativeEventFilter):
    def __init__(self, app, callbacks):
        super().__init__()
        self.app = app
        self.callbacks = callbacks
        self.registered = {}
        self.sequences = []
        self.suspended = False
        self.epoch = 0
        app.installNativeEventFilter(self)

    def configure(self, sequences):
        parsed = [parse_hotkey(s) for s in sequences]
        if len(set(parsed)) != len(parsed):
            raise ValueError("Her yakalama işlemi için farklı kısayol seçin.")
        if self.suspended:
            self.sequences = list(sequences)
            return
        old = self.sequences[:]
        changed = [i for i in range(len(sequences)) if i >= len(old) or parsed[i] != parse_hotkey(old[i]) or 0x5300+i not in self.registered]
        lib = user32()
        self.epoch += 1
        for i in changed:
            ident = 0x5300+i
            if ident in self.registered:
                lib.UnregisterHotKey(None,ident); self.registered.pop(ident)
        acquired = []
        try:
            for i in changed:
                ident = 0x5300+i
                if not lib.RegisterHotKey(None,ident,*parsed[i]):
                    raise OSError(f"{sequences[i]} Windows veya başka bir uygulama tarafından kullanılıyor. Farklı bir birleşim deneyin.")
                self.registered[ident] = self.callbacks[i]; acquired.append(ident)
            self.sequences = list(sequences)
        except OSError:
            for ident in acquired:
                lib.UnregisterHotKey(None,ident); self.registered.pop(ident,None)
            for i in changed:
                if i < len(old) and lib.RegisterHotKey(None,0x5300+i,*parse_hotkey(old[i])):
                    self.registered[0x5300+i] = self.callbacks[i]
            self.sequences = old
            raise

    def pause(self):
        if self.suspended: return
        previous = self.sequences[:]
        self.clear(); self.sequences = previous; self.suspended = True

    def resume(self):
        if not self.suspended: return
        previous = self.sequences[:]
        self.suspended = False
        if previous: self.configure(previous)

    def clear(self):
        self.epoch += 1
        if IS_WINDOWS:
            for ident in self.registered:
                user32().UnregisterHotKey(None, ident)
        self.registered.clear()
        self.sequences = []

    def nativeEventFilter(self, event_type, message):
        if IS_WINDOWS and bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam in self.registered:
                epoch = self.epoch
                callback = self.registered[msg.wParam]
                QTimer.singleShot(0, lambda: callback() if not self.suspended and self.epoch == epoch else None)
                return True, 0
        return False, 0
