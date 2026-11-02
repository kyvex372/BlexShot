import logging
from logging.handlers import RotatingFileHandler
import sys
from dataclasses import replace

from PySide6.QtCore import QObject, QLockFile, QPoint, QRect, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon, QWidgetAction, QLabel, QHBoxLayout, QFrame, QVBoxLayout

from .capture import CaptureSession, grab_desktop
from .inline import InlineSession
from .dialogs import SettingsDialog
from .hotkeys import Hotkeys
from .icons import icon
from .platform import data_dir, foreground_rect, resource_path, set_startup
from .settings import SettingsStore
from .theme import apply_theme
from .window import MainWindow


class Controller(QObject):
    def __init__(self, app, store, enable_hotkeys=True):
        super().__init__()
        self.app, self.store = app, store
        self.window = MainWindow(store)
        self.session = None
        self.capturing = False
        self.was_visible = True
        self.was_management_visible = False
        self.management = None
        self.window.capture_requested.connect(self.capture)
        self.window.settings_requested.connect(self.settings)
        self.window.quit_requested.connect(self.quit)
        self.window.notify.connect(self.notify)
        self.tray = QSystemTrayIcon(QIcon(str(resource_path("app.ico"))), self)
        self.tray.setToolTip("BlexShot · Yakala. Anlat. Paylaş.")
        self.menu = QMenu(); self.menu.setObjectName("trayMenu")
        self._build_tray_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()
        self.app.setProperty("tray_available", QSystemTrayIcon.isSystemTrayAvailable())
        self.hotkeys = Hotkeys(app, [lambda: self.capture("region"), lambda: self.capture("full"), lambda: self.capture("window")])
        if enable_hotkeys:
            try:
                self.hotkeys.configure(self.sequences(store.value))
            except (OSError, ValueError) as exc:
                message = str(exc)
                self.hotkeys.clear()
                QTimer.singleShot(700, lambda: self.window.show_error(message))
                self.window.key_status.setText("Kısayol kullanılamıyor · Ayarlardan değiştirin")
        if store.load_error:
            QTimer.singleShot(900, lambda: self.window.show_error(f"Ayar dosyası okunamadı; varsayılanlar yüklendi.\n{store.load_error}"))

    @staticmethod
    def sequences(prefs):
        return [prefs.capture_key, prefs.fullscreen_key, prefs.window_key]

    def _build_tray_menu(self):
        self.menu.clear()
        branding = QWidgetAction(self.menu)
        header = QFrame(); header.setObjectName("trayBranding")
        row = QHBoxLayout(header); row.setContentsMargins(13, 10, 13, 12); row.setSpacing(11)
        mark = QLabel(); mark.setPixmap(QIcon(str(resource_path("app.ico"))).pixmap(32, 32)); row.addWidget(mark)
        labels = QVBoxLayout(); labels.setSpacing(2)
        title = QLabel("BlexShot"); title.setObjectName("trayTitle"); labels.addWidget(title)
        subtitle = QLabel("Yakala. Anlat. Paylaş."); subtitle.setObjectName("muted"); labels.addWidget(subtitle)
        row.addLayout(labels); row.addStretch(); branding.setDefaultWidget(header)
        self.menu.addAction(branding); self.menu.addSeparator()
        prefs = self.store.value
        for name, title, key, mode in [("capture", "Alan yakala", prefs.capture_key, "region"),
                                      ("screen", "Tüm ekranları yakala", prefs.fullscreen_key, "full"),
                                      ("window", "Aktif pencere · 3 saniye", "", "window-delay")]:
            action = self.menu.addAction(icon(name), f"{title}\t{key}")
            action.triggered.connect(lambda checked=False, m=mode: self.capture(m))
        self.menu.addSeparator()
        self.menu.addAction(icon("settings"), "Yönetim ve ayarlar", self.settings)
        self.menu.addAction(icon("folder"), "Editörü aç", self.open_editor)
        self.menu.addSeparator()
        self.menu.addAction("Çıkış", self.quit)

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.capture("region")

    def open_editor(self):
        if self.management: self.management.hide()
        self.show()

    def show(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def notify(self, message):
        if self.store.value.notifications and self.tray.isSystemTrayAvailable():
            self.tray.showMessage("BlexShot", message, QSystemTrayIcon.MessageIcon.Information, 2500)

    def capture(self, mode):
        if self.capturing or self.hotkeys.suspended or self.app.activeModalWidget():
            return
        rect = foreground_rect() if mode == "window" else None
        if not self.window.can_replace():
            return
        self.capturing = True
        self.hotkeys.pause()
        self.was_visible = self.window.isVisible()
        self.was_management_visible = bool(self.management and self.management.isVisible())
        if self.management: self.management.hide()
        self.window.hide()
        delay = 3000 if mode == "window-delay" else 240
        if mode == "window-delay":
            self.notify("3 saniye içinde yakalamak istediğiniz pencereye geçin.")
        QTimer.singleShot(delay, lambda: self._capture(mode, rect))

    def _capture(self, mode, rect):
        try:
            if mode == "window-delay":
                rect = foreground_rect()
            frame = grab_desktop()
            if mode in ("window", "window-delay"):
                if not rect:
                    raise ValueError("Yakalanabilecek bir aktif pencere bulunamadı.")
            self.session = InlineSession(frame, self.store, self)
            self.session.completed.connect(self.complete_inline)
            self.session.cancelled.connect(self.cancel_capture)
            self.session.show()
            if mode in ("window", "window-delay"):
                self.session.rect = QRect(*rect).intersected(frame.bounds)
                self.session.finish()
            elif mode == "full":
                self.session.rect = QRect(frame.bounds)
                self.session.finish()
        except Exception as exc:
            logging.exception("Capture failed")
            self.cancel_capture()
            self.window.show_error(f"Ekran yakalanamadı: {exc}")

    def complete_inline(self, snapshot):
        self.capturing = False
        self.restore_hotkeys()
        if self.session:
            self.session.close()
            self.session.deleteLater()
            self.session = None
        # Keep the last result available only if the user explicitly opens the editor.
        self.window.set_document(snapshot["image"], "Son yakalama", show_window=False)
        self.window.doc.layers = snapshot["layers"]
        self.window.doc.mark_saved()
        self.notify("Ekran görüntüsü panoya kopyalandı." if snapshot["destination"] == "copy" else "Ekran görüntüsü kaydedildi.")

    def cancel_capture(self):
        self.capturing = False
        self.restore_hotkeys()
        if self.session:
            self.session.close()
            self.session.deleteLater()
            self.session = None
        if self.was_visible:
            self.show()
        if self.was_management_visible:
            self.settings()

    def restore_hotkeys(self):
        try:
            self.hotkeys.resume()
        except OSError as exc:
            logging.warning("Hotkey restore: %s", exc)
            self.window.key_status.setText("Kısayol kullanımda · Ayarlardan değiştirin")

    def settings(self):
        if self.capturing or self.app.activeModalWidget():
            return
        self.window.floating.hide()
        if self.management is None:
            self.management = SettingsDialog(self.store.value)
            self.management.apply_requested.connect(self.apply_settings)
            self.management.recording_changed.connect(self.recording_changed)
            self.management.capture_requested.connect(self.capture)
            self.management.editor_requested.connect(self.open_editor)
        elif not self.management.save_button.isEnabled():
            self.management.load(self.store.value)
        self.management.showNormal()
        self.management.raise_()
        self.management.activateWindow()

    def recording_changed(self, recording):
        try:
            self.hotkeys.pause() if recording else self.hotkeys.resume()
        except OSError as exc:
            if self.management: self.management.show_error(str(exc))

    def apply_settings(self):
        dialog = self.management
        if dialog is None: return
        old = self.store.value
        hotkeys_changed = False
        startup_changed = False
        try:
            prefs = dialog.preferences()
            if self.sequences(prefs) != self.sequences(old) or not self.hotkeys.registered:
                self.hotkeys.configure(self.sequences(prefs))
                hotkeys_changed = True
            if prefs.startup != old.startup:
                set_startup(prefs.startup)
                startup_changed = True
            self.store.save(prefs)
            apply_theme(self.app, prefs.theme)
            self.window.apply_preferences()
            self._build_tray_menu()
            dialog.saved(prefs)
        except (OSError, ValueError) as exc:
            if hotkeys_changed:
                try: self.hotkeys.configure(self.sequences(old))
                except OSError: self.hotkeys.clear()
            if startup_changed:
                try: set_startup(old.startup)
                except OSError: logging.exception("Startup rollback failed")
            dialog.show_error(str(exc))

    def quit(self):
        if self.capturing and self.session:
            self.session.cancel()
        if not self.window.can_replace():
            return
        self.hotkeys.clear()
        self.window.canvas.shutdown()
        self.tray.hide()
        if self.management: self.management.hide()
        self.window.force_close = True
        self.window.close()
        self.app.quit()


def run(argv):
    app = QApplication(argv)
    app.setApplicationName("BlexShot")
    app.setOrganizationName("BlexShot")
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)
    data_dir().mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(data_dir() / "blexshot.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(message)s")

    def exception_hook(typ, value, traceback):
        logging.error("Unhandled exception", exc_info=(typ, value, traceback))
        QMessageBox.critical(None, "BlexShot", f"Bir işlem tamamlanamadı:\n{value}\n\nAyrıntılar blexshot.log dosyasına yazıldı.")
    sys.excepthook = exception_hook
    lock = QLockFile(str(data_dir() / "instance.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, "BlexShot", "Uygulama zaten çalışıyor. Bildirim alanındaki BlexShot simgesini kullanın.")
        return 0
    store = SettingsStore()
    apply_theme(app, store.value.theme)
    app.setWindowIcon(QIcon(str(resource_path("app.ico"))))
    controller = Controller(app, store, enable_hotkeys="--smoke-test" not in argv)
    if "--tray" not in argv or not QSystemTrayIcon.isSystemTrayAvailable():
        controller.settings()
    if "--smoke-test" in argv:
        QTimer.singleShot(1800, controller.quit)
    result = app.exec()
    controller.hotkeys.clear()
    controller.window.canvas.shutdown()
    lock.unlock()
    return result
