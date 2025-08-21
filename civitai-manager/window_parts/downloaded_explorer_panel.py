# downloaded_explorer_panel.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QGridLayout
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtCore import Qt
from constants import PRIMARY_COLOR
from ui_components import ModelCard

class DownloadedExplorerBuilder:
    def __init__(self, host):
        self.host = host

    def build(self):
        host = self.host
        host.downloaded_explorer_panel = QWidget()
        dl_layout = QVBoxLayout(host.downloaded_explorer_panel)
        dl_layout.setContentsMargins(15, 15, 15, 15)
        dl_layout.setSpacing(12)

        title = QLabel("Downloaded Model Explorer")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet(f"color: {PRIMARY_COLOR.name()};")
        dl_layout.addWidget(title)

        host.downloaded_scroll = QScrollArea()
        host.downloaded_scroll.setWidgetResizable(True)
        host.downloaded_grid_container = QWidget()
        host.downloaded_grid_layout = QGridLayout(host.downloaded_grid_container)
        host.downloaded_grid_layout.setAlignment(Qt.AlignTop)
        host.downloaded_grid_layout.setContentsMargins(5,5,5,5)
        host.downloaded_grid_layout.setSpacing(15)
        host.downloaded_scroll.setWidget(host.downloaded_grid_container)
        dl_layout.addWidget(host.downloaded_scroll)

        host.right_panel.addWidget(host.downloaded_explorer_panel)

        try:
            host.downloaded_explorer_action.triggered.connect(host.show_downloaded_explorer)
        except Exception:
            pass
