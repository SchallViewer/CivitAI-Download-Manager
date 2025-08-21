# settings_dialog.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, 
    QFileDialog, QDialogButtonBox, QHBoxLayout, QLabel,QComboBox
)
from PyQt5.QtGui import QIcon,QFont
from settings import SettingsManager
from constants import PRIMARY_COLOR, BACKGROUND_COLOR, TEXT_COLOR


class SettingsDialog(QDialog):
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle("Settings")
        self.setWindowIcon(QIcon("icons/settings.png"))
        self.setFixedSize(500, 400)
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
        layout.setSpacing(15)
        
        # API Configuration section
        api_section = QLabel("API Configuration")
        api_section.setFont(QFont("Segoe UI", 12, QFont.Bold))
        api_section.setStyleSheet(f"color: {PRIMARY_COLOR.name()}; margin-bottom: 10px;")
        layout.addWidget(api_section)
        
        # API Key
        api_layout = QFormLayout()
        api_layout.setVerticalSpacing(15)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter your Civitai API key")
        api_key = self.settings_manager.get("api_key", "")
        self.api_key_input.setText(self.settings_manager.get("api_key"))
        self.api_key_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #2a2a2a;
                color: {TEXT_COLOR.name()};
                border: 1px solid {PRIMARY_COLOR.name()};
                border-radius: 4px;
                padding: 8px;
            }}
        """)
        api_layout.addRow("API Key:", self.api_key_input)
        

        self.api_key_input.setText(api_key or "")

        # Popular period
        self.period_combo = QComboBox()
        self.period_combo.addItem("Weekly Popular", "Week")
        self.period_combo.addItem("Monthly Popular", "Month")
        self.period_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #2a2a2a;
                color: {TEXT_COLOR.name()};
                border: 1px solid {PRIMARY_COLOR.name()};
                border-radius: 4px;
                padding: 8px;
            }}
        """)
        current_period = self.settings_manager.get("popular_period", "Week")
        index = self.period_combo.findData(current_period or "week")
        if index >= 0:
            self.period_combo.setCurrentIndex(index)

        api_layout.addRow("Popular Models Period:", self.period_combo)
        layout.addLayout(api_layout)
        
        # Download Configuration section
        dl_section = QLabel("Download Configuration")
        dl_section.setFont(QFont("Segoe UI", 12, QFont.Bold))
        dl_section.setStyleSheet(f"color: {PRIMARY_COLOR.name()}; margin-top: 20px; margin-bottom: 10px;")
        layout.addWidget(dl_section)
        
        # Download Directory
        download_layout = QFormLayout()
        download_layout.setVerticalSpacing(15)
        
        download_dir_layout = QHBoxLayout()
        download_dir = self.settings_manager.get("download_dir", "")
        self.download_dir_input = QLineEdit()
        self.download_dir_input.setText(download_dir or "")
        self.download_dir_input.setText(self.settings_manager.get("download_dir"))
        self.download_dir_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #2a2a2a;
                color: {TEXT_COLOR.name()};
                border: 1px solid {PRIMARY_COLOR.name()};
                border-radius: 4px;
                padding: 8px;
            }}
        """)
        download_dir_layout.addWidget(self.download_dir_input)
        
        browse_button = QPushButton("Browse...")
        browse_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {PRIMARY_COLOR.name()};
                color: white;
                padding: 8px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #9575cd;
            }}
        """)
        browse_button.clicked.connect(self.browse_directory)
        download_dir_layout.addWidget(browse_button)
        download_layout.addRow("Download Folder:", download_dir_layout)
        layout.addLayout(download_layout)
        
        # History Management section
        history_section = QLabel("History Management")
        history_section.setFont(QFont("Segoe UI", 12, QFont.Bold))
        history_section.setStyleSheet(f"color: {PRIMARY_COLOR.name()}; margin-top: 20px; margin-bottom: 10px;")
        layout.addWidget(history_section)
        
        # Export/Import History
        history_layout = QHBoxLayout()
        export_button = QPushButton("Export History")
        export_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {PRIMARY_COLOR.name()};
                color: white;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #9575cd;
            }}
        """)
        export_button.clicked.connect(self.export_history)
        import_button = QPushButton("Import History")
        import_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #333;
                color: #ddd;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #444;
            }}
        """)
        import_button.clicked.connect(self.import_history)
        history_layout.addWidget(export_button)
        history_layout.addWidget(import_button)
        layout.addLayout(history_layout)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.setStyleSheet("""
            QDialogButtonBox {
                border-top: 1px solid #333;
                padding-top: 15px;
            }
        """)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Download Directory", 
            self.download_dir_input.text()
        )
        if directory:
            self.download_dir_input.setText(directory)
    
    def export_history(self):
        # Implementation to export history
        pass
    
    def import_history(self):
        # Implementation to import history
        pass
    
    def save_settings(self):
        self.settings_manager.set("api_key", self.api_key_input.text())
        self.settings_manager.set("download_dir", self.download_dir_input.text())
        self.settings_manager.set("popular_period", self.period_combo.currentData())
        self.accept()