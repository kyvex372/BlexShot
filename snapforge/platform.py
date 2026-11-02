"""Small, typed Win32 boundary. No polling keyboard hook is required."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys

IS_WINDOWS = sys.platform == "win32"


def enable_dpi_awareness():
    if IS_WINDOWS:
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            ctypes.windll.shcore.SetProcessDpiAwareness(2)


def user32():
    lib = ctypes.WinDLL("user32", use_last_error=True)
    lib.GetForegroundWindow.restype = wintypes.HWND
    lib.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    lib.IsIconic.argtypes = [wintypes.HWND]
    lib.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    lib.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    lib.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    return lib


def cursor_position():
    pt = wintypes.POINT()
    if not user32().GetCursorPos(ctypes.byref(pt)):
        raise ctypes.WinError(ctypes.get_last_error())
    return pt.x, pt.y


def foreground_rect():
    if not IS_WINDOWS:
        return None
    lib = user32()
    hwnd = lib.GetForegroundWindow()
    if not hwnd or lib.IsIconic(hwnd):
        return None
    rect = wintypes.RECT()
    dwm = ctypes.WinDLL("dwmapi")
    dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    result = dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect))
    if result != 0 and not lib.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)


def set_startup(enabled: bool):
    if not IS_WINDOWS:
        if enabled:
            raise OSError("Otomatik başlatma yalnızca Windows üzerinde kullanılabilir.")
        return
    import winreg
    if getattr(sys, "frozen", False):
        command = subprocess.list2cmdline([sys.executable, "--tray"])
    else:
        pythonw = str(Path(sys.executable).with_name("pythonw.exe"))
        command = subprocess.list2cmdline([pythonw, str(Path(__file__).resolve().parent.parent / "main.py"), "--tray"])
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
        if enabled:
            winreg.SetValueEx(key, "BlexShot", 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, "BlexShot")
            except FileNotFoundError:
                pass
        # Retire the old entry only when the user changes startup preferences.
        try:
            winreg.DeleteValue(key, "SnapForgePro")
        except FileNotFoundError:
            pass


def resource_path(name):
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "resources" / name


def data_dir():
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    return root / "BlexShot"
