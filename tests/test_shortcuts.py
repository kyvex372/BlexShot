import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from unittest.mock import patch
import unittest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from snapforge.controls import ShortcutRecorder
from snapforge.hotkeys import Hotkeys, parse_hotkey

APP=QApplication.instance() or QApplication([])


class ShortcutTests(unittest.TestCase):
    def test_navigation_and_single_keys(self):
        for sequence,vk in [("PgUp",0x21),("PgDown",0x22),("Home",0x24),("End",0x23),
                            ("Ins",0x2d),("Del",0x2e),("Left",0x25),("Tab",9),("Esc",27),
                            ("Backspace",8),("A",65),("7",55),("F24",0x87)]:
            with self.subTest(sequence=sequence): self.assertEqual(parse_hotkey(sequence)[1],vk)

    def test_record_pageup_and_cancel_restore(self):
        recorder=ShortcutRecorder();recorder.setKeySequence(QKeySequence("Print"));recorder.show()
        events=[];recorder.recording_changed.connect(events.append)
        recorder.start_recording();QTest.keyClick(recorder,Qt.Key.Key_PageUp)
        self.assertEqual(recorder.keySequence().toString(),"PgUp")
        self.assertEqual(events,[True,False])
        recorder.start_recording();recorder.stop_recording()
        self.assertEqual(recorder.keySequence().toString(),"PgUp")
        recorder.close();recorder.deleteLater()

    def test_conflict_preserves_unchanged_registrations(self):
        class Native:
            def __init__(self): self.keys={};self.block=set();self.removed=[]
            def RegisterHotKey(self,hwnd,ident,mods,key):
                if (mods,key) in self.block:return False
                self.keys[ident]=(mods,key);return True
            def UnregisterHotKey(self,hwnd,ident):self.removed.append(ident);self.keys.pop(ident,None);return True
        native=Native();h=Hotkeys(APP,[lambda:None]*3)
        with patch("snapforge.hotkeys.user32",return_value=native):
            h.configure(["F7","F8","F9"])
            native.removed=[];native.block.add(parse_hotkey("PgUp"))
            with self.assertRaises(OSError):h.configure(["PgUp","F8","F9"])
            self.assertNotIn(0x5301,native.removed);self.assertNotIn(0x5302,native.removed)
            self.assertEqual(native.keys[0x5300],parse_hotkey("F7"))
            h.pause();self.assertEqual(native.keys,{})
            h.resume();self.assertEqual(len(native.keys),3);h.clear()
        APP.removeNativeEventFilter(h)
