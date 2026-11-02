"""Real Windows registration + custom recorder + native dispatcher regression."""
from pathlib import Path
import sys,ctypes,json,traceback
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from PySide6.QtCore import QTimer,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from snapforge.app import Controller
from snapforge.settings import SettingsStore
from snapforge.theme import apply_theme

root=Path(__file__).resolve().parent.parent;out=root/'artifacts';out.mkdir(exist_ok=True)
app=QApplication([]);app.setQuitOnLastWindowClosed(False);apply_theme(app)
store=SettingsStore(out/'hotkey-native-test.json')
store.value=replace(store.value,capture_key='Ctrl+Shift+F10',fullscreen_key='Ctrl+Shift+F11',window_key='Ctrl+Shift+F12')
c=Controller(app,store,enable_hotkeys=False);calls=[];report={}
c.hotkeys.callbacks=[lambda:calls.append('region'),lambda:None,lambda:None]

def finish(error=None):
    if error:report['error']=repr(error);report['traceback']=traceback.format_exc()
    c.hotkeys.clear();c.tray.hide()
    if c.management:c.management.hide()
    c.window.canvas.shutdown();c.window.force_close=True;c.window.close()
    (out/'hotkey-recording-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2));app.exit(1 if error else 0)

def verify():
    try:
        c.hotkeys.configure(c.sequences(store.value));c.settings();c.management.nav.setCurrentRow(1)
        r=c.management.keys[0];r.start_recording()
        assert c.hotkeys.suspended and not c.hotkeys.registered
        QTest.keyClick(r,Qt.Key.Key_PageUp)
        assert not c.hotkeys.suspended and r.keySequence().toString()=='PgUp'
        assert not c.capturing
        c.apply_settings()
        report['pgup_recorded']=True
        expected='PgUp'
        if store.value.capture_key != expected:
            # A running user application may legitimately own PgUp. Verify that
            # rejection is visible and leaves preferences intact, then test a
            # separate combination without interfering with that application.
            assert 'kullanılıyor' in c.management.error.text(), c.management.error.text()
            assert store.value.capture_key=='Ctrl+Shift+F10'
            report['pgup_conflict_reported_without_saving']=True
            r.start_recording()
            QTest.keyClick(r,Qt.Key.Key_F9,Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.ShiftModifier)
            expected='Ctrl+Shift+F9'
            c.apply_settings()
        assert store.value.capture_key==expected, c.management.error.text()
        assert SettingsStore(store.path).value.capture_key==expected
        assert c.hotkeys.registered.get(0x5300)
        report['registered_persisted_sequence']=expected
        report['recording_does_not_capture']=True
        assert ctypes.windll.user32.PostThreadMessageW(ctypes.windll.kernel32.GetCurrentThreadId(),0x312,0x5300,0)
        QTimer.singleShot(200,dispatch)
    except Exception as exc:finish(exc)

def dispatch():
    try:
        assert calls==['region'];report['native_dispatch']=True;report['passed']=True;finish()
    except Exception as exc:finish(exc)

QTimer.singleShot(200,verify);QTimer.singleShot(10000,lambda:finish(TimeoutError('Shortcut test timed out')))
sys.exit(app.exec())
