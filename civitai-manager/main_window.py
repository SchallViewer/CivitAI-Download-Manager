# main_window.py
import os
import re
import sys
import json
import math
import threading
import requests
from datetime import datetime
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QListWidget, QListWidgetItem, QScrollArea, QToolBar, QAction, QStatusBar,
    QFrame, QSizePolicy, QLabel, QFileDialog, QMessageBox, QGridLayout,
    QTreeWidget, QTreeWidgetItem, QGroupBox, QPushButton, QLineEdit, QComboBox,
    QProgressBar, QTabWidget, QTextEdit, QSizePolicy, QSpacerItem, QDialog, QCheckBox, QDialogButtonBox
)
from PyQt5.QtGui import (
    QIcon, QFont, QColor, QPalette, QBrush, QPixmap, QImage, QPainter, 
    QDesktopServices, QStandardItemModel, QStandardItem
)
from PyQt5.QtCore import (
    Qt, QSize, QTimer, QUrl, QThread, pyqtSignal, QObject, QByteArray,
    QBuffer, QRectF
)
from PyQt5.QtWidgets import QSystemTrayIcon
from PyQt5.QtGui import QMovie
from PyQt5.QtSql import QSqlDatabase, QSqlQuery, QSqlTableModel
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import QGraphicsColorizeEffect
from PyQt5.QtCore import QPropertyAnimation, QSequentialAnimationGroup

from ui_components import ModelCard, DownloadProgressWidget
from ui_helpers import ImageLoaderThread, FileSelectionDialog
from api import CivitaiAPI
from database import DatabaseManager
from download_manager import DownloadManager, DownloadTask
from settings import SettingsManager
from settings_dialog import SettingsDialog
from constants import (
    PRIMARY_COLOR, SECONDARY_COLOR, BACKGROUND_COLOR, CARD_BACKGROUND,
    TEXT_COLOR, SECONDARY_TEXT, ACCENT_COLOR, API_BASE_URL
)
from window_parts.details_panel import DetailsPanelBuilder
from window_parts.downloads_panel import DownloadsPanelBuilder
from window_parts.history_panel import HistoryPanelBuilder
from window_parts.downloaded_explorer_panel import DownloadedExplorerBuilder

## Moved ImageLoaderThread and FileSelectionDialog to ui_helpers.py

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Civitai Download Manager")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(1000, 700)
        
        # Apply Civitai color palette
        palette = self.palette()
        palette.setColor(QPalette.Window, BACKGROUND_COLOR)
        palette.setColor(QPalette.WindowText, TEXT_COLOR)
        palette.setColor(QPalette.Base, CARD_BACKGROUND)
        palette.setColor(QPalette.AlternateBase, BACKGROUND_COLOR)
        palette.setColor(QPalette.ToolTipBase, PRIMARY_COLOR)
        palette.setColor(QPalette.ToolTipText, TEXT_COLOR)
        palette.setColor(QPalette.Text, TEXT_COLOR)
        palette.setColor(QPalette.Button, PRIMARY_COLOR)
        palette.setColor(QPalette.ButtonText, TEXT_COLOR)
        palette.setColor(QPalette.BrightText, SECONDARY_COLOR)
        palette.setColor(QPalette.Highlight, PRIMARY_COLOR)
        palette.setColor(QPalette.HighlightedText, TEXT_COLOR)
        self.setPalette(palette)
        
        # Initialize modules
        self.settings_manager = SettingsManager()
        self.db_manager = DatabaseManager()
        self.api_key = self.settings_manager.get("api_key")
        self.api = CivitaiAPI(api_key=self.api_key)
        self.download_manager = DownloadManager(self.db_manager)
        # subscribe to download manager changes so UI can refresh
        try:
            self.download_manager.downloads_changed.connect(self.update_downloads_panel)
            self.download_manager.download_started.connect(self._notify_download_started)
            self.download_manager.download_queued.connect(self._notify_download_queued)
            # show noticeable message boxes when a download is started or queued
            try:
                self.download_manager.download_started.connect(self._modal_download_started)
                self.download_manager.download_queued.connect(self._modal_download_queued)
            except Exception:
                pass
        except Exception:
            pass
        self.current_model = None
        self.current_version = None
        self.image_loader_threads = []
        self.download_tasks = {}
        # track attempted image URLs per card/target to avoid infinite retries
        self.card_image_attempts = {}
        self.details_image_attempts = set()
        # details panel carousel state
        self.details_images_urls = []
        self.details_image_index = 0
        self.model_page = 1
        self.model_has_more = True
        # cache last search metadata (list of model_data dicts)
        self._search_cache = []

        # Setup UI
        self.init_ui()
        self.init_connections()

        # Load initial data only if user enabled auto-load in settings
        try:
            if self.settings_manager.get("auto_load_popular", False):
                self.load_popular_models()
        except Exception:
            # keep conservative default: do not auto-load models
            pass

        # Check API key and show warning if needed
        if not self.api_key:
            QTimer.singleShot(500, self.show_api_key_warning)
        
        # Create a tray icon for notifications
        try:
            self.tray = QSystemTrayIcon(self)
            # Try to reuse app icon if available
            app_icon = QIcon()
            try:
                app_icon = self.windowIcon() or QIcon()
            except Exception:
                pass
            if not app_icon.isNull():
                self.tray.setIcon(app_icon)
            else:
                self.tray.setIcon(QIcon())
            self.tray.setVisible(True)
        except Exception:
            self.tray = None

    def _notify_download_started(self, file_name: str):
        try:
            msg = f"Downloading: {file_name}"
            self.status_bar.showMessage(msg, 5000)
            if getattr(self, 'tray', None) and isinstance(self.tray, QSystemTrayIcon):
                self.tray.showMessage("Civitai Manager", msg, QSystemTrayIcon.Information, 5000)
        except Exception:
            pass

    def _notify_download_queued(self, file_name: str):
        try:
            msg = f"Queued: {file_name} (waiting for a free slot)"
            self.status_bar.showMessage(msg, 5000)
            if getattr(self, 'tray', None) and isinstance(self.tray, QSystemTrayIcon):
                self.tray.showMessage("Civitai Manager", msg, QSystemTrayIcon.Information, 5000)
        except Exception:
            pass

    def _modal_download_started(self, file_name: str):
        try:
            # Non-blocking information dialog that is still clearly visible
            QMessageBox.information(self, "Download Started", f"The model file is now downloading:\n\n{file_name}", QMessageBox.Ok)
        except Exception:
            pass

    def _modal_download_queued(self, file_name: str):
        try:
            QMessageBox.information(self, "Download Queued", f"The model file was queued and will start when a slot is free:\n\n{file_name}", QMessageBox.Ok)
        except Exception:
            pass
    
    def init_ui(self):
        # Create main central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create toolbar with Civitai style
        self.create_toolbar()
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setStyleSheet(f"""
            QStatusBar {{
                background-color: {BACKGROUND_COLOR.name()};
                color: {SECONDARY_TEXT.name()};
                border-top: 1px solid {PRIMARY_COLOR.name()};
            }}
        """)
        
        # Create main splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {PRIMARY_COLOR.name()}; }}")
        self.splitter = splitter  # keep reference
        main_layout.addWidget(splitter)
        
        # Left panel - Model list
        self.model_list_container = QWidget()
        model_list_layout = QVBoxLayout(self.model_list_container)
        model_list_layout.setContentsMargins(15, 15, 15, 15)
        model_list_layout.setSpacing(15)
        
        # Title with gradient effect
        self.title_container = QWidget()
        self.title_container.setStyleSheet(f"""
            background-color: {PRIMARY_COLOR.name()};
            border-radius: 6px;
            padding: 10px;
        """)
        title_layout = QHBoxLayout(self.title_container)
        self.title_label = QLabel("Model Explorer")
        self.title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.title_label.setStyleSheet(f"color: {TEXT_COLOR.name()};")
        title_layout.addWidget(self.title_label)
        model_list_layout.addWidget(self.title_container)
        
        # Search bar with modern style
        search_container = QWidget()
        search_container.setStyleSheet(f"""
            background-color: {CARD_BACKGROUND.name()};
            border-radius: 6px;
            padding: 10px;
        """)
        search_layout = QHBoxLayout(search_container)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search models...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {BACKGROUND_COLOR.name()};
                color: {TEXT_COLOR.name()};
                border: 1px solid {PRIMARY_COLOR.name()};
                border-radius: 4px;
                padding: 8px;
                font-size: 12pt;
            }}
        """)
        search_layout.addWidget(self.search_input)
        
        # Model type filter
        self.model_type_combo = QComboBox()
        self.model_type_combo.addItem("All Models", "all")
        self.model_type_combo.addItem("Checkpoints", "Checkpoint")
        self.model_type_combo.addItem("LoRAs", "LORA")
        self.model_type_combo.addItem("Textures", "Textures")  # Keep consistent with API map
        self.model_type_combo.addItem("Hypernetworks", "Hypernetwork")
        self.model_type_combo.addItem("Embeddings", "TextualInversion")
        self.model_type_combo.addItem("Aesthetic Gradients", "AestheticGradient")
        # Base model filter (SD 1.5, Illustrious, SDXL, Pony, NoobAI, etc.)
        self.base_model_combo = QComboBox()
        self.base_model_combo.addItem("Any Base", None)
        self.base_model_combo.addItem("SD 1.5", "SD 1.5")
        self.base_model_combo.addItem("Illustrious", "illustrious")
        self.base_model_combo.addItem("SDXL", "SDXL 1.0")
        self.base_model_combo.addItem("Pony", "pony")
        self.base_model_combo.addItem("NoobAI (NAI)", "NoobAI")
        # Only the search input lives in the search bar to maximize space
        search_layout.addWidget(self.search_input)
        search_layout.setStretch(0, 3)
        model_list_layout.addWidget(search_container)

        # Query log bar (small) to show the last query parameters sent
        self.query_log_label = QLabel("")
        self.query_log_label.setStyleSheet(f"color: {SECONDARY_TEXT.name()}; font-family: Consolas, 'Courier New'; font-size: 9pt; padding: 4px;")
        model_list_layout.addWidget(self.query_log_label)

        # Filters bar (separate row so it doesn't steal space from the search input)
        filters_container = QWidget()
        filters_layout = QHBoxLayout(filters_container)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(8)

        # Style the existing combos consistently
        combo_style = f"""
            QComboBox {{
                background-color: {BACKGROUND_COLOR.name()};
                color: {TEXT_COLOR.name()};
                border: 1px solid {PRIMARY_COLOR.name()};
                border-radius: 4px;
                padding: 6px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
        """

        self.model_type_combo.setStyleSheet(combo_style)
        self.base_model_combo.setStyleSheet(combo_style)

        filters_layout.addWidget(self.model_type_combo)
        filters_layout.addWidget(self.base_model_combo)

        # Sorting options
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Relevance", None)
        self.sort_combo.addItem("Newest", "Newest")
        self.sort_combo.addItem("Most Downloaded", "Most Downloaded")
        self.sort_combo.addItem("Most Liked", "MostLiked")
        self.sort_combo.setStyleSheet(combo_style)
        filters_layout.addWidget(self.sort_combo)

        # Time period filter for popular/sort (week/month/year)
        self.period_combo = QComboBox()
        self.period_combo.addItem("Any", None)
        self.period_combo.addItem("Week", "Week")
        self.period_combo.addItem("Month", "Month")
        self.period_combo.addItem("Year", "Year")
        self.period_combo.setStyleSheet(combo_style)
        filters_layout.addWidget(self.period_combo)

        # NSFW checkbox (include NSFW when checked)
        from PyQt5.QtWidgets import QCheckBox
        self.nsfw_checkbox = QCheckBox("Include NSFW")
        self.nsfw_checkbox.setStyleSheet(f"color: {TEXT_COLOR.name()}; padding: 6px;")
        filters_layout.addWidget(self.nsfw_checkbox)

        filters_layout.addStretch()
        model_list_layout.addWidget(filters_container)

        # Model ID quick-load input
        id_container = QWidget()
        id_layout = QHBoxLayout(id_container)
        id_layout.setContentsMargins(0, 8, 0, 8)
        id_layout.setSpacing(8)
        self.model_id_input = QLineEdit()
        self.model_id_input.setPlaceholderText("Load by Model ID")
        self.model_id_input.setStyleSheet(
            f"background-color: {BACKGROUND_COLOR.name()}; color: {TEXT_COLOR.name()}; "
            f"border: 1px solid {PRIMARY_COLOR.name()}; padding: 6px;"
        )
        id_layout.addWidget(self.model_id_input)
        self.model_id_btn = QPushButton("Load")
        self.model_id_btn.setToolTip("Load model details by ID")
        self.model_id_btn.clicked.connect(self.load_model_by_id)
        id_layout.addWidget(self.model_id_btn)
        model_list_layout.addWidget(id_container)

        # Model grid scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(f"background-color: {BACKGROUND_COLOR.name()}; border: none;")
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.check_scroll)

        self.model_grid_container = QWidget()
        self.model_grid_layout = QGridLayout(self.model_grid_container)
        self.model_grid_layout.setAlignment(Qt.AlignTop)
        self.model_grid_layout.setContentsMargins(5, 5, 5, 5)
        self.model_grid_layout.setSpacing(15)
        # Responsive columns: we'll compute column count dynamically

        self.scroll_area.setWidget(self.model_grid_container)
        model_list_layout.addWidget(self.scroll_area)

        # keep list of created card widgets so we can reflow on resize
        self.model_cards = []

        splitter.addWidget(self.model_list_container)
        
        # Right panel - Details and downloads
        self.right_panel = QStackedWidget()
        self.right_panel.setStyleSheet(f"""
            QStackedWidget {{
                background-color: {BACKGROUND_COLOR.name()};
                border-left: 1px solid {PRIMARY_COLOR.name()};
            }}
        """)
        splitter.addWidget(self.right_panel)

        # Initialize panels
        self.create_model_details_panel()
        self.create_download_manager_panel()
        self.create_history_panel()
        self.create_downloaded_explorer_panel()
        self.create_welcome_panel()

        # Set initial sizes
        splitter.setSizes([400, 800])
        # Enforce fixed width for right panel (~740px) while letting only left panel flex
        try:
            fixed_width = 660
            self.right_panel.setMinimumWidth(fixed_width)
            self.right_panel.setMaximumWidth(fixed_width)
            # Ensure left panel has a reasonable minimum
            self.model_list_container.setMinimumWidth(320)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 0)
            # Remove any previous splitterMoved handlers risking recursion
            try:
                splitter.splitterMoved.disconnect()
            except Exception:
                pass
        except Exception:
            pass

        # Show welcome panel initially
        self.right_panel.setCurrentIndex(3)

    def _extract_image_url(self, model):
        """Return the best available image URL from a model dict or None."""
        if not model or not isinstance(model, dict):
            return None

        # Common field used elsewhere
        if model.get('firstImageUrl'):
            return model.get('firstImageUrl')

        if model.get('imageUrl'):
            return model.get('imageUrl')

        # images can be list of dicts or strings - prefer static images and skip videos
        def is_video_url(u):
            if not u or not isinstance(u, str):
                return False
            low = u.lower()
            for ext in ('.mp4', '.webm', '.mov', '.mkv', '.avi'):
                if low.endswith(ext) or ext in low:
                    return True
            return False

        images = model.get('images') or []
        if images:
            for first in images:
                if isinstance(first, dict):
                    url = first.get('url') or first.get('thumbnail')
                else:
                    url = first if isinstance(first, str) else None
                if url and not is_video_url(url):
                    return url

        # try modelVersions -> images
        versions = model.get('modelVersions') or model.get('versions') or []
        if versions and isinstance(versions[0], dict):
            vimgs = versions[0].get('images') or []
            for fv in vimgs:
                if isinstance(fv, dict):
                    url = fv.get('url') or fv.get('thumbnail')
                else:
                    url = fv if isinstance(fv, str) else None
                if url and not is_video_url(url):
                    return url

        return None

    def _matches_base_model(self, model, base_model):
        """Return True if model or any of its versions declare the given base_model."""
        try:
            if not base_model:
                return True
            bm = model.get('baseModel') or model.get('base_model')
            if isinstance(bm, str) and bm.lower() == str(base_model).lower():
                return True
            versions = model.get('modelVersions') or model.get('versions') or []
            for v in versions:
                if not isinstance(v, dict):
                    continue
                vb = v.get('baseModel') or v.get('base_model')
                if isinstance(vb, str) and vb.lower() == str(base_model).lower():
                    return True
        except Exception:
            pass
        return False

    def _safe_get_number(self, d, keys, default=0):
        """Return first numeric-like value found in dict d for any key in keys."""
        if not d or not isinstance(d, dict):
            return default
        for k in keys:
            v = d.get(k)
            if isinstance(v, (int, float)):
                return v
            try:
                if v is not None:
                    return int(v)
            except Exception:
                continue
        return default

    def _extract_date(self, d, keys):
        """Return first non-empty ISO-like date string for keys or empty string."""
        if not d or not isinstance(d, dict):
            return ''
        for k in keys:
            v = d.get(k)
            if isinstance(v, str) and v:
                return v
        return ''
    
    def create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setStyleSheet(f"""
            QToolBar {{
                background-color: {BACKGROUND_COLOR.name()};
                border-bottom: 1px solid {PRIMARY_COLOR.name()};
                padding: 5px;
            }}
        """)
        self.addToolBar(toolbar)

        # Navigation actions
        self.search_action = QAction(QIcon("icons/search.png"), "Search", self)
        self.downloads_action = QAction(QIcon("icons/downloads.png"), "Downloads", self)
        self.history_action = QAction(QIcon("icons/history.png"), "History", self)
        # note: file name is 'setting.png' in icons folder
        self.settings_action = QAction(QIcon("icons/setting.png"), "Settings", self)
        # use the available image name 'donwloads_explorer.png' (typo in file name kept)
        self.downloaded_explorer_action = QAction(QIcon("icons/donwloads_explorer.png"), "Downloaded Explorer", self)
        self.downloaded_explorer_action.setToolTip("Switch to Downloaded Model Explorer")

        toolbar.addAction(self.search_action)
        toolbar.addAction(self.downloads_action)
        toolbar.addAction(self.downloaded_explorer_action)
        toolbar.addAction(self.history_action)
        toolbar.addSeparator()
        toolbar.addAction(self.settings_action)
    
    def create_welcome_panel(self):
        self.welcome_panel = QWidget()
        layout = QVBoxLayout(self.welcome_panel)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)
        
        # Welcome message
        welcome_label = QLabel("Civitai Download Manager")
        welcome_label.setFont(QFont("Segoe UI", 24, QFont.Bold))
        welcome_label.setStyleSheet(f"color: {PRIMARY_COLOR.name()}; margin-bottom: 30px;")
        layout.addWidget(welcome_label, alignment=Qt.AlignCenter)
        
        # Info text
        info_label = QLabel(
            "Welcome to the Civitai Download Manager!\n\n"
            "To get started, search for models on the left panel or click below to\n"
            "see the most popular models this week.\n\n"
            "You can configure your API key and download settings using the gear icon."
        )
        info_label.setFont(QFont("Segoe UI", 12))
        info_label.setStyleSheet(f"color: {TEXT_COLOR.name()}; margin-bottom: 30px;")
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label, alignment=Qt.AlignCenter)
        
        # Popular models button
        popular_btn = QPushButton("Show Popular Models")
        popular_btn.setFont(QFont("Segoe UI", 12))
        popular_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PRIMARY_COLOR.name()};
                color: white;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #9575cd;
            }}
        """)
        popular_btn.setFixedSize(200, 50)
        popular_btn.clicked.connect(self.load_popular_models)
        layout.addWidget(popular_btn, alignment=Qt.AlignCenter)
        
        # Spacer
        layout.addStretch()
        
        self.right_panel.addWidget(self.welcome_panel)
    
    def create_model_details_panel(self):
        # Build details panel using a helper to keep this file smaller
        DetailsPanelBuilder(self).build()
    
    def create_download_manager_panel(self):
        DownloadsPanelBuilder(self).build()
    
    def create_history_panel(self):
        HistoryPanelBuilder(self).build()

    def create_downloaded_explorer_panel(self):
        DownloadedExplorerBuilder(self).build()

    def show_downloaded_explorer(self):
        # Show downloaded models in the left "Model Explorer" grid (replace search results view)
        # This makes the downloaded explorer occupy the same space as the search/grid panel
        # record the previous left view so we can cache search results only when
        # we are switching away from the 'search' view
        prev_view = getattr(self, 'current_left_view', 'search')

        # before changing view, cache up to 21 current search cards' metadata
        try:
            # only cache when previous view was search
            if prev_view == 'search' and getattr(self, 'model_cards', None):
                cached = []
                for c in self.model_cards[:21]:
                    try:
                        md = getattr(c, 'model_data', None) or {}
                        cached.append(md)
                    except Exception:
                        continue
                self._search_cache = cached
        except Exception:
            pass

        # now mark the current view as downloaded
        try:
            self.current_left_view = 'downloaded'
        except Exception:
            self.current_left_view = 'downloaded'

        # update title and background to indicate downloaded mode
        try:
            self.title_label.setText("Downloaded Models")
            # subtle darker background for downloaded explorer
            self.title_container.setStyleSheet(f"background-color: {CARD_BACKGROUND.name()}; border-radius: 6px; padding: 10px;")
        except Exception:
            pass

        # load downloaded models into the left grid
        try:
            # disable search pagination while viewing downloaded explorer to avoid mixing results
            try:
                self.model_has_more = False
                self.search_cursor = None
                self.model_page = 0
            except Exception:
                pass
            self.load_downloaded_models_left()
            self.status_bar.showMessage("Showing downloaded models")
        except Exception as e:
            print("Error showing downloaded explorer in left pane:", e)
            # fallback to the original right-panel explorer if left-loading fails
            try:
                self.load_downloaded_models()
                idx = None
                for i in range(self.right_panel.count()):
                    if self.right_panel.widget(i) is self.downloaded_explorer_panel:
                        idx = i
                        break
                if idx is not None:
                    self.right_panel.setCurrentIndex(idx)
            except Exception:
                pass

        # Note: details panel behavior unchanged; clicking a card will still open details on the right.

    def load_downloaded_models(self):
        # Clear existing
        for i in reversed(range(self.downloaded_grid_layout.count())):
            w = self.downloaded_grid_layout.itemAt(i).widget() if self.downloaded_grid_layout.itemAt(i) else None
            if w:
                w.setParent(None)

        models = []
        try:
            models = self.db_manager.get_downloaded_models()
        except Exception:
            models = []

        # Aggregate by model_id so multiple downloaded versions of the same model
        # result in a single card with a list of downloaded version ids stored on
        # the metadata under the key '_downloaded_versions'. This avoids showing
        # duplicate cards per-version.
        agg = {}
        for item in models:
            # metadata now comes from normalized 'models' table (stored under 'metadata')
            model_data = item.get('metadata') or {}
            # include url into metadata for convenience
            try:
                if item.get('model_id') and (not model_data.get('id')):
                    model_data['id'] = item.get('model_id')
                if item.get('model_name') and (not model_data.get('name')):
                    model_data['name'] = item.get('model_name')
            except Exception:
                pass
            model_id = item.get('model_id') or model_data.get('id')
            if model_id is None:
                # fallback: use DB id to keep item unique
                key = f"db_{item.get('id')}"
            else:
                key = f"m_{model_id}"

            if key not in agg:
                # clone metadata and attach versions list
                md = dict(model_data)
                try:
                    if model_id and 'modelVersions' not in md and hasattr(self, 'db_manager'):
                        md['modelVersions'] = self.db_manager.get_model_versions(model_id)
                except Exception:
                    pass
                md['_db_id'] = item.get('id')
                md['_downloaded_versions'] = [item.get('version_id')] if item.get('version_id') else []
                md['_images'] = item.get('images') or []
                agg[key] = md
            else:
                if item.get('version_id'):
                    agg[key]['_downloaded_versions'].append(item.get('version_id'))
                # extend images list
                for im in (item.get('images') or []):
                    if im not in agg[key]['_images']:
                        agg[key]['_images'].append(im)

        # Render aggregated cards
        for i, (k, md) in enumerate(agg.items()):
            card = ModelCard(md)
            card.clicked.connect(self.show_downloaded_model_details)
            imgs = md.get('_images') or []
            if imgs:
                try:
                    pix = QPixmap(imgs[0])
                    if not pix.isNull():
                        card.set_image(pix)
                except Exception:
                    pass
            row = i // 4
            col = i % 4
            self.downloaded_grid_layout.addWidget(card, row, col)

    def load_downloaded_models_left(self):
        """Load downloaded models into the left-hand model grid (replacing search results)."""
        # Clear existing left grid widgets and internal card list
        try:
            # Remove widgets from the model grid layout
            while self.model_grid_layout.count():
                child = self.model_grid_layout.takeAt(0)
                if child and child.widget():
                        child.widget().setParent(None) if child.widget() else None
            self.model_cards = []

            models = self.db_manager.get_downloaded_models() or []
        except Exception as e:
            print("Error fetching downloaded models:", e)
            models = []

        for i, item in enumerate(models):
            model_data = item.get('metadata') or {}
            try:
                if item.get('model_id') and (not model_data.get('id')):
                    model_data['id'] = item.get('model_id')
                if item.get('model_name') and (not model_data.get('name')):
                    model_data['name'] = item.get('model_name')
            except Exception:
                pass
            # aggregate by model_id to avoid duplicate cards per-version
            model_id = item.get('model_id') or model_data.get('id')
            if not hasattr(self, '_left_agg_downloaded'):
                self._left_agg_downloaded = {}
            key = f"m_{model_id}" if model_id is not None else f"db_{item.get('id')}"
            if key not in self._left_agg_downloaded:
                md = dict(model_data)
                # attach versions list for offline/imported entries
                try:
                    if model_id and 'modelVersions' not in md and hasattr(self, 'db_manager'):
                        md['modelVersions'] = self.db_manager.get_model_versions(model_id)
                except Exception:
                    pass
                md['_db_id'] = item.get('id')
                md['_downloaded_versions'] = [item.get('version_id')] if item.get('version_id') else []
                md['_images'] = item.get('images') or []
                self._left_agg_downloaded[key] = md
            else:
                if item.get('version_id'):
                    self._left_agg_downloaded[key]['_downloaded_versions'].append(item.get('version_id'))
                for im in (item.get('images') or []):
                    if im not in self._left_agg_downloaded[key]['_images']:
                        self._left_agg_downloaded[key]['_images'].append(im)

        # create cards from aggregated entries
        # Build map of models with any Missing entries to highlight
        missing_map = {}
        try:
            if hasattr(self, 'db_manager'):
                missing_map = self.db_manager.get_missing_status_map() or {}
        except Exception:
            missing_map = {}

        for k, md in (getattr(self, '_left_agg_downloaded', {}) or {}).items():
            card = ModelCard(md)
            card.clicked.connect(self.show_downloaded_model_details)
            imgs = md.get('_images') or []
            if imgs:
                try:
                    pix = QPixmap(imgs[0])
                    if not pix.isNull():
                        card.set_image(pix)
                except Exception:
                    pass
            # Highlight if Missing
            try:
                mid = md.get('id') or md.get('model_id') or md.get('_db_id')
                if mid in missing_map:
                    card.setStyleSheet(card.styleSheet() + '\nModelCard { background-color: #664; border: 2px solid #ffeb3b; }')
            except Exception:
                pass
            self.model_cards.append(card)

        # place into grid
        self.relayout_model_cards()

    def show_downloaded_model_details(self, model_data):
        # model_data is the metadata dict; show in details panel but disable download button
        try:
            # Mark that we're routing through downloaded-explorer so show_model_details
            # can record 'last details' source appropriately
            try:
                self._incoming_show_from_downloaded = True
            except Exception:
                pass
            # Use existing details UI but suppress its initial API image loading
            try:
                self._suppress_details_initial_load = True
            except Exception:
                pass
            self.show_model_details(model_data)
            try:
                self._suppress_details_initial_load = False
            except Exception:
                pass
            try:
                # Clear the routing flag
                self._incoming_show_from_downloaded = False
            except Exception:
                pass
            # disable download button (already downloaded)
            self.download_btn.setEnabled(False)
            self.download_btn.setVisible(False)
            # show a small badge on model name
            self.model_name.setText(self.model_name.text() + "  (Downloaded)")

            # Prefer locally saved images for the details carousel when in Downloaded Explorer
            imgs = []
            try:
                # Prefer version-specific images if available via DB
                model_id = model_data.get('id') or model_data.get('model_id') or model_data.get('_db_id')
                version_id = None
                try:
                    # if current_version is known for this downloaded selection, use it
                    if getattr(self, 'current_version', None):
                        version_id = self.current_version.get('id')
                except Exception:
                    version_id = None
                try:
                    if model_id and hasattr(self, 'db_manager'):
                        rec = self.db_manager.find_downloaded_model(model_id, version_id) if version_id else None
                        if rec and isinstance(rec, dict):
                            imgs = rec.get('images') or []
                except Exception:
                    pass
                # fallback to aggregated images list on the metadata
                if not imgs:
                    imgs = model_data.get('_images') or []
            except Exception:
                imgs = []
            if imgs:
                self.details_images_urls = imgs[:5]
                self.details_image_index = 0
                self._load_details_image_by_index(self.details_image_index)
                # mark that we are showing downloaded model details so future
                # version selection attempts also prefer local images when available
                try:
                    self._showing_downloaded_details = True
                except Exception:
                    pass
        except Exception:
            pass
    
    def init_connections(self):
        self.search_action.triggered.connect(self.show_search_panel)
        self.downloads_action.triggered.connect(self.show_downloads_panel)
        self.history_action.triggered.connect(self.show_history_panel)
        self.settings_action.triggered.connect(self.open_settings)
        self.search_input.returnPressed.connect(self.search_models)
        self.model_type_combo.currentIndexChanged.connect(self.search_models)
        # connect new filter widgets
        self.base_model_combo.currentIndexChanged.connect(self.search_models)
        self.sort_combo.currentIndexChanged.connect(self.search_models)
        self.period_combo.currentIndexChanged.connect(self.search_models)
        # nsfw checkbox
        try:
            self.nsfw_checkbox.stateChanged.connect(self.search_models)
        except Exception:
            pass
    
    def show_api_key_warning(self):
        QMessageBox.warning(
            self, 
            "API Key Required",
            "A Civitai API key is required to access model data.\n\n"
            "Please go to Settings > API Configuration to add your API key.",
            QMessageBox.Ok
        )
        self.open_settings()
    
    def on_model_card_clicked(self, model_data):
        self.show_model_details(model_data)

    def load_popular_models(self):
        try:
            if not self.api_key:
                self.show_api_key_warning()
                return

            # Fetch popular models (default server period now handled by API or UI filters)
            popular_models = self.api.get_popular_models()
            
            # Clear existing models
            self.clear_model_grid()
            
            # Add new models
            for i, model in enumerate(popular_models.get('items', [])):
                row = i // 4
                col = i % 4
                card = ModelCard(model)
                card.clicked.connect(self.show_model_details)
                self.model_grid_layout.addWidget(card, row, col)
                
                # Load image asynchronously (robust extraction)
                image_url = self._extract_image_url(model)
                if image_url:
                    self.load_model_image(card, image_url)
            
            self.status_bar.showMessage(f"Loaded {len(popular_models.get('items', []))} popular models")
            self.right_panel.setCurrentIndex(0)
        except Exception as e:
            self.status_bar.showMessage(f"Error loading popular models: {str(e)}")

    def load_model_by_id(self):
        model_id = self.model_id_input.text().strip() if hasattr(self, 'model_id_input') else ''
        if not model_id:
            return
        try:
            mid = int(model_id) if model_id.isdigit() else model_id
            model_data = self.api.get_model_details(mid)
            if model_data and isinstance(model_data, dict) and model_data.get('id'):
                self.show_model_details(model_data)
            else:
                # No result
                self.right_panel.setCurrentIndex(0)
                self.model_name.setText(f"No model found using ID {model_id}")
                self.model_creator.setText("")
                self.downloads_count.setText("0")
                self.ratings_count.setText("0")
                self.description.clear()
                self.version_list.clear()
                self.trigger_words.clear()
                self.model_image.clear()
        except Exception as e:
            print(f"Error fetching model by id {model_id}:", e)
            self.right_panel.setCurrentIndex(0)
            self.model_name.setText(f"No model found using ID {model_id}")
            self.model_creator.setText("")
            self.downloads_count.setText("0")
            self.ratings_count.setText("0")
            self.description.clear()
            self.version_list.clear()
            self.trigger_words.clear()
            self.model_image.clear()
    
    def search_models(self):
        if not self.api_key:
            self.show_api_key_warning()
            return
            
        try:
            query = self.search_input.text()
            model_type = self.model_type_combo.currentData()
            # Expand model_type filter: when user selects LORA, also include Lycoris(LoCon) and DoRA
            def _normalize_type(s):
                return str(s or '').lower().replace(' ', '').replace('-', '')

            allowed_types = None
            if model_type and isinstance(model_type, str) and _normalize_type(model_type) == 'lora':
                allowed_types = ['lora', 'lycoris', 'dora', 'locon']
                # to ensure broader results from API, don't send the strict type filter
                api_model_type = None
            else:
                api_model_type = model_type if model_type != 'all' else None
            base_model = self.base_model_combo.currentData()
            sort = self.sort_combo.currentData()
            period = self.period_combo.currentData()
            # nsfw checkbox: when checked include NSFW results, otherwise only safe
            nsfw = True if getattr(self, 'nsfw_checkbox', None) and self.nsfw_checkbox.isChecked() else None

            # model_type = model_type if model_type != "all" else None
            
            # Handle "all models" case differently
            # if model_type == "all":
            #     model_type = None  # Don't send type filter
            # elif model_type == "TextualInversion":
            #     model_type = "TextualInversion"

            # Reset pagination
            self.model_page = 1
            self.model_has_more = True
            self.search_cursor = None
            
            # Clear existing models
            self.clear_model_grid()
            
            # Fetch models. If a free-text query is present, avoid sending base_model to API
            # (some API endpoints reject baseModels with query). We'll filter client-side.
            if query and base_model:
                models_raw = self.api.search_models(
                    query=query,
                    model_type=api_model_type,
                    base_model=None,
                    nsfw=nsfw,
                    sort=sort,
                    period=period,
                    limit=50,
                    cursor=self.search_cursor
                )
                items = models_raw.get('items', [])
                filtered = [m for m in items if self._matches_base_model(m, base_model)]
                # apply expanded type filtering if requested
                if allowed_types:
                    def _type_ok(m):
                        t = (m.get('type') or m.get('modelType') or '')
                        if not isinstance(t, str):
                            return False
                        nt = t.lower().replace(' ', '').replace('-', '')
                        return any(k in nt for k in allowed_types)
                    filtered = [m for m in filtered if _type_ok(m)]
                # keep metadata from raw response but override items for display
                models = {'items': filtered, 'metadata': models_raw.get('metadata', {})}
            else:
                # Call API but be resilient to 400 errors caused by type filter; if that happens,
                # re-run without the type filter and filter client-side.
                try:
                    models = self.api.search_models(
                        query=query,
                        model_type=api_model_type,
                        base_model=base_model,
                        nsfw=nsfw,
                        sort=sort,
                        period=period,
                        limit=20,
                        cursor=self.search_cursor
                    )
                except Exception as e:
                    # If API refuses the type param, retry without type and do local filter
                    try:
                        models_raw = self.api.search_models(
                            query=query,
                            model_type=None,
                            base_model=base_model,
                            nsfw=nsfw,
                            sort=sort,
                            period=period,
                            limit=50,
                            cursor=self.search_cursor
                        )
                        items = models_raw.get('items', [])
                        # client-side filter for model_type (with expanded LORA mapping)
                        if allowed_types:
                            def _type_ok(m):
                                t = (m.get('type') or m.get('modelType') or '')
                                if not isinstance(t, str):
                                    return False
                                nt = t.lower().replace(' ', '').replace('-', '')
                                return any(k in nt for k in allowed_types)
                            filtered = [m for m in items if _type_ok(m)]
                            models = {'items': filtered, 'metadata': models_raw.get('metadata', {})}
                        else:
                            type_key = str(model_type or '').lower() if model_type else None
                            if type_key:
                                filtered = []
                                for m in items:
                                    t = (m.get('type') or m.get('modelType') or '')
                                    if isinstance(t, str) and t.lower().replace(' ', '') == type_key.replace(' ', ''):
                                        filtered.append(m)
                                models = {'items': filtered, 'metadata': models_raw.get('metadata', {})}
                            else:
                                models = models_raw
                    except Exception:
                        raise

            # update the small query log so users can see what was sent
            try:
                params_preview = {
                    'query': query,
                    'type': model_type,
                    'base': base_model,
                    'sort': sort,
                    'period': period,
                    'nsfw': nsfw
                }
                self.query_log_label.setText(json.dumps(params_preview))
            except Exception:
                pass
            
            # Add models to grid
            self.add_models_to_grid(models.get('items', []))
            
            metadata = models.get('metadata', {})
            total_items = metadata.get('totalItems', 0)
            # update cursor if provided (cursor-based pagination)
            self.search_cursor = metadata.get('nextCursor') or metadata.get('cursor')
            self.model_has_more = bool(self.search_cursor)
            # self.status_bar.showMessage(f"Found {models.get('metadata', {}).get('totalItems', 0)} models")
            self.status_bar.showMessage(f"Found {total_items} models")
            self.right_panel.setCurrentIndex(0)
        except Exception as e:
            self.status_bar.showMessage(f"Error searching models: {str(e)}")
    
    def check_scroll(self, value):
        # Implement infinite scroll only when the left view is the search results
        if getattr(self, 'current_left_view', 'search') != 'search':
            return
        scrollbar = self.scroll_area.verticalScrollBar()
        if scrollbar.value() >= scrollbar.maximum() - 100 and self.model_has_more:
            self.load_more_models()
    
    def load_more_models(self):
        if not self.api_key or not self.model_has_more:
            return
            
        try:
            query = self.search_input.text()
            model_type = self.model_type_combo.currentData()
            model_type = model_type if model_type != "all" else None
            base_model = self.base_model_combo.currentData()
            sort = self.sort_combo.currentData()
            period = self.period_combo.currentData()
            # nsfw checkbox: when checked include NSFW results, otherwise omit param
            nsfw = True if getattr(self, 'nsfw_checkbox', None) and self.nsfw_checkbox.isChecked() else None

            # For query searches use cursor-based pagination
            if query:
                # For query-based navigation, avoid passing base_model to API; filter locally if needed
                if base_model:
                    models_raw = self.api.search_models(
                        query=query,
                        model_type=model_type,
                        base_model=None,
                        nsfw=nsfw,
                        sort=sort,
                        period=period,
                        limit=50,
                        cursor=self.search_cursor
                    )
                    metadata = models_raw.get('metadata', {})
                    self.search_cursor = metadata.get('nextCursor') or metadata.get('cursor')
                    self.model_has_more = bool(self.search_cursor)
                    items = models_raw.get('items', [])
                    filtered = [m for m in items if self._matches_base_model(m, base_model)]
                    self.add_models_to_grid(filtered)
                    self.status_bar.showMessage(f"Loaded more results (cursor present: {bool(self.search_cursor)})")
                    try:
                        self.query_log_label.setText(str({'cursor': self.search_cursor}))
                    except Exception:
                        pass
                else:
                    # regular query pagination
                    try:
                        models = self.api.search_models(
                            query=query,
                            model_type=model_type,
                            base_model=base_model,
                            nsfw=nsfw,
                            sort=sort,
                            period=period,
                            limit=20,
                            cursor=self.search_cursor
                        )
                        metadata = models.get('metadata', {})
                        # advance cursor
                        self.search_cursor = metadata.get('nextCursor') or metadata.get('cursor')
                        self.model_has_more = bool(self.search_cursor)
                        self.add_models_to_grid(models.get('items', []))
                        self.status_bar.showMessage(f"Loaded more results (cursor present: {bool(self.search_cursor)})")
                        try:
                            self.query_log_label.setText(str({'cursor': self.search_cursor}))
                        except Exception:
                            pass
                    except Exception:
                        # If API rejects the model_type filter, retry without it and filter client-side
                        try:
                            models_raw = self.api.search_models(
                                query=query,
                                model_type=None,
                                base_model=base_model,
                                nsfw=nsfw,
                                sort=sort,
                                period=period,
                                limit=50,
                                cursor=self.search_cursor
                            )
                            metadata = models_raw.get('metadata', {})
                            self.search_cursor = metadata.get('nextCursor') or metadata.get('cursor')
                            self.model_has_more = bool(self.search_cursor)
                            items = models_raw.get('items', [])
                            type_key = str(model_type or '').lower() if model_type else None
                            if type_key:
                                filtered = []
                                for m in items:
                                    t = (m.get('type') or m.get('modelType') or '')
                                    if isinstance(t, str) and t.lower().replace(' ', '') == type_key.replace(' ', ''):
                                        filtered.append(m)
                                self.add_models_to_grid(filtered)
                            else:
                                self.add_models_to_grid(items)
                        except Exception as e:
                            self.status_bar.showMessage(f"Error loading more models: {str(e)}")
                # (handled above)
            else:
                # page-based pagination for non-query browsing
                self.model_page += 1
                models = self.api.search_models(
                    query=None,
                    model_type=model_type,
                    base_model=base_model,
                    nsfw=nsfw,
                    sort=sort,
                    period=period,
                    limit=20,
                    page=self.model_page
                )
                metadata = models.get('metadata', {})
                total_pages = metadata.get('totalPages', 1)
                self.model_has_more = self.model_page < total_pages
                self.add_models_to_grid(models.get('items', []))
                self.status_bar.showMessage(f"Loaded page {self.model_page} of {total_pages}")
        except Exception as e:
            self.status_bar.showMessage(f"Error loading more models: {str(e)}")
    
    def add_models_to_grid(self, models):
        # Append new cards to internal list then reflow
        for model in models:
            card = ModelCard(model)
            card.clicked.connect(lambda checked, m=model: self.show_model_details(m))
            self.model_cards.append(card)

            # Load image asynchronously
            image_url = self._extract_image_url(model)
            if image_url:
                self.load_model_image(card, image_url)

        # Reflow cards into grid based on available columns
        self.relayout_model_cards()
    
    def clear_model_grid(self):
        # Remove all widgets from grid
        # delete widgets and clear internal list
        while self.model_grid_layout.count():
            child = self.model_grid_layout.takeAt(0)
            if child and child.widget():
                child.widget().setParent(None)
        self.model_cards = []

    def compute_columns(self):
        # Compute number of columns that fit in the scroll area viewport.
        try:
            viewport = self.scroll_area.viewport()
            available_width = viewport.width() - self.model_grid_layout.contentsMargins().left() - self.model_grid_layout.contentsMargins().right()
            # approximate card width (ModelCard fixed width 240) plus spacing
            card_total = 240 + self.model_grid_layout.horizontalSpacing()
            if card_total <= 0:
                return 3
            cols = max(3, max(1, available_width // card_total))
            return int(cols)
        except Exception:
            return 3

    def relayout_model_cards(self):
        # Clear layout but keep widgets (they are in self.model_cards)
        # Remove all items from layout
        while self.model_grid_layout.count():
            item = self.model_grid_layout.takeAt(0)
            # do not delete widgets here; they remain in model_cards

        cols = self.compute_columns()
        for idx, card in enumerate(self.model_cards):
            row = idx // cols
            col = idx % cols
            self.model_grid_layout.addWidget(card, row, col)

    def resizeEvent(self, event):
        try:
            if getattr(self, '_enforcing_splitter', False):
                super().resizeEvent(event)
                return
            if hasattr(self, 'splitter') and hasattr(self, 'right_panel'):
                fixed_width = self.right_panel.maximumWidth()
                if fixed_width > 0:
                    total = self.splitter.size().width()
                    left_width = max(self.model_list_container.minimumWidth(), total - fixed_width)
                    self._enforcing_splitter = True
                    self.splitter.setSizes([left_width, fixed_width])
                    self._enforcing_splitter = False
        except Exception:
            self._enforcing_splitter = False
        super().resizeEvent(event)
    
    def load_model_image(self, card, image_url):
        # pass authorization header if available so NSFW images or gated images load
        headers = self.api.headers if hasattr(self, 'api') else None
        # record expected URL on the card so stale responses can be ignored
        try:
            setattr(card, '_expected_image_url', image_url)
        except Exception:
            pass
        thread = ImageLoaderThread(image_url, card, headers=headers)
        thread.image_loaded.connect(self.set_card_image)
        thread.start()
        self.image_loader_threads.append(thread)
        
    def set_card_image(self, url, data_bytes, card):
        # url: the image URL that was requested; data_bytes: bytes; card: target ModelCard
        try:
            # ignore stale responses when a newer image request exists for this card
            try:
                expected = getattr(card, '_expected_image_url', None)
                if expected and url != expected:
                    return
            except Exception:
                pass

            # data_bytes may be bytes (from network) or a QPixmap depending on callers
            # If bytes and appear to be GIF, attempt to find alternate static images
            if isinstance(card, ModelCard) and isinstance(data_bytes, (bytes, bytearray)):
                b = bytes(data_bytes)
                if b[:6] in (b'GIF87a', b'GIF89a'):
                    tried = self.card_image_attempts.setdefault(id(card), set())
                    # look for other candidate image URLs on the model data
                    candidates = []
                    mdl = getattr(card, 'model_data', {}) or {}

                    def _is_video(u):
                        if not u or not isinstance(u, str):
                            return False
                        low = u.lower()
                        for ext in ('.mp4', '.webm', '.mov', '.mkv', '.avi'):
                            if low.endswith(ext) or ext in low:
                                return True
                        return False

                    images = mdl.get('images') or []
                    if not images:
                        versions = mdl.get('modelVersions') or mdl.get('versions') or []
                        if versions and isinstance(versions[0], dict):
                            images = versions[0].get('images') or []
                    for img in images:
                        if isinstance(img, dict):
                            cand = img.get('url') or img.get('thumbnail')
                        else:
                            cand = str(img)
                        # skip video URLs
                        if cand and (not _is_video(cand)) and cand not in tried:
                            candidates.append(cand)

                    # try next candidate
                    for cand in candidates:
                        try:
                            tried.add(cand)
                            headers = self.api.headers if hasattr(self, 'api') else None
                            try:
                                setattr(card, '_expected_image_url', cand)
                            except Exception:
                                pass
                            thread = ImageLoaderThread(cand, card, headers=headers)
                            thread.image_loaded.connect(self.set_card_image)
                            thread.start()
                            self.image_loader_threads.append(thread)
                            return
                        except Exception:
                            continue

                    # no alternative found; leave card blank or fallback to non-animated render
                    return

                # not a GIF -> render normally
                card.set_image_from_bytes(b)
                return

            # fallback: if not ModelCard or not bytes, try existing handling
            if isinstance(card, ModelCard):
                card.set_image(data_bytes)
        except Exception:
            pass
    
    def show_model_details(self, model_data):
        self.current_model = model_data
        # Record this details view for 'Back to details' feature
        try:
            self._last_details_model_data = model_data
            self._last_details_from_downloaded = bool(getattr(self, '_incoming_show_from_downloaded', False))
        except Exception:
            pass
        self.right_panel.setCurrentIndex(0)  # Show details panel
        # By default clear the downloaded-details indicator; callers that want
        # to display locally cached images should set _suppress_details_initial_load
        # before calling this function so we skip the initial API-based image load.
        try:
            self._showing_downloaded_details = False
        except Exception:
            pass

        if not getattr(self, '_suppress_details_initial_load', False):
            # Collect up to 5 showcase images for the carousel (model-level + version samples)
            self.details_images_urls = self._collect_details_images(model_data, max_images=5)
            self.details_image_index = 0
            self._load_details_image_by_index(self.details_image_index)

        # Set model info
        self.model_name.setText(model_data.get('name', 'Untitled Model'))
        creator = model_data.get('creator') or {}
        creator_name = creator.get('username') if isinstance(creator, dict) else str(creator) if creator else 'Unknown'
        self.model_creator.setText(f"by {creator_name}")

        # Populate model type, primary tag, and compact base tag under the title
        try:
            raw_type = model_data.get('type') or model_data.get('modelType') or model_data.get('model_type') or ''
            type_map = {
                'LORA': 'LoRA',
                'Embeddings': 'Embedding',
                'TextualInversion': 'Textual Inversion',
                'Hypernetwork': 'Hypernetwork',
                'Checkpoint': 'Checkpoint',
                'Aesthetic': 'Aesthetic Gradient',
                'Textures': 'Textures'
            }
            type_label = type_map.get(raw_type, str(raw_type)) if raw_type else ''
            try:
                self.model_type_label.setText(type_label)
                self.model_type_label.setVisible(bool(type_label))
            except Exception:
                pass

            tags = model_data.get('tags') or []
            primary_tag = ''
            if tags:
                # build normalized list
                names = []
                for t in tags:
                    if isinstance(t, dict):
                        n = t.get('name') or ''
                    else:
                        n = str(t or '')
                    if n:
                        names.append(n)
                # Fetch user-configured priority tags from settings (comma separated)
                try:
                    if hasattr(self, 'settings_manager'):
                        pri_raw = self.settings_manager.get('priority_tags', '') or ''
                        priority = [p.strip().lower() for p in pri_raw.split(',') if p.strip()]
                        if not priority:
                            priority = ['meme','concept','character','style','clothing','pose']
                    else:
                        priority = ['meme','concept','character','style','clothing','pose']
                except Exception:
                    priority = ['meme','concept','character','style','clothing','pose']
                lower_map = {n.lower(): n for n in names}
                chosen = None
                for p in priority:
                    if p in lower_map:
                        chosen = lower_map[p]
                        break
                if not chosen and names:
                    chosen = names[0]
                primary_tag = chosen or ''
            self._current_primary_tag = primary_tag  # store for download filename usage
            try:
                self.model_primary_tag_label.setText(primary_tag)
                self.model_primary_tag_label.setVisible(bool(primary_tag))
            except Exception:
                pass

            # compact base tag (prefer model-level baseModel or first version)
            base_model_name = ''
            if isinstance(model_data.get('baseModel'), str):
                base_model_name = model_data.get('baseModel')
            else:
                versions = model_data.get('modelVersions') or model_data.get('versions') or []
                if versions and isinstance(versions[0], dict):
                    bm = versions[0].get('baseModel') or versions[0].get('base_model')
                    if isinstance(bm, str):
                        base_model_name = bm
            try:
                self.model_base_tag.setText(base_model_name)
                self.model_base_tag.setVisible(bool(base_model_name))
            except Exception:
                pass
        except Exception:
            pass

        # Model ID label: show and make clickable to copy the raw ID (ensure always executed)
        try:
            model_id = str(model_data.get('id') or model_data.get('model_id') or '')
            if model_id:
                self.model_id_label.setText(f"ID: {model_id}")
                self.model_id_label.setVisible(True)

                def _on_id_click(event, mid=model_id):
                    try:
                        QGuiApplication.clipboard().setText(str(mid))
                    except Exception:
                        pass
                    try:
                        effect = QGraphicsColorizeEffect()
                        effect.setColor(QColor('#4caf50'))
                        effect.setStrength(0.0)
                        self.model_id_label.setGraphicsEffect(effect)
                        anim_in = QPropertyAnimation(effect, b"strength")
                        anim_in.setStartValue(0.0)
                        anim_in.setEndValue(1.0)
                        anim_in.setDuration(220)
                        anim_out = QPropertyAnimation(effect, b"strength")
                        anim_out.setStartValue(1.0)
                        anim_out.setEndValue(0.0)
                        anim_out.setDuration(700)
                        seq = QSequentialAnimationGroup(self)
                        seq.addAnimation(anim_in)
                        seq.addAnimation(anim_out)
                        seq.start()
                    except Exception:
                        pass

                try:
                    self.model_id_label.mousePressEvent = _on_id_click
                except Exception:
                    pass
            else:
                self.model_id_label.setVisible(False)
        except Exception:
            try:
                self.model_id_label.setVisible(False)
            except Exception:
                pass

        # robust numeric extraction
        downloads = self._safe_get_number(model_data, ('downloadCount', 'downloads', 'download_count', 'downloadCount'))
        ratings = self._safe_get_number(model_data, ('ratingCount', 'rating_count', 'ratings', 'ratingsCount'))
        # Fallback: check nested stats dict if counts are zero
        try:
            if (not downloads) or downloads == 0:
                stats = model_data.get('stats') or {}
                downloads = self._safe_get_number(stats, ('downloadCount', 'downloads')) or downloads
            if (not ratings) or ratings == 0:
                stats = model_data.get('stats') or {}
                ratings = self._safe_get_number(stats, ('ratingCount', 'ratings')) or ratings
        except Exception:
            pass
        # Secondary fallback: sum version stats if still zero
        try:
            if (not downloads) or downloads == 0:
                v_total = 0
                for v in model_data.get('modelVersions') or []:
                    sv = v.get('stats') or {}
                    v_total += self._safe_get_number(sv, ('downloadCount', 'downloads'))
                if v_total:
                    downloads = v_total
            if (not ratings) or ratings == 0:
                r_total = 0
                for v in model_data.get('modelVersions') or []:
                    sv = v.get('stats') or {}
                    r_total += self._safe_get_number(sv, ('ratingCount', 'ratings'))
                if r_total:
                    ratings = r_total
        except Exception:
            pass
        self.downloads_count.setText(str(downloads))
        self.ratings_count.setText(str(ratings))
        self.description.setHtml(model_data.get('description', 'No description available'))

        # base model and dates (prefer model-level, but will be overwritten by version selection)
        base_model_val = model_data.get('baseModel') or model_data.get('base_model') or ''
        self.model_base_model.setText(f"Base model: {base_model_val}" if base_model_val else "")
        pub = self._extract_date(model_data, ('publishedAt', 'createdAt', 'created_at', 'published_at'))
        upd = self._extract_date(model_data, ('updatedAt', 'updated_at'))
        self.model_published.setText(f"Published: {pub}" if pub else "")
        self.model_updated.setText(f"Updated: {upd}" if upd else "")

        # Populate versions and mark which are already downloaded
        self.version_list.clear()
        versions = model_data.get('modelVersions', [])
        model_id = model_data.get('id') if isinstance(model_data, dict) else None
        for version in versions:
            vname = version.get('name', 'Unknown')
            vb = version.get('baseModel') or version.get('base_model') or ''
            extra = f" — base: {vb}" if vb else ''
            # detect downloaded state for this specific version
            downloaded_flag = False
            try:
                vid = version.get('id')
                if model_id and vid and hasattr(self, 'db_manager'):
                    downloaded_flag = self.db_manager.is_model_downloaded(model_id, vid)
            except Exception:
                downloaded_flag = False

            label = f"Version {vname}{extra}"
            if downloaded_flag:
                label = label + "  (Downloaded)"

            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, version)
            try:
                item.setData(Qt.UserRole + 1, bool(downloaded_flag))
            except Exception:
                pass
            self.version_list.addItem(item)

        # Clear trigger words and disable download button
        self.trigger_words.clear()
        # When showing model details in general, make sure the download button is visible
        # (it may have been hidden by the downloaded-explorer view)
        try:
            self.download_btn.setVisible(True)
        except Exception:
            pass
        self.download_btn.setEnabled(False)

    def _collect_details_images(self, model_data, max_images=5):
        """Return a list of up to max_images image URLs to show in the details carousel.
        Prefer model-level gallery images, then version images, skipping videos and duplicates.
        """
        urls = []
        seen = set()

        def add_url(u):
            if not u or not isinstance(u, str):
                return
            low = u.lower()
            for ext in ('.mp4', '.webm', '.mov', '.mkv', '.avi'):
                if low.endswith(ext) or ext in low:
                    return
            if u in seen:
                return
            seen.add(u)
            urls.append(u)

        # Model gallery (some models include 'images' or 'gallery')
        for key in ('images', 'gallery', 'modelImages'):
            imgs = model_data.get(key) or []
            for img in imgs:
                if isinstance(img, dict):
                    add_url(img.get('url') or img.get('thumbnail'))
                else:
                    add_url(str(img))
                if len(urls) >= max_images:
                    return urls

        # Fall back to versions
        for version in model_data.get('modelVersions', []):
            for img in (version.get('images') or []):
                if isinstance(img, dict):
                    add_url(img.get('url') or img.get('thumbnail'))
                else:
                    add_url(str(img))
                if len(urls) >= max_images:
                    return urls

        # As a last resort use the single showcase image extractor
        showcase = self._extract_image_url(model_data)
        add_url(showcase)
        return urls

    def _load_details_image_by_index(self, index):
        # load image at details_images_urls[index] into self.model_image using ImageLoaderThread
        try:
            if not self.details_images_urls:
                self.model_image.clear()
                self.details_index_label.setText("")
                self.prev_image_btn.setEnabled(False)
                self.next_image_btn.setEnabled(False)
                return

            index = max(0, min(index, len(self.details_images_urls) - 1))
            url = self.details_images_urls[index]
            self.details_index_label.setText(f"{index+1} / {len(self.details_images_urls)}")
            self.prev_image_btn.setEnabled(index > 0)
            self.next_image_btn.setEnabled(index < len(self.details_images_urls) - 1)

            # reset attempts for details carousel
            self.details_image_attempts = set()
            headers = self.api.headers if hasattr(self, 'api') else None
            try:
                self._expected_details_image = url
            except Exception:
                self._expected_details_image = None
            thread = ImageLoaderThread(url, self.model_image, headers=headers)
            thread.image_loaded.connect(self.set_details_image)
            thread.start()
            self.image_loader_threads.append(thread)
        except Exception:
            pass

    def _change_details_image(self, delta):
        if not self.details_images_urls:
            return
        self.details_image_index = max(0, min(self.details_image_index + delta, len(self.details_images_urls) - 1))
        self._load_details_image_by_index(self.details_image_index)
    
    def set_details_image(self, url, data_bytes, target):
        # Handle bytes and animated images for the details panel; if GIF, try other version images.
        # The ImageLoaderThread now emits (url, bytes, target). We compare the returned
        # url against the expected token to ignore stale responses from previous clicks.
        try:
            # drop responses that are not targeted at the details image widget
            if target != self.model_image:
                return

            # ignore stale results
            expected = getattr(self, '_expected_details_image', None)
            if expected and url != expected:
                return

            if isinstance(data_bytes, (bytes, bytearray)):
                b = bytes(data_bytes)
                if b[:6] in (b'GIF87a', b'GIF89a'):
                    # attempt to find another static image from the selected version
                    tried = self.details_image_attempts
                    def _is_video(u):
                        if not u or not isinstance(u, str):
                            return False
                        low = u.lower()
                        for ext in ('.mp4', '.webm', '.mov', '.mkv', '.avi'):
                            if low.endswith(ext) or ext in low:
                                return True
                        return False

                    if self.current_version:
                        images = self.current_version.get('images') or []
                        for img in images:
                            if isinstance(img, dict):
                                candidate = img.get('url') or img.get('thumbnail')
                            else:
                                candidate = str(img)
                            if candidate and (not _is_video(candidate)) and candidate not in tried:
                                try:
                                    tried.add(candidate)
                                    headers = self.api.headers if hasattr(self, 'api') else None
                                    # mark expected token before starting the loader so
                                    # its completion can be validated.
                                    try:
                                        self._expected_details_image = candidate
                                    except Exception:
                                        self._expected_details_image = None
                                    thread = ImageLoaderThread(candidate, self.model_image, headers=headers)
                                    thread.image_loaded.connect(self.set_details_image)
                                    thread.start()
                                    self.image_loader_threads.append(thread)
                                    return
                                except Exception:
                                    continue
                    # no alternative -> leave blank
                    return

                # static image: render
                pixmap = QPixmap()
                pixmap.loadFromData(b)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.model_image.setPixmap(scaled)
            else:
                # fallback if argument is already a QPixmap
                scaled = data_bytes.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.model_image.setPixmap(scaled)
        except Exception:
            pass
    
    def version_selected(self):
        selected_items = self.version_list.selectedItems()
        if selected_items:
            version = selected_items[0].data(Qt.UserRole)
            self.current_version = version
            
            # Show trigger words
            trigger_words = version.get('trainedWords', [])
            if trigger_words:
                self.trigger_words.setText("\n".join(trigger_words))
            else:
                self.trigger_words.setText("No trigger words available")
            
            # Security: detect unsafe PickleTensor (.pt/.pth) model files for this version
            unsafe = False
            try:
                files = version.get('files') or []
                for f in files:
                    if not isinstance(f, dict):
                        continue
                    if f.get('type') == 'Model':
                        name = (f.get('name') or '').lower()
                        if name.endswith('.pt') or name.endswith('.pth'):
                            unsafe = True
                            break
            except Exception:
                unsafe = False

            # Show/hide security warning and toggle download button
            if unsafe:
                self.security_warning_label.setText(
                    "Security warning: This version only provides PickleTensor files (.pt/.pth), "
                    "which can execute code when loaded and are not supported here. "
                    "Use 'Open on Civitai' to download at your own risk."
                )
                self.security_warning_label.setVisible(True)
                self.download_btn.setEnabled(False)
            else:
                self.security_warning_label.setVisible(False)
                self.download_btn.setEnabled(True)
            # Load first image from this version into the details panel (prefer version images)
            self.details_image_attempts = set()
            # populate version-level base model and dates
            vb = version.get('baseModel') or version.get('base_model') or ''
            if vb:
                self.model_base_model.setText(f"Base model: {vb}")
            pubv = self._extract_date(version, ('publishedAt', 'createdAt', 'created_at', 'published_at'))
            updv = self._extract_date(version, ('updatedAt', 'updated_at'))
            self.model_published.setText(f"Published: {pubv}" if pubv else self.model_published.text())
            self.model_updated.setText(f"Updated: {updv}" if updv else self.model_updated.text())
            # Build the carousel images for the selected version (or local cache in downloaded mode)
            def _is_video(u: str) -> bool:
                if not u or not isinstance(u, str):
                    return False
                low = u.lower()
                for ext in ('.mp4', '.webm', '.mov', '.mkv', '.avi'):
                    if low.endswith(ext) or ext in low:
                        return True
                return False

            urls = []
            seen = set()
            def _add(u: str):
                if not u or not isinstance(u, str):
                    return
                if _is_video(u):
                    return
                if u in seen:
                    return
                seen.add(u)
                urls.append(u)

            # Prefer locally saved images for this specific version if available
            used_local = False
            try:
                if getattr(self, '_showing_downloaded_details', False) and hasattr(self, 'db_manager'):
                    mid = (self.current_model or {}).get('id') or (self.current_model or {}).get('model_id')
                    vid = version.get('id')
                    if mid and vid:
                        rec = self.db_manager.find_downloaded_model(mid, vid)
                        local_imgs = (rec.get('images') if rec else []) or []
                        for u in local_imgs:
                            _add(u)
                        used_local = len(urls) > 0
            except Exception:
                used_local = False

            # If not using local images, take images from the selected version
            if not used_local:
                for img in (version.get('images') or []):
                    if isinstance(img, dict):
                        _add(img.get('url') or img.get('thumbnail'))
                    else:
                        _add(str(img))

            # Fallback to model-level gallery if needed
            if not urls:
                for key in ('images', 'gallery', 'modelImages'):
                    for img in (self.current_model or {}).get(key, []) or []:
                        if isinstance(img, dict):
                            _add(img.get('url') or img.get('thumbnail'))
                        else:
                            _add(str(img))
                        if len(urls) >= 5:
                            break
                    if len(urls) >= 5:
                        break

            # Limit to 5 and load via the carousel loader
            self.details_images_urls = urls[:5]
            self.details_image_index = 0
            self._load_details_image_by_index(self.details_image_index)
    
    def open_model_in_browser(self):
        if self.current_model:
            model_id = self.current_model.get('id')
            if model_id:
                url = f"https://civitai.com/models/{model_id}"
                QDesktopServices.openUrl(QUrl(url))
    
    def download_selected_version(self):
        if not self.current_version or not self.current_model:
            return
            
        # Get download directory
        download_dir = self.settings_manager.get("download_dir")
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
        
        # Create download task
        model_name = self.current_model.get('name', 'model')
        version_name = self.current_version.get('name', 'version')

        def _sanitize_filename(s: str) -> str:
            # Remove characters not allowed on Windows filenames and control chars
            if not isinstance(s, str):
                s = str(s or '')
            # replace invalid characters with underscore
            s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', s)
            # collapse multiple spaces and trim
            s = re.sub(r'\s+', ' ', s).strip()
            # avoid names that end with dot or space
            s = s.rstrip('. ')
            # limit length to reasonable size
            return s[:200]

        # Build list of version files
        files_list = [f for f in (self.current_version.get('files') or []) if isinstance(f, dict) and f.get('type') == 'Model']
        safetensors = [f for f in files_list if (f.get('name') or '').lower().endswith('.safetensors')]
        pickles = [f for f in files_list if (f.get('name') or '').lower().endswith('.pt') or (f.get('name') or '').lower().endswith('.pth')]

        selected_files = []
        if not files_list:
            QMessageBox.warning(self, "Download Error", "No files available for this version")
            return

        if len(files_list) == 1:
            if safetensors:
                selected_files = safetensors
            else:
                QMessageBox.warning(
                    self,
                    "Unsafe File Type",
                    "This version only provides PickleTensor files (.pt/.pth), which are blocked due to security risks.\n"
                    "Use 'Open on Civitai' to download at your own risk."
                )
                return
        else:
            # Show selection dialog; hides .pt/.pth when .safetensors exist
            dlg = FileSelectionDialog(self, files_list)
            if dlg.exec_() == QDialog.Accepted:
                selected_files = dlg.get_selected_files()
            else:
                return
            # If any safetensors selected, drop any .pt/.pth
            if any((f.get('name') or '').lower().endswith('.safetensors') for f in selected_files):
                selected_files = [f for f in selected_files if (f.get('name') or '').lower().endswith('.safetensors')]

            if not selected_files:
                return

        # Parse custom tags (comma separated)
        custom_tags_raw = ''
        try:
            if hasattr(self, 'custom_tags_input'):
                custom_tags_raw = self.custom_tags_input.text().strip()
        except Exception:
            pass
        custom_tags = []
        if custom_tags_raw:
            for part in custom_tags_raw.split(','):
                p = part.strip()
                if p:
                    custom_tags.append(p)

        primary_tag = getattr(self, '_current_primary_tag', '') or ''
        # Enqueue all selected files
        any_added = False
        for f in selected_files:
            # compose safe filename from model/version
            base_fname = f"{_sanitize_filename(model_name)} - {_sanitize_filename(version_name)}"
            parts = [base_fname]
            if primary_tag:
                parts.append(_sanitize_filename(primary_tag))
            for ct in custom_tags:
                parts.append(_sanitize_filename(ct))
            fname = " - ".join(parts) + ".safetensors"
            url = f.get('downloadUrl')
            save_path = os.path.join(download_dir, fname)

            # Prevent duplicate download for this model/version and file path
            try:
                model_id = self.current_model.get('id')
                version_id = self.current_version.get('id')
                if self.db_manager.is_model_downloaded(model_id, version_id, file_path=save_path):
                    continue
            except Exception:
                pass

            # Capture original model file name (without added tags) and SHA256 if provided
            original_name = f.get('name') or fname
            file_sha256 = None
            try:
                hashes = f.get('hashes') if isinstance(f, dict) else None
                if isinstance(hashes, dict):
                    file_sha256 = hashes.get('SHA256') or hashes.get('sha256')
            except Exception:
                pass

            task = DownloadTask(
                fname,
                url,
                save_path,
                self.api_key,
                model_data=self.current_model,
                version=self.current_version
            )
            # attach extra metadata for db recording after completion
            task.original_file_name = original_name
            task.file_sha256 = file_sha256
            task.primary_tag = primary_tag
            try:
                self.download_manager.add_download(task)
                any_added = True
            except Exception:
                pass

        if any_added:
            # Do not redirect to downloads; keep user on details
            self.status_bar.showMessage("Added selected file(s) to download queue")
    
    def show_search_panel(self):
        # switch back to search left view
        try:
            self.current_left_view = 'search'
            self.title_label.setText("Model Explorer")
            # restore primary color background for search mode
            self.title_container.setStyleSheet(f"background-color: {PRIMARY_COLOR.name()}; border-radius: 6px; padding: 10px;")
        except Exception:
            pass
        # ensure download button is visible again when returning to search
        try:
            self.download_btn.setVisible(True)
            # enable only if a version is selected
            self.download_btn.setEnabled(bool(getattr(self, 'current_version', None)))
        except Exception:
            pass
        # restore cached search cards if available
        try:
            if getattr(self, '_search_cache', None):
                # replace model grid with cached cards
                try:
                    self.clear_model_grid()
                except Exception:
                    pass
                for md in self._search_cache:
                    try:
                        card = ModelCard(md)
                        card.clicked.connect(lambda checked=False, m=md: self.show_model_details(m))
                        self.model_cards.append(card)
                        # attempt to (re)load a thumbnail for the restored card using the
                        # same extraction logic as live search results. Images are not
                        # persisted; we fetch them from the API again.
                        try:
                            url = self._extract_image_url(md)
                            if url:
                                # Use existing async loader
                                self.load_model_image(card, url)
                        except Exception:
                            pass
                    except Exception:
                        continue
                try:
                    self.relayout_model_cards()
                except Exception:
                    pass
        except Exception:
            pass

        self.right_panel.setCurrentIndex(0)
    
    def show_downloads_panel(self):
        self.right_panel.setCurrentIndex(1)
        self.update_downloads_panel()
        # Enable/disable back button based on availability
        try:
            has_last = bool(getattr(self, '_last_details_model_data', None))
            if hasattr(self, 'back_to_details_from_downloads_btn'):
                self.back_to_details_from_downloads_btn.setEnabled(has_last)
        except Exception:
            pass
    
    def show_history_panel(self):
        self.right_panel.setCurrentIndex(2)
        self.load_download_history()
        # Enable/disable back button based on availability
        try:
            has_last = bool(getattr(self, '_last_details_model_data', None))
            if hasattr(self, 'back_to_details_from_history_btn'):
                self.back_to_details_from_history_btn.setEnabled(has_last)
        except Exception:
            pass

    def back_to_last_details(self):
        """Return to the last details view (downloaded/explorer-aware)."""
        try:
            data = getattr(self, '_last_details_model_data', None)
            if not data:
                return
            if bool(getattr(self, '_last_details_from_downloaded', False)):
                self.show_downloaded_model_details(data)
            else:
                self.show_model_details(data)
        except Exception:
            pass

    def open_settings(self):
        dialog = SettingsDialog(self.settings_manager, self)
        if dialog.exec_() == QDialog.accepted:
            # Update API key if changed
            new_api_key = self.settings_manager.get("api_key")
            if new_api_key != self.api_key:
                self.api_key = new_api_key
                self.api = CivitaiAPI(api_key=self.api_key)
                
                # Reload models if needed
                if self.model_grid_layout.count() > 0:
                    self.load_popular_models()
    
    def update_downloads_panel(self):
        # Clear current lists
        while self.active_downloads_list.count():
            child = self.active_downloads_list.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        while self.queue_list.count():
            child = self.queue_list.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Get active and queued downloads
        active_downloads = self.download_manager.get_active_downloads()
        queued_downloads = self.download_manager.get_queued_downloads()
        
        # Add active downloads
        if active_downloads:
            for task in active_downloads:
                widget = DownloadProgressWidget(task)
                # connect cancel request from widget to manager
                try:
                    widget.cancel_requested.connect(lambda fn, mgr=self.download_manager: (mgr.cancel_download(fn), self.update_downloads_panel()))
                except Exception:
                    pass
                self.active_downloads_list.addWidget(widget)
        else:
            placeholder = QLabel("No active downloads")
            placeholder.setStyleSheet(f"color: {SECONDARY_TEXT.name()}; font-style: italic;")
            placeholder.setAlignment(Qt.AlignCenter)
            self.active_downloads_list.addWidget(placeholder)
        
        # Add queued downloads
        if queued_downloads:
            for task in queued_downloads:
                widget = QLabel(f"{task.file_name} - Queued")
                widget.setStyleSheet(f"color: {SECONDARY_TEXT.name()}; padding: 8px;")
                widget.setMinimumHeight(40)
                self.queue_list.addWidget(widget)
        else:
            placeholder = QLabel("Download queue is empty")
            placeholder.setStyleSheet(f"color: {SECONDARY_TEXT.name()}; font-style: italic;")
            placeholder.setAlignment(Qt.AlignCenter)
            self.queue_list.addWidget(placeholder)
    
    def load_download_history(self):
        self.history_tree.clear()
        history = self.db_manager.get_download_history()
        # Optionally filter out failed downloads
        try:
            if getattr(self, 'hide_failed_checkbox', None) and self.hide_failed_checkbox.isChecked():
                history = [h for h in history if (h.get('status') or '').lower() != 'failed']
        except Exception:
            pass
        
        # Group by main tag
        tag_groups = {}
        for item in history:
            tag = item.get('main_tag', 'Other')
            if tag not in tag_groups:
                tag_groups[tag] = []
            tag_groups[tag].append(item)
        
        # Add to tree
        for tag, items in tag_groups.items():
            group_item = QTreeWidgetItem(self.history_tree, [tag])
            group_item.setExpanded(True)
            
            for item in items:
                model_name = item.get('model_name', 'Unknown')
                model_id = str(item.get('model_id', ''))
                version = item.get('version', 'Unknown')
                date = item.get('download_date', 'Unknown')
                # file_size stored in MB by DownloadManager
                size = f"{item.get('file_size', 0):.1f} MB"
                status = item.get('status', 'Completed')
                
                child = QTreeWidgetItem(group_item, [
                    model_name, model_id, version, date, size, status
                ])
        
        # Expand all groups
        self.history_tree.expandAll()

    def refresh_download_history_status(self):
        # Update statuses for missing/restored files then reload view
        counts = {"missing":0, "restored":0}
        try:
            download_dir = self.settings_manager.get("download_dir") or ''
            counts = self.db_manager.update_file_statuses(download_dir)
        except Exception:
            pass
        self.load_download_history()
        try:
            self.status_bar.showMessage(
                f"History refreshed. Missing: {counts.get('missing',0)} Restored(existing): {counts.get('restored',0)} Renamed restored: {counts.get('renamed_restored',0)} (hashed {counts.get('hashed_files',0)}/{counts.get('scanned_files',0)} files)",
                8000
            )
        except Exception:
            pass
    
    def export_history(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export History", "", "JSON Files (*.json)"
        )
        if file_path:
            # Use minimal portable export (no local paths/images)
            try:
                history = self.db_manager.get_minimal_download_export()
            except Exception:
                history = self.db_manager.get_download_history()
            try:
                with open(file_path, 'w') as f:
                    json.dump(history, f, indent=2)
                self.status_bar.showMessage(f"History exported to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export history: {str(e)}")
    
    def import_history(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import History", "", "JSON Files (*.json)"
        )
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    history = json.load(f)
                self.db_manager.import_history(history)
                self.load_download_history()
                self.status_bar.showMessage(f"History imported from {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import history: {str(e)}")
    
    def clear_history(self):
        reply = QMessageBox.question(
            self, "Clear History",
            "Are you sure you want to clear all download history?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db_manager.clear_history()
            self.history_tree.clear()
            self.status_bar.showMessage("Download history cleared")