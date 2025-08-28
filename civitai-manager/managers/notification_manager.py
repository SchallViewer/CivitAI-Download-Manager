# notification_manager.py - Centralized notification handling
from PyQt5.QtWidgets import QSystemTrayIcon, QMessageBox

class NotificationManager:
    """Handles status bar and system tray notifications."""
    def __init__(self, main_window):
        self.main = main_window
        self.tray = getattr(main_window, 'tray', None)

    def _show_status(self, msg: str, timeout_ms: int = 5000):
        try:
            if hasattr(self.main, 'status_bar'):
                self.main.status_bar.showMessage(msg, timeout_ms)
        except Exception:
            pass

    def _show_tray(self, title: str, msg: str, timeout_ms: int = 5000):
        try:
            if self.tray and isinstance(self.tray, QSystemTrayIcon):
                self.tray.showMessage(title, msg, QSystemTrayIcon.Information, timeout_ms)
        except Exception:
            pass

    def notify_download_started(self, file_name: str):
        msg = f"Downloading: {file_name}"
        self._show_status(msg, 5000)
        self._show_tray("Civitai Manager", msg, 5000)

    def notify_download_queued(self, file_name: str):
        msg = f"Queued: {file_name} (waiting for a free slot)"
        self._show_status(msg, 5000)
        self._show_tray("Civitai Manager", msg, 5000)

    def show_modal_download_started(self, file_name: str):
        try:
            QMessageBox.information(self.main, "Download Started", f"The model file is now downloading:\n\n{file_name}", QMessageBox.Ok)
        except Exception:
            pass

    def show_modal_download_queued(self, file_name: str):
        try:
            QMessageBox.information(self.main, "Download Queued", f"The model file was queued and will start when a slot is free:\n\n{file_name}", QMessageBox.Ok)
        except Exception:
            pass

    def notify_download_file_completed(self, file_name: str):
        msg = f"Model downloaded: {file_name} - Now gathering images..."
        self._show_status(msg, 8000)
        self._show_tray("Civitai Manager", f"Model downloaded: {file_name}", 5000)

    def notify_download_gathering_images(self, file_name: str):
        msg = f"Gathering images for: {file_name}..."
        self._show_status(msg, 10000)

    def notify_download_fully_completed(self, file_name: str):
        msg = f"Download completed: {file_name}"
        self._show_status(msg, 8000)
        self._show_tray("Civitai Manager", f"Download completed: {file_name}", 5000)
