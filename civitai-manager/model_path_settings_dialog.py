import os
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QMessageBox,
    QLineEdit,
    QComboBox,
)
from PyQt5.QtGui import QFont
from constants import PRIMARY_COLOR, BACKGROUND_COLOR, TEXT_COLOR


MODEL_TYPE_OPTIONS = [
    "Checkpoint",
    "LORA",
    "TextualInversion",
    "Hypernetwork",
    "AestheticGradient",
    "VAE",
    "Upscaler",
    "Controlnet",
    "LoCon",
    "Poses",
    "Textures",
]


class ModelPathEntryDialog(QDialog):
    def __init__(self, available_types, initial=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Model Download Path")
        self.setMinimumWidth(520)
        self._initial = initial or {}

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BACKGROUND_COLOR.name()};
                color: {TEXT_COLOR.name()};
            }}
            QLabel {{
                color: {TEXT_COLOR.name()};
            }}
        """)

        layout = QVBoxLayout(self)

        form = QVBoxLayout()
        form.setSpacing(10)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Model Type:"))
        self.type_combo = QComboBox()
        for item in available_types:
            self.type_combo.addItem(item)
        type_row.addWidget(self.type_combo, 1)
        form.addLayout(type_row)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Download Folder:"))
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Select folder path")
        path_row.addWidget(self.path_input, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        form.addLayout(path_row)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if self._initial:
            model_type = str(self._initial.get("model_type") or "").strip()
            folder = str(self._initial.get("download_dir") or "").strip()
            idx = self.type_combo.findText(model_type)
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)
            self.path_input.setText(folder)

    def _browse(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Download Directory", self.path_input.text())
        if directory:
            self.path_input.setText(directory)

    def _validate_and_accept(self):
        model_type = self.type_combo.currentText().strip()
        path = self.path_input.text().strip()
        if not model_type:
            QMessageBox.warning(self, "Invalid Entry", "Please select a model type.")
            return
        if not path:
            QMessageBox.warning(self, "Invalid Entry", "Download folder path cannot be empty.")
            return
        if not os.path.isdir(path):
            QMessageBox.warning(self, "Invalid Entry", "The selected download folder path is not valid.")
            return
        self.accept()

    def get_value(self):
        return {
            "model_type": self.type_combo.currentText().strip(),
            "download_dir": self.path_input.text().strip(),
        }


class ModelPathSettingsDialog(QDialog):
    def __init__(self, definitions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Per-Model Download Folders")
        self.setMinimumSize(680, 520)
        self._definitions = [
            {
                "model_type": str(d.get("model_type") or "").strip(),
                "download_dir": str(d.get("download_dir") or "").strip(),
            }
            for d in (definitions or []) if isinstance(d, dict)
        ]
        if not self._definitions:
            self._definitions = [{"model_type": "Checkpoint", "download_dir": ""}]

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BACKGROUND_COLOR.name()};
                color: {TEXT_COLOR.name()};
            }}
            QLabel {{
                color: {TEXT_COLOR.name()};
            }}
            QFrame#RowCard {{
                border: 1px solid #444;
                border-radius: 6px;
                background-color: #1f1f1f;
            }}
            QPushButton {{
                background-color: {PRIMARY_COLOR.name()};
                color: white;
                border-radius: 4px;
                padding: 6px 10px;
            }}
            QPushButton:hover {{
                background-color: #9575cd;
            }}
        """)

        self._build_ui()
        self._render_rows()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Model Type Download Folders")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet(f"color: {PRIMARY_COLOR.name()};")
        layout.addWidget(title)

        info = QLabel(
            "Define a download folder for each model type. "
            "Changes are only applied when this window is closed with OK."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #aaaaaa;")
        layout.addWidget(info)

        self.rows_container = QVBoxLayout()
        self.rows_container.setSpacing(8)
        layout.addLayout(self.rows_container)

        add_frame = QFrame()
        add_frame.setObjectName("RowCard")
        add_layout = QHBoxLayout(add_frame)
        add_layout.setContentsMargins(12, 12, 12, 12)

        self.add_btn = QPushButton("+ Add Model Type Folder")
        self.add_btn.setMinimumHeight(44)
        self.add_btn.clicked.connect(self._add_entry)
        add_layout.addWidget(self.add_btn)
        layout.addWidget(add_frame)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _clear_rows(self):
        while self.rows_container.count():
            item = self.rows_container.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _render_rows(self):
        self._clear_rows()
        for idx, row in enumerate(self._definitions):
            frame = QFrame()
            frame.setObjectName("RowCard")
            r = QHBoxLayout(frame)
            r.setContentsMargins(12, 10, 12, 10)
            r.setSpacing(10)

            type_lbl = QLabel(str(row.get("model_type") or "Unknown"))
            type_lbl.setMinimumWidth(160)
            type_lbl.setStyleSheet("font-weight: bold;")
            r.addWidget(type_lbl)

            folder_lbl = QLabel(str(row.get("download_dir") or "(empty path)"))
            folder_lbl.setWordWrap(True)
            folder_lbl.setStyleSheet("color: #cfcfcf;")
            r.addWidget(folder_lbl, 1)

            edit_btn = QPushButton("Edit")
            edit_btn.clicked.connect(lambda checked=False, i=idx: self._edit_entry(i))
            r.addWidget(edit_btn)

            remove_btn = QPushButton("Remove")
            remove_btn.setStyleSheet("QPushButton { background-color: #8b0000; color: white; border-radius: 4px; padding: 6px 10px; }")
            remove_btn.clicked.connect(lambda checked=False, i=idx: self._remove_entry(i))
            r.addWidget(remove_btn)

            self.rows_container.addWidget(frame)

        used = {str(x.get("model_type") or "").strip().lower() for x in self._definitions}
        has_available = any(opt.lower() not in used for opt in MODEL_TYPE_OPTIONS)
        self.add_btn.setEnabled(has_available)

    def _available_types(self, include_current=None):
        used = {str(x.get("model_type") or "").strip().lower() for x in self._definitions}
        if include_current:
            used.discard(str(include_current).strip().lower())
        return [opt for opt in MODEL_TYPE_OPTIONS if opt.lower() not in used]

    def _add_entry(self):
        options = self._available_types()
        if not options:
            QMessageBox.information(self, "No Types Available", "All model types already have a configured entry.")
            return
        dlg = ModelPathEntryDialog(options, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self._definitions.append(dlg.get_value())
            self._render_rows()

    def _edit_entry(self, index):
        if index < 0 or index >= len(self._definitions):
            return
        current = self._definitions[index]
        options = [current.get("model_type")] + self._available_types(include_current=current.get("model_type"))
        # keep order stable and dedupe
        dedup = []
        seen = set()
        for o in options:
            key = str(o or "").strip().lower()
            if key and key not in seen:
                seen.add(key)
                dedup.append(o)

        dlg = ModelPathEntryDialog(dedup, initial=current, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self._definitions[index] = dlg.get_value()
            self._render_rows()

    def _remove_entry(self, index):
        if index < 0 or index >= len(self._definitions):
            return
        del self._definitions[index]
        if not self._definitions:
            self._definitions = [{"model_type": "Checkpoint", "download_dir": ""}]
        self._render_rows()

    def get_definitions(self):
        return [
            {
                "model_type": str(d.get("model_type") or "").strip(),
                "download_dir": str(d.get("download_dir") or "").strip(),
            }
            for d in self._definitions if isinstance(d, dict)
        ]
