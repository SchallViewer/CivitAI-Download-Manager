# history_panel.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTreeWidget, QPushButton, QHBoxLayout
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from constants import PRIMARY_COLOR, SECONDARY_TEXT, BACKGROUND_COLOR

class HistoryPanelBuilder:
    def __init__(self, host):
        self.host = host

    def build(self):
        host = self.host
        host.history_panel = QWidget()
        history_layout = QVBoxLayout(host.history_panel)
        history_layout.setContentsMargins(20, 20, 20, 20)
        history_layout.setSpacing(20)

        title = QLabel("Download History")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet(f"color: {PRIMARY_COLOR.name()};")
        history_layout.addWidget(title)

        # Back to last details button
        top_btns = QHBoxLayout()
        self.host.back_to_details_from_history_btn = QPushButton("Back to Details")
        self.host.back_to_details_from_history_btn.setToolTip("Return to the last model details you viewed")
        self.host.back_to_details_from_history_btn.setStyleSheet(f"""
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
        self.host.back_to_details_from_history_btn.clicked.connect(self.host.back_to_last_details)
        self.host.back_to_details_from_history_btn.setEnabled(False)
        top_btns.addWidget(self.host.back_to_details_from_history_btn)
        top_btns.addStretch(1)
        history_layout.addLayout(top_btns)

        host.history_tree = QTreeWidget()
        host.history_tree.setHeaderLabels(["Model", "Version", "Date Downloaded", "Size", "Status"])
        host.history_tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {BACKGROUND_COLOR.name()};
                color: {SECONDARY_TEXT.name()};
                border: 1px solid {PRIMARY_COLOR.name()};
                border-radius: 6px;
            }}
            QHeaderView::section {{
                background-color: {PRIMARY_COLOR.name()};
                color: white;
                padding: 4px;
                border: none;
            }}
        """)
        host.history_tree.setColumnWidth(0, 250)
        host.history_tree.setColumnWidth(1, 100)
        host.history_tree.setColumnWidth(2, 150)
        host.history_tree.setColumnWidth(3, 80)
        history_layout.addWidget(host.history_tree)

        host.hide_failed_checkbox = QPushButton("Hide failed downloads")
        host.hide_failed_checkbox.setCheckable(True)
        host.hide_failed_checkbox.setChecked(True)
        host.hide_failed_checkbox.setStyleSheet(f"""
            QPushButton {{
                background-color: {BACKGROUND_COLOR.name()};
                color: {SECONDARY_TEXT.name()};
                border: 1px solid {PRIMARY_COLOR.name()};
                padding: 6px;
                border-radius: 4px;
            }}
            QPushButton:checked {{
                background-color: {PRIMARY_COLOR.name()};
                color: white;
            }}
        """)
        host.hide_failed_checkbox.toggled.connect(host.load_download_history)
        history_layout.addWidget(host.hide_failed_checkbox)

        btn_layout = QHBoxLayout()
        host.export_btn = QPushButton("Export History")
        host.export_btn.setFont(QFont("Segoe UI", 10))
        host.export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PRIMARY_COLOR.name()};
                color: white;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #9575cd;
            }}
        """)
        host.export_btn.clicked.connect(host.export_history)
        btn_layout.addWidget(host.export_btn)

        host.import_btn = QPushButton("Import History")
        host.import_btn.setFont(QFont("Segoe UI", 10))
        host.import_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #333;
                color: #ddd;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #444;
            }}
        """)
        host.import_btn.clicked.connect(host.import_history)
        btn_layout.addWidget(host.import_btn)

        host.clear_btn = QPushButton("Clear History")
        host.clear_btn.setFont(QFont("Segoe UI", 10))
        host.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #b00020;
                color: white;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #c00030;
            }}
        """)
        host.clear_btn.clicked.connect(host.clear_history)
        btn_layout.addWidget(host.clear_btn)

        history_layout.addLayout(btn_layout)
        host.right_panel.addWidget(host.history_panel)
