# details_panel.py
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QGroupBox, QListWidget,
    QListWidgetItem, QTextEdit, QPushButton, QLabel, QSizePolicy
)
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtCore import Qt, QSize, QUrl
from PyQt5.QtGui import QDesktopServices

from constants import PRIMARY_COLOR, SECONDARY_TEXT, BACKGROUND_COLOR, CARD_BACKGROUND, TEXT_COLOR
from ui_helpers import ImageLoaderThread

class DetailsPanelBuilder:
    """
    Helper to build and wire the Model Details panel widgets onto a MainWindow-like host
    that provides attributes used by the app (e.g., status_bar, api, etc.).
    It configures self.details_panel and populates many self.* fields expected elsewhere.
    """
    def __init__(self, host):
        self.host = host

    def build(self):
        host = self.host
        host.details_panel = QScrollArea()
        host.details_panel.setWidgetResizable(True)
        host.details_panel.setStyleSheet(
            f"""
            QScrollArea {{
                border: none;
                background-color: {BACKGROUND_COLOR.name()};
            }}
            QScrollArea > QWidget {{
                background-color: {BACKGROUND_COLOR.name()};
                color: {TEXT_COLOR.name()};
            }}
            QGroupBox {{
                background-color: transparent;
                color: {SECONDARY_TEXT.name()};
            }}
            """
        )

        details_container = QWidget()
        details_container.setStyleSheet(
            f"background-color: {BACKGROUND_COLOR.name()}; color: {TEXT_COLOR.name()};"
        )
        details_layout = QVBoxLayout(details_container)
        details_layout.setContentsMargins(20, 20, 20, 20)
        details_layout.setSpacing(20)

        # Header (left image + carousel, right info block)
        header_layout = QHBoxLayout()

        # Image + carousel
        image_container = QWidget()
        image_container_layout = QVBoxLayout(image_container)
        image_container_layout.setContentsMargins(0, 0, 0, 0)
        image_container_layout.setSpacing(6)

        host.model_image = QLabel()
        host.model_image.setFixedSize(300, 300)
        host.model_image.setAlignment(Qt.AlignCenter)
        host.model_image.setStyleSheet(
            f"""
            background-color: {BACKGROUND_COLOR.name()};
            border: 1px solid {PRIMARY_COLOR.name()};
            border-radius: 6px;
            """
        )
        image_container_layout.addWidget(host.model_image, alignment=Qt.AlignCenter)

        carousel_controls = QWidget()
        carousel_layout = QHBoxLayout(carousel_controls)
        carousel_layout.setContentsMargins(0, 0, 0, 0)
        carousel_layout.setSpacing(8)

        host.prev_image_btn = QPushButton("◀")
        host.prev_image_btn.setFixedSize(28, 28)
        host.prev_image_btn.setToolTip("Previous image")
        host.prev_image_btn.clicked.connect(lambda: host._change_details_image(-1))
        carousel_layout.addWidget(host.prev_image_btn)

        host.details_index_label = QLabel("")
        host.details_index_label.setAlignment(Qt.AlignCenter)
        host.details_index_label.setStyleSheet(f"color: {SECONDARY_TEXT.name()};")
        carousel_layout.addWidget(host.details_index_label, stretch=1)

        host.next_image_btn = QPushButton("▶")
        host.next_image_btn.setFixedSize(28, 28)
        host.next_image_btn.setToolTip("Next image")
        host.next_image_btn.clicked.connect(lambda: host._change_details_image(1))
        carousel_layout.addWidget(host.next_image_btn)

        image_container_layout.addWidget(carousel_controls)
        header_layout.addWidget(image_container)

        # Info block with constrained width so long titles don't stretch splitter
        info_container = QWidget()
        info_container.setMaximumWidth(520)  # cap width
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(6)
        info_layout.setAlignment(Qt.AlignTop)

        host.model_name = QLabel()
        host.model_name.setWordWrap(True)
        host.model_name.setFont(QFont("Segoe UI", 16, QFont.Bold))
        host.model_name.setStyleSheet(f"color: {PRIMARY_COLOR.name()};")
        host.model_name.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        info_layout.addWidget(host.model_name)

        host.model_id_label = QLabel()
        host.model_id_label.setFont(QFont("Segoe UI", 10))
        host.model_id_label.setStyleSheet(
            f"color: {SECONDARY_TEXT.name()}; text-decoration: underline;"
        )
        host.model_id_label.setCursor(Qt.PointingHandCursor)
        host.model_id_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        info_layout.addWidget(host.model_id_label)

        host.model_creator = QLabel()
        host.model_creator.setFont(QFont("Segoe UI", 12))
        host.model_creator.setStyleSheet(f"color: {TEXT_COLOR.name()};")
        info_layout.addWidget(host.model_creator)

        tags_row = QHBoxLayout()
        tags_row.setSpacing(8)
        host.model_type_label = QLabel()
        host.model_type_label.setFont(QFont("Segoe UI", 10))
        host.model_type_label.setStyleSheet(
            f"background-color: {PRIMARY_COLOR.name()}; color: white; padding: 2px 6px; border-radius: 4px;"
        )
        tags_row.addWidget(host.model_type_label)

        host.model_primary_tag_label = QLabel()
        host.model_primary_tag_label.setFont(QFont("Segoe UI", 10))
        host.model_primary_tag_label.setStyleSheet(
            f"background-color: {SECONDARY_TEXT.name()}; color: white; padding: 2px 6px; border-radius: 4px;"
        )
        tags_row.addWidget(host.model_primary_tag_label)

        host.model_base_tag = QLabel()
        host.model_base_tag.setFont(QFont("Segoe UI", 10))
        host.model_base_tag.setStyleSheet(
            "background-color: #4caf50; color: white; padding: 2px 6px; border-radius: 4px;"
        )
        tags_row.addWidget(host.model_base_tag)

        tags_row.addStretch()
        info_layout.addLayout(tags_row)

        host.model_base_model = QLabel()
        host.model_base_model.setFont(QFont("Segoe UI", 11))
        host.model_base_model.setStyleSheet(f"color: {SECONDARY_TEXT.name()};")
        info_layout.addWidget(host.model_base_model)

        host.model_published = QLabel()
        host.model_published.setFont(QFont("Segoe UI", 10))
        host.model_published.setStyleSheet(f"color: {SECONDARY_TEXT.name()};")
        info_layout.addWidget(host.model_published)

        host.model_updated = QLabel()
        host.model_updated.setFont(QFont("Segoe UI", 10))
        host.model_updated.setStyleSheet(f"color: {SECONDARY_TEXT.name()};")
        info_layout.addWidget(host.model_updated)

        stats_layout = QHBoxLayout()

        downloads_box = QGroupBox("Downloads")
        downloads_box.setStyleSheet(
            f"""
            QGroupBox {{
                color: {SECONDARY_TEXT.name()};
                font-size: 10pt;
                border: 1px solid {PRIMARY_COLOR.name()};
                border-radius: 6px;
                margin-top: 16px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            """
        )
        downloads_layout = QVBoxLayout(downloads_box)
        host.downloads_count = QLabel("0")
        host.downloads_count.setFont(QFont("Segoe UI", 14, QFont.Bold))
        host.downloads_count.setStyleSheet(f"color: {TEXT_COLOR.name()};")
        downloads_layout.addWidget(host.downloads_count, alignment=Qt.AlignCenter)
        stats_layout.addWidget(downloads_box)

        ratings_box = QGroupBox("Ratings")
        ratings_box.setStyleSheet(
            f"""
            QGroupBox {{
                color: {SECONDARY_TEXT.name()};
                font-size: 10pt;
                border: 1px solid {PRIMARY_COLOR.name()};
                border-radius: 6px;
                margin-top: 16px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            """
        )
        ratings_layout = QVBoxLayout(ratings_box)
        host.ratings_count = QLabel("0")
        host.ratings_count.setFont(QFont("Segoe UI", 14, QFont.Bold))
        host.ratings_count.setStyleSheet(f"color: {TEXT_COLOR.name()};")
        ratings_layout.addWidget(host.ratings_count, alignment=Qt.AlignCenter)
        stats_layout.addWidget(ratings_box)

        info_layout.addLayout(stats_layout)

        host.open_browser_btn = QPushButton("Open on Civitai")
        host.open_browser_btn.setFont(QFont("Segoe UI", 10))
        host.open_browser_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {CARD_BACKGROUND.name()};
                color: {TEXT_COLOR.name()};
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
                border: 1px solid {PRIMARY_COLOR.name()};
            }}
            QPushButton:hover {{
                background-color: {PRIMARY_COLOR.name()};
                color: white;
            }}
            """
        )
        host.open_browser_btn.setFixedHeight(35)
        host.open_browser_btn.clicked.connect(host.open_model_in_browser)
        info_layout.addWidget(host.open_browser_btn)

        header_layout.addWidget(info_container, stretch=0)
        header_layout.addStretch()
        details_layout.addLayout(header_layout)

        # Versions group
        version_group = QGroupBox("Available Versions")
        version_group.setStyleSheet(
            f"""
            QGroupBox {{
                color: {SECONDARY_TEXT.name()};
                font-size: 11pt;
                border: 1px solid {PRIMARY_COLOR.name()};
                border-radius: 6px;
                margin-top: 16px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            """
        )
        version_layout = QVBoxLayout(version_group)

        host.version_list = QListWidget()
        host.version_list.setStyleSheet(
            f"""
            QListWidget {{
                background-color: {BACKGROUND_COLOR.name()};
                color: {TEXT_COLOR.name()};
                border: none;
                border-radius: 4px;
            }}
            QListWidget::item {{
                padding: 10px;
                border-bottom: 1px solid {CARD_BACKGROUND.name()};
            }}
            QListWidget::item:selected {{
                background-color: {PRIMARY_COLOR.name()};
                color: white;
            }}
            """
        )
        host.version_list.setFixedHeight(150)
        host.version_list.itemSelectionChanged.connect(host.version_selected)
        version_layout.addWidget(host.version_list)

        host.trigger_words = QTextEdit()
        host.trigger_words.setReadOnly(True)
        host.trigger_words.setFont(QFont("Consolas", 10))
        host.trigger_words.setStyleSheet(
            f"""
            QTextEdit {{
                background-color: {BACKGROUND_COLOR.name()};
                color: {TEXT_COLOR.name()};
                border: 1px solid #333;
                border-radius: 4px;
                padding: 10px;
            }}
            """
        )
        host.trigger_words.setPlaceholderText(
            "Trigger words will appear here when a version is selected"
        )
        version_layout.addWidget(host.trigger_words)

        host.security_warning_label = QLabel()
        host.security_warning_label.setWordWrap(True)
        host.security_warning_label.setVisible(False)
        host.security_warning_label.setStyleSheet(
            """
            QLabel {
                color: #ffb74d; /* amber */
                border: 1px solid #ffb74d;
                border-radius: 4px;
                padding: 8px;
                background-color: rgba(255, 183, 77, 0.08);
            }
            """
        )
        version_layout.addWidget(host.security_warning_label)

        host.download_btn = QPushButton("Download Selected Version")
        host.download_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        host.download_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {PRIMARY_COLOR.name()};
                color: white;
                padding: 12px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #9575cd;
            }}
            QPushButton:disabled {{
                background-color: #555;
                color: #888;
            }}
            """
        )
        host.download_btn.setFixedHeight(45)
        host.download_btn.setEnabled(False)
        host.download_btn.clicked.connect(host.download_selected_version)
        version_layout.addWidget(host.download_btn)

        # Custom download tags input
        from PyQt5.QtWidgets import QLineEdit
        host.custom_tags_input = QLineEdit()
        host.custom_tags_input.setPlaceholderText("Add custom tags (comma separated) to append to filename")
        host.custom_tags_input.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {BACKGROUND_COLOR.name()};
                color: {TEXT_COLOR.name()};
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px;
            }}
            QLineEdit:focus {{
                border: 1px solid {PRIMARY_COLOR.name()};
            }}
            """
        )
        version_layout.addWidget(host.custom_tags_input)

        details_layout.addWidget(version_group)

        # Description group
        desc_group = QGroupBox("Description")
        desc_group.setStyleSheet(
            f"""
            QGroupBox {{
                color: {SECONDARY_TEXT.name()};
                font-size: 11pt;
                border: 1px solid {PRIMARY_COLOR.name()};
                border-radius: 6px;
                margin-top: 16px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            """
        )
        desc_layout = QVBoxLayout(desc_group)

        host.description = QTextEdit()
        host.description.setReadOnly(True)
        host.description.setFont(QFont("Segoe UI", 10))
        host.description.setStyleSheet(
            f"""
            QTextEdit {{
                background-color: {BACKGROUND_COLOR.name()};
                color: {TEXT_COLOR.name()};
                border: none;
                padding: 10px;
            }}
            """
        )
        desc_layout.addWidget(host.description)

        details_layout.addWidget(desc_group)

        host.details_panel.setWidget(details_container)
        host.right_panel.addWidget(host.details_panel)
