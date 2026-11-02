# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os
import sys
root = Path(SPECPATH)
# Do not collect unrelated ICU/UCRT DLLs from tools installed on the build
# machine's PATH (e.g. Poppler). Qt uses Windows' system ICU; a foreign ICU
# with the same DLL name can package successfully but fail to import QtCore.
windows = Path(os.environ.get('SystemRoot', r'C:\Windows'))
os.environ['PATH'] = os.pathsep.join(dict.fromkeys([
    str(Path(sys.executable).parent), sys.base_prefix,
    str(Path(sys.base_prefix) / 'DLLs'), str(windows / 'System32'), str(windows),
]))
a = Analysis([str(root / 'main.py')], pathex=[str(root)],
             binaries=[], datas=[(str(root / 'resources'), 'resources')],
             hiddenimports=['PIL.WebPImagePlugin', 'PIL.JpegImagePlugin', 'PIL.PngImagePlugin'],
             hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtQml',
                       'PySide6.QtQuick', 'PySide6.QtPdf', 'tkinter', 'matplotlib', 'pytest'],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name=os.environ.get('BLEXSHOT_EXE_NAME', 'BlexShot'),
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False,
          icon=str(root / 'resources' / 'app.ico'),
          manifest=str(root / 'resources' / 'app.manifest'))
