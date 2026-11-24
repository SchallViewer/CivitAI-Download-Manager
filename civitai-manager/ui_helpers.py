# ui_helpers.py
import os
import ntpath
import requests
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QCheckBox, QDialogButtonBox


def _local_image_path(source):
    if not isinstance(source, str):
        return None
    if source.lower().startswith('file://'):
        parsed = urlsplit(source)
        path = url2pathname(unquote(parsed.path))
        if parsed.netloc:
            path = os.path.join('\\\\' + parsed.netloc, path.lstrip('\\/'))
        return path
    if os.path.exists(source) or os.path.isabs(source) or ntpath.isabs(source):
        return source
    return None


class ImageLoaderThread(QThread):
    """
    Thread that loads an image from a URL or local path and emits (url, bytes, target_widget).
    Used to avoid blocking the UI and to prevent race conditions by tagging requests.
    """
    image_loaded = pyqtSignal(object, object, object)

    def __init__(self, url, target_widget, headers=None):
        super().__init__()
        self.url = url
        self.target_widget = target_widget
        self.headers = headers or {}

    def run(self):
        try:
            path = _local_image_path(self.url)
            if path:
                try:
                    with open(path, 'rb') as f:
                        data = f.read()
                    self.image_loaded.emit(self.url, data, self.target_widget)
                except Exception as e:
                    print(f"Error loading local image '{path}': {e}")
                return

            if not isinstance(self.url, str) or urlsplit(self.url).scheme.lower() not in ('http', 'https'):
                print(f"Unsupported image source: {self.url}")
                return

            headers = dict(self.headers or {})
            headers.setdefault("User-Agent", "CivitaiDownloadManager/1.0")
            resp = requests.get(self.url, headers=headers, timeout=15)
            if resp.status_code == 200:
                self.image_loaded.emit(self.url, resp.content, self.target_widget)
            else:
                print(f"Failed to load image: HTTP {resp.status_code}")
        except Exception as e:
            print(f"Error loading image: {e}")


class FileSelectionDialog(QDialog):
    """
    Dialog to select one or more files to download for a model version.
    If any .safetensors exists, .pt/.pth files are hidden by default.
    """
    def __init__(self, parent, version_files):
        super().__init__(parent)
        self.setWindowTitle("Select files to download")
        self.setModal(True)

        layout = QVBoxLayout(self)
        info = QLabel("This version has multiple files. Select which files to download.")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.checkboxes = []
        # Prefer safe files; if any .safetensors exist, hide .pt/.pth from selection
        has_safetensors = any(((f.get('name') or '').lower().endswith('.safetensors') and f.get('type') == 'Model') for f in (version_files or []))
        for f in (version_files or []):
            if not isinstance(f, dict) or f.get('type') != 'Model':
                continue
            name = f.get('name') or ''
            lname = name.lower()
            if has_safetensors and (lname.endswith('.pt') or lname.endswith('.pth')):
                continue
            cb = QCheckBox(name if name else 'Model file')
            cb.setChecked(lname.endswith('.safetensors'))
            cb.file_ref = f
            layout.addWidget(cb)
            self.checkboxes.append(cb)

        if not self.checkboxes:
            # Fallback: show all Model files if filtering removed everything
            for f in (version_files or []):
                if not isinstance(f, dict) or f.get('type') != 'Model':
                    continue
                name = f.get('name') or ''
                cb = QCheckBox(name if name else 'Model file')
                cb.setChecked(False)
                cb.file_ref = f
                layout.addWidget(cb)
                self.checkboxes.append(cb)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selected_files(self):
        return [cb.file_ref for cb in self.checkboxes if cb.isChecked()]
