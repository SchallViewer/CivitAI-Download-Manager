# download_notifications.py
from PyQt5.QtWidgets import QMessageBox, QSystemTrayIcon


class DownloadNotificationHandler:
    def __init__(self, host):
        self.host = host

    def connect(self):
        host = self.host
        try:
            host.download_manager.downloads_changed.connect(host.update_downloads_panel)
            host.download_manager.download_started.connect(self._notify_download_started)
            host.download_manager.download_queued.connect(self._notify_download_queued)
            host.download_manager.download_file_completed.connect(self._notify_download_file_completed)
            host.download_manager.download_gathering_images.connect(self._notify_download_gathering_images)
            host.download_manager.download_fully_completed.connect(self._notify_download_fully_completed)
            try:
                host.download_manager.download_started.connect(self._modal_download_started)
                host.download_manager.download_queued.connect(self._modal_download_queued)
            except Exception:
                pass
        except Exception:
            pass

    def _notify_download_started(self, file_name: str):
        try:
            msg = f"Downloading: {file_name}"
            self.host.status_bar.showMessage(msg, 5000)
            if getattr(self.host, 'tray', None) and isinstance(self.host.tray, QSystemTrayIcon):
                self.host.tray.showMessage("Civitai Manager", msg, QSystemTrayIcon.Information, 5000)
        except Exception:
            pass

    def _notify_download_queued(self, file_name: str):
        try:
            msg = f"Queued: {file_name} (waiting for a free slot)"
            self.host.status_bar.showMessage(msg, 5000)
            if getattr(self.host, 'tray', None) and isinstance(self.host.tray, QSystemTrayIcon):
                self.host.tray.showMessage("Civitai Manager", msg, QSystemTrayIcon.Information, 5000)
        except Exception:
            pass

    def _modal_download_started(self, file_name: str):
        try:
            QMessageBox.information(
                self.host,
                "Download Started",
                f"The model file is now downloading:\n\n{file_name}",
                QMessageBox.Ok,
            )
        except Exception:
            pass

    def _modal_download_queued(self, file_name: str):
        try:
            QMessageBox.information(
                self.host,
                "Download Queued",
                f"The model file was queued and will start when a slot is free:\n\n{file_name}",
                QMessageBox.Ok,
            )
        except Exception:
            pass

    def _notify_download_file_completed(self, file_name: str):
        try:
            msg = f"Model downloaded: {file_name} - Now gathering images..."
            self.host.status_bar.showMessage(msg, 8000)
            if getattr(self.host, 'tray', None) and isinstance(self.host.tray, QSystemTrayIcon):
                self.host.tray.showMessage(
                    "Civitai Manager",
                    f"Model downloaded: {file_name}",
                    QSystemTrayIcon.Information,
                    5000,
                )
        except Exception:
            pass

    def _notify_download_gathering_images(self, file_name: str):
        try:
            msg = f"Gathering images for: {file_name}..."
            self.host.status_bar.showMessage(msg, 10000)
        except Exception:
            pass

    def _notify_download_fully_completed(self, file_name: str):
        try:
            msg = f"Download completed: {file_name}"
            self.host.status_bar.showMessage(msg, 8000)
            if getattr(self.host, 'tray', None) and isinstance(self.host.tray, QSystemTrayIcon):
                self.host.tray.showMessage(
                    "Civitai Manager",
                    f"Download completed: {file_name}",
                    QSystemTrayIcon.Information,
                    5000,
                )
        except Exception:
            pass
