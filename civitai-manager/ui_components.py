# ui_components.py
from PyQt5.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QFrame, QProgressBar,
    QPushButton, QSizePolicy
)
from PyQt5.QtGui import QPixmap, QFont, QColor, QPainter
from PyQt5.QtGui import QMovie
from PyQt5.QtCore import QBuffer, QByteArray
from PyQt5.QtCore import Qt, QSize, pyqtSignal

class ModelCard(QFrame):
    clicked = pyqtSignal(object)
    
    def __init__(self, model_data, parent=None):
        super().__init__(parent)
        self.model_data = model_data
        self.setFixedSize(240, 300)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            ModelCard {{
                border: 1px solid {QColor("#444").name()};
                border-radius: 8px;
                background-color: {QColor("#333").name()};
            }}
            ModelCard:hover {{
                background-color: #3a3a3a;
                border-color: #666;
            }}
        """)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Image placeholder
        self.image_label = QLabel()
        self.image_label.setFixedSize(220, 180)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet(f"""
            background-color: {QColor("#222").name()}; 
            border-radius: 4px;
            color: {QColor("#888").name()};
        """)
        self.image_label.setText("Loading image...")
        layout.addWidget(self.image_label)
        
        # Model name
        name_label = QLabel(self.model_data.get('name', 'Untitled'))
        name_label.setStyleSheet(f"""
            font-weight: bold; 
            font-size: 12pt; 
            color: {QColor("#e0e0e0").name()};
        """)
        name_label.setWordWrap(True)
        layout.addWidget(name_label)
        
        # Tags and type
        tags_layout = QHBoxLayout()
        tags_layout.setSpacing(6)
        
        # Model type tag (Checkpoint, LoRA, Embedding, etc.)
        raw_type = self.model_data.get('type') or self.model_data.get('modelType') or self.model_data.get('model_type') or 'Unknown'
        type_map = {
            'LORA': 'LoRA',
            'Embeddings': 'Embedding',
            'TextualInversion': 'Textual Inversion',
            'Hypernetwork': 'Hypernetwork',
            'Checkpoint': 'Checkpoint',
            'Aesthetic': 'Aesthetic Gradient',
            'Textures': 'Textures'
        }
        type_label = type_map.get(raw_type, str(raw_type))
        type_tag = QLabel(type_label)
        type_tag.setStyleSheet(f"""
            background-color: {QColor('#555').name()};
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 9pt;
        """)
        tags_layout.addWidget(type_tag)

        # Base model tag (if provided in version or model metadata)
        base_model_name = None
        # try to read from model_data top-level
        if isinstance(self.model_data.get('baseModel'), str):
            base_model_name = self.model_data.get('baseModel')
        # or try to infer from first version
        versions = self.model_data.get('modelVersions') or self.model_data.get('versions') or []
        if not base_model_name and versions and isinstance(versions[0], dict):
            bm = versions[0].get('baseModel') or versions[0].get('base_model')
            if isinstance(bm, str):
                base_model_name = bm
        if base_model_name:
            base_tag = QLabel(base_model_name)
            base_tag.setStyleSheet(f"""
                background-color: {QColor('#4caf50').name()};
                color: white;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 9pt;
            """)
            tags_layout.addWidget(base_tag)

        # Main tag (choose by priority: meme, concept, character, style, clothing, pose)
        tags = self.model_data.get('tags') or []
        main_tag_name = 'General'
        if tags:
            # Build list of tag names preserving original casing
            names = []
            for t in tags:
                if isinstance(t, dict):
                    n = t.get('name') or ''
                else:
                    n = str(t or '')
                if n:
                    names.append(n)

            # Priority list (left = higher priority)
            priority = ['meme', 'concept', 'character', 'style', 'clothing', 'pose']
            chosen = None
            # map lowercased to original for case-insensitive match
            lower_map = {n.lower(): n for n in names}
            for p in priority:
                if p in lower_map:
                    chosen = lower_map[p]
                    break

            # fallback to first tag if no priority matched
            if not chosen and names:
                chosen = names[0]

            if chosen:
                main_tag_name = chosen

        tag = QLabel(main_tag_name)
        tag.setStyleSheet(f"""
            background-color: {QColor('#7e57c2').name()};
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 9pt;
        """)
        tags_layout.addWidget(tag)
        tags_layout.addStretch()
        layout.addLayout(tags_layout)
    
    def set_image(self, pixmap):
        # Clear placeholder text and set pixmap if available
        try:
            self.image_label.setText("")
            if pixmap and not pixmap.isNull():
                self.image_label.setPixmap(
                    pixmap.scaled(220, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
        except Exception:
            # Fallback: leave placeholder text
            pass

    def set_image_from_bytes(self, data_bytes):
        """Accept raw image bytes. If animated (GIF), use QMovie; otherwise display a QPixmap."""
        try:
            # Try to detect GIF animation by magic bytes. For cards we skip animated images
            if data_bytes[:6] in (b'GIF87a', b'GIF89a'):
                # Indicate to caller that this was animated and not rendered
                return False

            # Fallback to static pixmap
            pixmap = QPixmap()
            pixmap.loadFromData(data_bytes)
            if not pixmap.isNull():
                self.set_image(pixmap)
                return True
            return False
        except Exception:
            return False
    
    def mousePressEvent(self, event):
        # Emit the model data when clicked
        self.clicked.emit(self.model_data)
        super().mousePressEvent(event)

class DownloadProgressWidget(QWidget):
    cancel_requested = pyqtSignal(str)
    def __init__(self, task, download_manager=None, parent=None):
        super().__init__(parent)
        self.task = task
        self.download_manager = download_manager
        self.init_ui()
        self.connect_signals()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # File info
        name_label = QLabel(self.task.file_name)
        name_label.setStyleSheet("font-weight: bold; color: #ddd;")
        layout.addWidget(name_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {QColor("#444").name()};
                border-radius: 4px;
                background-color: {QColor("#2a2a2a").name()};
                height: 12px;
            }}
            QProgressBar::chunk {{
                background-color: {QColor("#7e57c2").name()};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.progress_bar)
        
        # Status and actions
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("Starting...")
        self.status_label.setStyleSheet("color: #aaa; font-size: 10pt;")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {QColor("#5a5a5a").name()};
                color: {QColor("#ddd").name()};
                padding: 2px 8px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {QColor("#6a6a6a").name()};
            }}
        """)
        self.cancel_button.setFixedSize(60, 22)
        self.cancel_button.clicked.connect(self.cancel_download)
        status_layout.addWidget(self.cancel_button)
        
        layout.addLayout(status_layout)
    
    def connect_signals(self):
        self.task.signals.progress.connect(self.update_progress)
        self.task.signals.completed.connect(self.download_completed)
        self.task.signals.error.connect(self.download_error)
        
        # Connect to download manager phase signals if available
        if self.download_manager:
            try:
                self.download_manager.download_file_completed.connect(self.file_download_completed)
                self.download_manager.download_gathering_images.connect(self.gathering_images)
                self.download_manager.download_fully_completed.connect(self.fully_completed)
            except Exception:
                pass
    
    def update_progress(self, file_name, received, total):
        if file_name == self.task.file_name:
            percent = int((received / total) * 100) if total > 0 else 0
            self.progress_bar.setValue(percent)
            size_mb = received / 1024 / 1024
            total_mb = total / 1024 / 1024
            self.status_label.setText(f"Downloading: {percent}% ({size_mb:.1f}/{total_mb:.1f} MB)")
    
    def download_completed(self, file_name, file_path, file_size):
        if file_name == self.task.file_name:
            # Don't mark as completed yet - wait for post-processing
            self.status_label.setText("File downloaded - Gathering images...")
            self.progress_bar.setValue(100)
            
    def file_download_completed(self, file_name):
        if file_name == self.task.file_name:
            self.status_label.setText("File downloaded - Gathering images...")
            self.progress_bar.setValue(100)
            
    def gathering_images(self, file_name):
        if file_name == self.task.file_name:
            self.status_label.setText("Gathering images...")
            self.progress_bar.setRange(0, 0)  # Indeterminate progress
            
    def fully_completed(self, file_name):
        if file_name == self.task.file_name:
            self.status_label.setText("Completed")
            self.progress_bar.setRange(0, 100)  # Back to normal range
            self.progress_bar.setValue(100)
            self.cancel_button.setVisible(False)
    
    def download_error(self, file_name, error):
        if file_name == self.task.file_name:
            self.status_label.setText(f"Error: {error}")
            self.cancel_button.setText("Close")
    
    def cancel_download(self):
        # emit a cancel request so the manager can update queue/active lists
        try:
            self.cancel_requested.emit(self.task.file_name)
        except Exception:
            pass
        # also call task.cancel() to stop the running download
        try:
            self.task.cancel()
        except Exception:
            pass
        self.status_label.setText("Cancelled")
        self.cancel_button.setVisible(False)