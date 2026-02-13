"""Main application window (refactored)."""
from PyQt5.QtWidgets import QMainWindow, QSystemTrayIcon
from PyQt5.QtGui import QIcon, QPalette
from PyQt5.QtCore import QTimer
from api import CivitaiAPI
from database import DatabaseManager
from download_manager import DownloadManager
from settings import SettingsManager
from constants import PRIMARY_COLOR, SECONDARY_COLOR, BACKGROUND_COLOR, CARD_BACKGROUND, TEXT_COLOR
from window_parts.download_notifications import DownloadNotificationHandler
from window_parts.model_utils import ModelDataUtils
from window_parts.search_manager import SearchManager
from window_parts.downloaded_manager import DownloadedManager
from window_parts.download_handler import DownloadHandler
from window_parts.main_window_mixins import (
    UiMixin,
    ConnectionsMixin,
    DelegationMixin,
    DiagnosticsMixin,
    SearchMixin,
    SearchViewMixin,
    DetailsMixin,
    ImageMixin,
    ModeMixin,
    HistoryMixin,
    LayoutMixin,
    SettingsMixin,
    UtilsMixin,
    CleanupMixin,
)

class MainWindow(
    QMainWindow,
    UiMixin,
    ConnectionsMixin,
    DelegationMixin,
    DiagnosticsMixin,
    SearchMixin,
    SearchViewMixin,
    DetailsMixin,
    ImageMixin,
    ModeMixin,
    HistoryMixin,
    LayoutMixin,
    SettingsMixin,
    UtilsMixin,
    CleanupMixin,
):
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
        
        # Initialize managers and utilities
        self.utils = ModelDataUtils()
        self.search_manager = SearchManager(self)
        self.downloaded_manager = DownloadedManager(self)
        self.download_handler = DownloadHandler(self)
        
        # Initialize modules
        self.settings_manager = SettingsManager()
        self.db_manager = DatabaseManager()
        self.api_key = self.settings_manager.get("api_key")
        self.api = CivitaiAPI(api_key=self.api_key)
        self.download_manager = DownloadManager(self.db_manager)
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
        self._ui_generation = 0
        self._details_image_generation = 0
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

        self.notification_handler = DownloadNotificationHandler(self)
        self.notification_handler.connect()