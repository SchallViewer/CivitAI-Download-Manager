# settings_dialog.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QFileDialog, QDialogButtonBox, QHBoxLayout, QLabel, QComboBox,
    QListWidget, QListWidgetItem, QWidget, QAbstractItemView
)
from PyQt5.QtGui import QIcon,QFont
from settings import SettingsManager
from constants import PRIMARY_COLOR, BACKGROUND_COLOR, TEXT_COLOR
from model_path_settings_dialog import ModelPathSettingsDialog


class SettingsDialog(QDialog):
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.model_download_paths = self.settings_manager.get_model_download_paths()
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
        label_row = QWidget()
        label_row_layout = QHBoxLayout(label_row)
        label_row_layout.setContentsMargins(0, 0, 0, 0)
        label_row_layout.setSpacing(8)
        label_row_layout.addWidget(QLabel("Download Folder:"))

        self.model_paths_button = QPushButton("Per Model Paths...")
        self.model_paths_button.clicked.connect(self.open_model_path_settings)
        self.model_paths_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {PRIMARY_COLOR.name()};
                color: white;
                padding: 6px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #9575cd;
            }}
        """)
        label_row_layout.addWidget(self.model_paths_button)
        label_row_layout.addStretch()

        download_layout.addRow(label_row, download_dir_layout)

        self.model_paths_summary = QLabel()
        self.model_paths_summary.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        self.model_paths_summary.setWordWrap(True)
        download_layout.addRow(self.model_paths_summary)
        self.refresh_model_paths_summary()
        layout.addLayout(download_layout)
        
        # Tag Priority section
        tag_section = QLabel("Filename Tag Priority & Aliases")
        tag_section.setFont(QFont("Segoe UI", 12, QFont.Bold))
        tag_section.setStyleSheet(f"color: {PRIMARY_COLOR.name()}; margin-top: 20px; margin-bottom: 10px;")
        layout.addWidget(tag_section)

        tag_layout = QVBoxLayout()
        
        # Instructions
        instruction_label = QLabel("Set tag priority and their filename aliases. Tags are matched in order, and the alias is used in the filename.")
        instruction_label.setWordWrap(True)
        instruction_label.setStyleSheet("color: #aaaaaa; font-size: 11px; margin-bottom: 10px;")
        tag_layout.addWidget(instruction_label)
        
        # Two-column layout for priority tags and aliases
        lists_layout = QHBoxLayout()
        
        # Priority Tags column
        priority_column = QVBoxLayout()
        priority_column.addWidget(QLabel("Tag Priority (drag to reorder)"))
        self.priority_list = QListWidget()
        self.priority_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.priority_list.setDragEnabled(True)
        self.priority_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.priority_list.setStyleSheet("QListWidget { background:#2a2a2a; border:1px solid #444; } QListWidget::item { padding:4px; }")
        self.priority_list.itemSelectionChanged.connect(self.sync_selection_to_aliases)
        priority_column.addWidget(self.priority_list)
        
        # Aliases column
        aliases_column = QVBoxLayout()
        aliases_column.addWidget(QLabel("Filename Aliases"))
        self.aliases_list = QListWidget()
        self.aliases_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.aliases_list.setDragEnabled(True)
        self.aliases_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.aliases_list.setStyleSheet("QListWidget { background:#2a2a2a; border:1px solid #444; } QListWidget::item { padding:4px; }")
        self.aliases_list.itemSelectionChanged.connect(self.sync_selection_to_priority)
        aliases_column.addWidget(self.aliases_list)
        
        lists_layout.addLayout(priority_column)
        lists_layout.addLayout(aliases_column)
        tag_layout.addLayout(lists_layout)
        
        # populate from settings
        pri_raw = self.settings_manager.get("priority_tags", "") or ""
        ali_raw = self.settings_manager.get("tag_aliases", "") or ""
        priority_tags = [t.strip() for t in pri_raw.split(',') if t.strip()]
        alias_tags = [t.strip() for t in ali_raw.split(',') if t.strip()]
        
        # Ensure both lists have same length, pad with defaults if needed
        while len(alias_tags) < len(priority_tags):
            alias_tags.append(priority_tags[len(alias_tags)])
        while len(priority_tags) < len(alias_tags):
            priority_tags.append(alias_tags[len(priority_tags)])
            
        for tag in priority_tags:
            self.priority_list.addItem(QListWidgetItem(tag))
        for alias in alias_tags:
            self.aliases_list.addItem(QListWidgetItem(alias))
        
        # Control buttons
        btn_row = QHBoxLayout()
        self.add_tag_input = QLineEdit()
        self.add_tag_input.setPlaceholderText("Add tag")
        self.add_alias_input = QLineEdit()
        self.add_alias_input.setPlaceholderText("Add alias")
        self.add_btn = QPushButton("Add Both")
        self.add_btn.clicked.connect(self.add_priority_tag)
        self.edit_btn = QPushButton("Edit Selected")
        self.edit_btn.clicked.connect(self.edit_priority_tag)
        self.rem_btn = QPushButton("Remove Selected")
        self.rem_btn.clicked.connect(self.remove_priority_tag)
        
        # Store original button styles
        self.normal_button_style = f"QPushButton {{ background-color: {PRIMARY_COLOR.name()}; color:white; border-radius:4px; padding:4px 10px;}}"
        self.edit_mode_style = "QPushButton { background-color: #ff8c00; color:white; border-radius:4px; padding:4px 10px;}"  # Orange
        
        for b in (self.add_btn, self.edit_btn, self.rem_btn):
            b.setStyleSheet(self.normal_button_style)
        
        btn_row.addWidget(self.add_tag_input)
        btn_row.addWidget(self.add_alias_input)
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.rem_btn)
        tag_layout.addLayout(btn_row)
        layout.addLayout(tag_layout)

    # Images folder is fixed to workspace 'images' and not editable by user

        # History Management section
        history_section = QLabel("History Management")
        history_section.setFont(QFont("Segoe UI", 12, QFont.Bold))
        history_section.setStyleSheet(f"color: {PRIMARY_COLOR.name()}; margin-top: 20px; margin-bottom: 10px;")
        layout.addWidget(history_section)
        
        # History Management actions (single recovery button)
        history_layout = QHBoxLayout()
        recover_button = QPushButton("Recover Models Data")
        recover_button.setStyleSheet(f"""
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
        # Placeholder: no logic yet, only UI wiring
        recover_button.clicked.connect(self.recover_models_data)
        history_layout.addWidget(recover_button)
        history_layout.addStretch()
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

    def open_model_path_settings(self):
        dlg = ModelPathSettingsDialog(self.model_download_paths, self)
        if dlg.exec_() == QDialog.Accepted:
            self.model_download_paths = dlg.get_definitions()
            self.refresh_model_paths_summary()

    def refresh_model_paths_summary(self):
        defs = self.model_download_paths or []
        if not defs:
            self.model_paths_summary.setText("No model-type paths configured.")
            return
        non_empty = [d for d in defs if str(d.get("download_dir") or "").strip()]
        self.model_paths_summary.setText(
            f"Configured model-type folders: {len(defs)} entries ({len(non_empty)} with valid path set)."
        )
        
    
    def export_history(self):
        # Implementation to export history
        pass
    
    def import_history(self):
        # Implementation to import history
        pass

    def recover_models_data(self):
        """Start the model recovery process"""
        from PyQt5.QtWidgets import QMessageBox
        from model_recovery import ModelRecoveryManager
        
        # Show information dialog before starting recovery
        msg = QMessageBox(self)
        msg.setWindowTitle("Model Recovery Process")
        msg.setIcon(QMessageBox.Information)
        
        # Set the main message
        msg.setText("Model Recovery Process")
        
        # Set detailed information
        detailed_info = """
<b>What this process does:</b>
• Scans your download folder for model files (.safetensors, .ckpt, .pt, .pth, .bin)
• Calculates SHA256 hash for each file to identify it uniquely
• Queries CivitAI database using the hash to recover metadata
• Downloads preview images and stores them in workspace/images folder
• Saves all recovered data to the local database

<b>What data will be recovered:</b>
• Model name, type, creator, and description
• Version information and trained words/trigger keywords
• Preview images (up to 5 per model)
• Tags, base model information, and publishing dates

<b>Important considerations:</b>
• <b>Processing time:</b> Large collections may take considerable time to process
• <b>API rate limiting:</b> Requests are throttled to avoid overloading CivitAI servers
• <b>Internet required:</b> Active connection needed for API queries and image downloads
• <b>Testing mode:</b> You can rollback all changes after completion for testing
• <b>Safe operation:</b> Only adds data, does not modify or move your model files

<b>Files that will be skipped:</b>
• Models already registered in the database
• Files that cannot be found in CivitAI's database
• Duplicate files (same hash)

Do you want to start the model recovery process?
        """
        
        msg.setDetailedText(detailed_info.strip())
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        
        # Style the message box
        msg.setStyleSheet(f"""
            QMessageBox {{
                background-color: {BACKGROUND_COLOR.name()};
                color: {TEXT_COLOR.name()};
            }}
            QMessageBox QLabel {{
                color: {TEXT_COLOR.name()};
            }}
            QPushButton {{
                background-color: {PRIMARY_COLOR.name()};
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: #9575cd;
            }}
        """)
        
        # Show the dialog and check user's choice
        reply = msg.exec_()
        
        if reply == QMessageBox.Yes:
            # User confirmed, start the recovery process
            recovery_manager = ModelRecoveryManager(self.parent())
            recovery_manager.start_recovery()
            
            # Close settings dialog after starting recovery
            self.accept()
        # If user clicked No, do nothing and stay in settings dialog
    
    def save_settings(self):
        self.settings_manager.set("api_key", self.api_key_input.text())
        self.settings_manager.set("download_dir", self.download_dir_input.text())
        self.settings_manager.set_model_download_paths(self.model_download_paths)
    # popular period removed
        # priority tags and aliases
        tags = []
        aliases = []
        for i in range(self.priority_list.count()):
            t = self.priority_list.item(i).text().strip()
            if t and t not in tags:
                tags.append(t)
        for i in range(self.aliases_list.count()):
            a = self.aliases_list.item(i).text().strip()
            if a:
                aliases.append(a)
        
        # Ensure both lists have same length
        while len(aliases) < len(tags):
            aliases.append(tags[len(aliases)])
        while len(tags) < len(aliases):
            tags.append(aliases[len(tags)])
            
        self.settings_manager.set("priority_tags", ",".join(tags))
        self.settings_manager.set("tag_aliases", ",".join(aliases))
    # images folder is fixed to workspace/images; no user setting
        self.accept()

    def clear_api_key(self):
        """Clear the API key from registry and the input field."""
        try:
            self.settings_manager.delete_api_key()
        except Exception:
            pass
        self.api_key_input.clear()

    def edit_priority_tag(self):
        """Edit the selected tag/alias pair or cancel edit mode"""
        # Check if we're already in edit mode - if so, cancel it
        if hasattr(self, '_editing_row') and self._editing_row >= 0:
            self.cancel_edit_mode()
            return
        
        row = self.priority_list.currentRow()
        if row < 0:
            return
            
        # Get current values
        current_tag = self.priority_list.item(row).text()
        current_alias = self.aliases_list.item(row).text() if row < self.aliases_list.count() else current_tag
        
        # Pre-fill input fields with current values
        self.add_tag_input.setText(current_tag)
        self.add_alias_input.setText(current_alias)
        
        # Enter edit mode
        self._editing_row = row
        self.enter_edit_mode()
    
    def enter_edit_mode(self):
        """Visual feedback for entering edit mode"""
        self.edit_btn.setText("Cancel Edit")
        self.edit_btn.setStyleSheet(self.edit_mode_style)
        self.add_btn.setText("Complete Edit")
        self.add_btn.setStyleSheet(self.edit_mode_style)
    
    def cancel_edit_mode(self):
        """Cancel edit mode and restore normal state"""
        if hasattr(self, '_editing_row'):
            del self._editing_row
        self.add_tag_input.clear()
        self.add_alias_input.clear()
        self.exit_edit_mode()
    
    def exit_edit_mode(self):
        """Visual feedback for exiting edit mode"""
        self.edit_btn.setText("Edit Selected")
        self.edit_btn.setStyleSheet(self.normal_button_style)
        self.add_btn.setText("Add Both")
        self.add_btn.setStyleSheet(self.normal_button_style)
    
    def add_priority_tag(self):
        tag_txt = self.add_tag_input.text().strip()
        alias_txt = self.add_alias_input.text().strip()
        
        if not tag_txt:
            return
        
        # Use tag as alias if no alias provided
        if not alias_txt:
            alias_txt = tag_txt
        
        # Check if we're in editing mode
        if hasattr(self, '_editing_row') and self._editing_row >= 0:
            row = self._editing_row
            # Update existing items
            self.priority_list.item(row).setText(tag_txt)
            if row < self.aliases_list.count():
                self.aliases_list.item(row).setText(alias_txt)
            else:
                # Add alias if it doesn't exist
                self.aliases_list.addItem(QListWidgetItem(alias_txt))
            
            # Clear editing mode and restore normal UI
            del self._editing_row
            self.exit_edit_mode()
        else:
            # Adding new items - check for duplicates
            existing = [self.priority_list.item(i).text() for i in range(self.priority_list.count())]
            if tag_txt in existing:
                self.add_tag_input.clear()
                self.add_alias_input.clear()
                return
                
            self.priority_list.addItem(QListWidgetItem(tag_txt))
            self.aliases_list.addItem(QListWidgetItem(alias_txt))
        
        self.add_tag_input.clear()
        self.add_alias_input.clear()

    def remove_priority_tag(self):
        row = self.priority_list.currentRow()
        if row >= 0:
            # Remove from both lists
            priority_item = self.priority_list.takeItem(row)
            alias_item = self.aliases_list.takeItem(row)
            del priority_item
            del alias_item
    
    def sync_selection_to_aliases(self):
        """Sync selection from priority list to aliases list"""
        current_row = self.priority_list.currentRow()
        if current_row >= 0 and current_row < self.aliases_list.count():
            self.aliases_list.setCurrentRow(current_row)
    
    def sync_selection_to_priority(self):
        """Sync selection from aliases list to priority list"""
        current_row = self.aliases_list.currentRow()
        if current_row >= 0 and current_row < self.priority_list.count():
            self.priority_list.setCurrentRow(current_row)