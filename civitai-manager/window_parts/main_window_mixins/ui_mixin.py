# ui_mixin.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSplitter, QStackedWidget, QStatusBar
from PyQt5.QtCore import Qt
from constants import PRIMARY_COLOR, BACKGROUND_COLOR, SECONDARY_TEXT
from window_parts.toolbar_builder import ToolbarBuilder
from window_parts.left_panel_builder import LeftPanelBuilder
from window_parts.welcome_panel_builder import WelcomePanelBuilder
from window_parts.details_panel import DetailsPanelBuilder
from window_parts.downloads_panel import DownloadsPanelBuilder
from window_parts.history_panel import HistoryPanelBuilder
from window_parts.downloaded_explorer_panel import DownloadedExplorerBuilder


class UiMixin:
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        ToolbarBuilder(self).build()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setStyleSheet(
            f"""
            QStatusBar {{
                background-color: {BACKGROUND_COLOR.name()};
                color: {SECONDARY_TEXT.name()};
                border-top: 1px solid {PRIMARY_COLOR.name()};
            }}
            """
        )

        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {PRIMARY_COLOR.name()}; }}")
        self.splitter = splitter
        main_layout.addWidget(splitter)

        LeftPanelBuilder(self).build(splitter)

        self.right_panel = QStackedWidget()
        self.right_panel.setStyleSheet(
            f"""
            QStackedWidget {{
                background-color: {BACKGROUND_COLOR.name()};
                border-left: 1px solid {PRIMARY_COLOR.name()};
            }}
            """
        )
        splitter.addWidget(self.right_panel)

        self.create_model_details_panel()
        self.create_download_manager_panel()
        self.create_history_panel()
        self.create_downloaded_explorer_panel()
        WelcomePanelBuilder(self).build()

        splitter.setSizes([400, 800])
        try:
            fixed_width = 660
            self.right_panel.setMinimumWidth(fixed_width)
            self.right_panel.setMaximumWidth(fixed_width)
            self.model_list_container.setMinimumWidth(320)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 0)
            try:
                splitter.splitterMoved.disconnect()
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.right_panel.setCurrentIndex(self.right_panel.count() - 1)
        except Exception:
            self.right_panel.setCurrentIndex(0)

    def create_model_details_panel(self):
        DetailsPanelBuilder(self).build()

    def create_download_manager_panel(self):
        DownloadsPanelBuilder(self).build()

    def create_history_panel(self):
        HistoryPanelBuilder(self).build()

    def create_downloaded_explorer_panel(self):
        DownloadedExplorerBuilder(self).build()
