# welcome_panel_builder.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from constants import PRIMARY_COLOR, TEXT_COLOR, BACKGROUND_COLOR


class WelcomePanelBuilder:
    def __init__(self, host):
        self.host = host

    def build(self):
        host = self.host
        host.welcome_panel = QWidget()
        host.welcome_panel.setStyleSheet(f"background-color: {BACKGROUND_COLOR.name()};")
        layout = QVBoxLayout(host.welcome_panel)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)

        welcome_label = QLabel("Civitai Download Manager")
        welcome_label.setFont(QFont("Segoe UI", 24, QFont.Bold))
        welcome_label.setStyleSheet(f"color: {PRIMARY_COLOR.name()}; margin-bottom: 30px;")
        layout.addWidget(welcome_label, alignment=Qt.AlignCenter)

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

        popular_btn = QPushButton("Show Popular Models")
        popular_btn.setFont(QFont("Segoe UI", 12))
        popular_btn.setStyleSheet(
            f"""
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
            """
        )
        popular_btn.setFixedSize(200, 50)
        popular_btn.clicked.connect(host.load_popular_models)
        layout.addWidget(popular_btn, alignment=Qt.AlignCenter)

        layout.addStretch()
        host.right_panel.addWidget(host.welcome_panel)
        return host.welcome_panel
