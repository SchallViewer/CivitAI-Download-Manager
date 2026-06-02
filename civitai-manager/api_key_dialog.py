from PyQt5.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QLabel, QMessageBox, QDialogButtonBox
from PyQt5.QtGui import QFont
from constants import PRIMARY_COLOR, BACKGROUND_COLOR, TEXT_COLOR


class ApiKeyDialog(QDialog):
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle("API Key Manager")
        self.setMinimumWidth(520)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BACKGROUND_COLOR.name()};
                color: {TEXT_COLOR.name()};
            }}
            QLabel {{
                color: {TEXT_COLOR.name()};
            }}
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("API Key")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet(f"color: {PRIMARY_COLOR.name()};")
        layout.addWidget(title)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        layout.addWidget(self.status_label)

        form = QFormLayout()
        form.setVerticalSpacing(12)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter your Civitai API key")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #2a2a2a;
                color: {TEXT_COLOR.name()};
                border: 1px solid {PRIMARY_COLOR.name()};
                border-radius: 4px;
                padding: 8px;
            }}
        """)
        form.addRow("New API Key:", self.api_key_input)

        layout.addLayout(form)

        clear_btn = QPushButton("Clear Stored API Key")
        clear_btn.setStyleSheet("QPushButton { background-color: #8b0000; color: white; padding: 6px; border-radius: 4px; }")
        clear_btn.clicked.connect(self.clear_api_key)
        layout.addWidget(clear_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_api_key)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.refresh_status()

    def refresh_status(self):
        if self.settings_manager.has_api_key():
            self.status_label.setText("An API key is currently configured.")
        else:
            self.status_label.setText("There is no API key is currently configured.")

    def save_api_key(self):
        value = self.api_key_input.text().strip()
        if not value:
            QMessageBox.warning(self, "Missing API Key", "Please enter an API key.")
            return

        try:
            self.settings_manager.set("api_key", value)
            self.api_key_input.clear()
            QMessageBox.information(self, "Saved", "API key saved.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save API key:\n{e}")

    def clear_api_key(self):
        reply = QMessageBox.question(
            self,
            "Clear API Key",
            "Remove the stored API key from Windows Credential Manager?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            self.settings_manager.delete_api_key()
            self.api_key_input.clear()
            self.refresh_status()
            QMessageBox.information(self, "Cleared", "Stored API key was removed.")
        except Exception as e:
            QMessageBox.critical(self, "Clear Error", f"Failed to clear API key:\n{e}")
