# downloads_panel.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QGroupBox, QPushButton, QHBoxLayout
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from constants import PRIMARY_COLOR, SECONDARY_TEXT

class DownloadsPanelBuilder:
    def __init__(self, host):
        self.host = host

    def build(self):
        host = self.host
        host.download_panel = QWidget()
        dl_layout = QVBoxLayout(host.download_panel)
        dl_layout.setContentsMargins(20, 20, 20, 20)
        dl_layout.setSpacing(20)

        title = QLabel("Download Manager")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet(f"color: {PRIMARY_COLOR.name()};")
        dl_layout.addWidget(title)

        # Back to last details button
        top_btns = QHBoxLayout()
        host.back_to_details_from_downloads_btn = QPushButton("Back to Details")
        host.back_to_details_from_downloads_btn.setToolTip("Return to the last model details you viewed")
        host.back_to_details_from_downloads_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #333;
                color: #ddd;
                padding: 6px 10px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #444;
            }}
            QPushButton:disabled {{
                color: #777;
                background-color: #2a2a2a;
            }}
        """)
        host.back_to_details_from_downloads_btn.clicked.connect(host.back_to_last_details)
        host.back_to_details_from_downloads_btn.setEnabled(False)
        top_btns.addWidget(host.back_to_details_from_downloads_btn)
        top_btns.addStretch(1)
        dl_layout.addLayout(top_btns)

        active_group = QGroupBox("Active Downloads")
        active_group.setStyleSheet(f"""
            QGroupBox {{
                color: {SECONDARY_TEXT.name()};
                font-size: 11pt;
                border: 1px solid {PRIMARY_COLOR.name()};
                border-radius: 6px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)
        active_layout = QVBoxLayout(active_group)
        host.active_downloads_list = QVBoxLayout()
        host.active_downloads_list.setSpacing(10)
        placeholder = QLabel("No active downloads")
        placeholder.setStyleSheet(f"color: {SECONDARY_TEXT.name()}; font-style: italic;")
        placeholder.setAlignment(Qt.AlignCenter)
        host.active_downloads_list.addWidget(placeholder)
        active_layout.addLayout(host.active_downloads_list)
        dl_layout.addWidget(active_group)

        queue_group = QGroupBox("Download Queue")
        queue_group.setStyleSheet(f"""
            QGroupBox {{
                color: {SECONDARY_TEXT.name()};
                font-size: 11pt;
                border: 1px solid {PRIMARY_COLOR.name()};
                border-radius: 6px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)
        queue_layout = QVBoxLayout(queue_group)
        host.queue_list = QVBoxLayout()
        host.queue_list.setSpacing(10)
        placeholder = QLabel("Download queue is empty")
        placeholder.setStyleSheet(f"color: {SECONDARY_TEXT.name()}; font-style: italic;")
        placeholder.setAlignment(Qt.AlignCenter)
        host.queue_list.addWidget(placeholder)
        queue_layout.addLayout(host.queue_list)
        dl_layout.addWidget(queue_group)

        host.right_panel.addWidget(host.download_panel)
