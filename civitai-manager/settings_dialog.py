# settings_dialog.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QFileDialog, QDialogButtonBox, QHBoxLayout, QLabel, QComboBox,
    QListWidget, QListWidgetItem, QWidget, QAbstractItemView
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
        # Make dialog larger and resizable to accommodate new sections
        try:
            self.setMinimumSize(560, 650)
            self.resize(640, 760)
        except Exception:
            # fallback fixed size if resize APIs fail
            self.setFixedSize(640, 760)
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
        # Add input and clear button in a horizontal layout
        key_row = QHBoxLayout()
        key_row.addWidget(self.api_key_input)
        clear_btn = QPushButton("Clear API Key")
        clear_btn.setStyleSheet(f"QPushButton {{ background-color: #8b0000; color: white; padding:6px; border-radius:4px;}}")
        clear_btn.clicked.connect(self.clear_api_key)
        key_row.addWidget(clear_btn)
        api_layout.addRow("API Key:", key_row)

        self.api_key_input.setText(api_key or "")
        # Inform user where the API key is stored
        info_label = QLabel("Note: API key is stored securely in the Windows registry; exported JSON will NOT contain the key.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        api_layout.addRow(info_label)

        # Removed obsolete popular period setting (handled directly in explorer filters)
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
        
        # Tag Priority section
        tag_section = QLabel("Filename Tag Priority")
        tag_section.setFont(QFont("Segoe UI", 12, QFont.Bold))
        tag_section.setStyleSheet(f"color: {PRIMARY_COLOR.name()}; margin-top: 20px; margin-bottom: 10px;")
        layout.addWidget(tag_section)

        tag_layout = QVBoxLayout()
        self.priority_list = QListWidget()
        self.priority_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.priority_list.setDragEnabled(True)
        self.priority_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.priority_list.setStyleSheet("QListWidget { background:#2a2a2a; border:1px solid #444; } QListWidget::item { padding:4px; }")
        # populate from settings
        pri_raw = self.settings_manager.get("priority_tags", "") or ""
        for tag in [t.strip() for t in pri_raw.split(',') if t.strip()]:
            self.priority_list.addItem(QListWidgetItem(tag))
        btn_row = QHBoxLayout()
        self.add_tag_input = QLineEdit()
        self.add_tag_input.setPlaceholderText("Add tag")
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_priority_tag)
        rem_btn = QPushButton("Remove Selected")
        rem_btn.clicked.connect(self.remove_priority_tag)
        for b in (add_btn, rem_btn):
            b.setStyleSheet(f"QPushButton {{ background-color: {PRIMARY_COLOR.name()}; color:white; border-radius:4px; padding:4px 10px;}}")
        btn_row.addWidget(self.add_tag_input)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rem_btn)
        tag_layout.addWidget(QLabel("Drag to reorder. First match is used for primary tag in filenames."))
        tag_layout.addWidget(self.priority_list)
        tag_layout.addLayout(btn_row)
        layout.addLayout(tag_layout)

    # Images folder is fixed to workspace 'images' and not editable by user

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

    def browse_images_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Images Directory",
            self.images_dir_input.text()
        )
        if directory:
            self.images_dir_input.setText(directory)
        
    
    def export_history(self):
        # Implementation to export history
        pass
    
    def import_history(self):
        # Implementation to import history
        pass
    
    def save_settings(self):
        self.settings_manager.set("api_key", self.api_key_input.text())
        self.settings_manager.set("download_dir", self.download_dir_input.text())
    # popular period removed
        # priority tags
        tags = []
        for i in range(self.priority_list.count()):
            t = self.priority_list.item(i).text().strip()
            if t and t not in tags:
                tags.append(t)
        self.settings_manager.set("priority_tags", ",".join(tags))
    # images folder is fixed to workspace/images; no user setting
        self.accept()

    def clear_api_key(self):
        """Clear the API key from registry and the input field."""
        try:
            self.settings_manager.delete_api_key()
        except Exception:
            pass
        self.api_key_input.clear()

    def add_priority_tag(self):
        txt = self.add_tag_input.text().strip()
        if not txt:
            return
        # avoid duplicates
        existing = [self.priority_list.item(i).text() for i in range(self.priority_list.count())]
        if txt in existing:
            self.add_tag_input.clear()
            return
        self.priority_list.addItem(QListWidgetItem(txt))
        self.add_tag_input.clear()

    def remove_priority_tag(self):
        row = self.priority_list.currentRow()
        if row >= 0:
            it = self.priority_list.takeItem(row)
            del it