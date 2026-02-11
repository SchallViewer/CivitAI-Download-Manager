# left_panel_builder.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QScrollArea, QGridLayout, QCheckBox, QPushButton
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from constants import PRIMARY_COLOR, BACKGROUND_COLOR, CARD_BACKGROUND, TEXT_COLOR, SECONDARY_TEXT


class LeftPanelBuilder:
    def __init__(self, host):
        self.host = host

    def build(self, splitter):
        host = self.host

        host.model_list_container = QWidget()
        model_list_layout = QVBoxLayout(host.model_list_container)
        model_list_layout.setContentsMargins(15, 15, 15, 15)
        model_list_layout.setSpacing(15)

        host.title_container = QWidget()
        host.title_container.setStyleSheet(
            f"background-color: {PRIMARY_COLOR.name()}; border-radius: 6px; padding: 10px;"
        )
        title_layout = QHBoxLayout(host.title_container)
        host.title_label = QLabel("Model Explorer")
        host.title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        host.title_label.setStyleSheet(f"color: {TEXT_COLOR.name()};")
        title_layout.addWidget(host.title_label)
        model_list_layout.addWidget(host.title_container)

        search_container = QWidget()
        search_container.setStyleSheet(
            f"background-color: {CARD_BACKGROUND.name()}; border-radius: 6px; padding: 10px;"
        )
        search_layout = QHBoxLayout(search_container)

        host.search_input = QLineEdit()
        host.search_input.setPlaceholderText("Search models...")
        host.search_input.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {BACKGROUND_COLOR.name()};
                color: {TEXT_COLOR.name()};
                border: 1px solid {PRIMARY_COLOR.name()};
                border-radius: 4px;
                padding: 8px;
                font-size: 12pt;
            }}
            """
        )
        search_layout.addWidget(host.search_input)
        model_list_layout.addWidget(search_container)

        host.query_log_label = QLabel("")
        host.query_log_label.setStyleSheet(
            f"color: {SECONDARY_TEXT.name()}; font-family: Consolas, 'Courier New'; font-size: 9pt; padding: 4px;"
        )
        model_list_layout.addWidget(host.query_log_label)

        filters_container = QWidget()
        filters_layout = QHBoxLayout(filters_container)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(8)

        combo_style = (
            f"QComboBox {{ background-color: {BACKGROUND_COLOR.name()}; color: {TEXT_COLOR.name()}; "
            f"border: 1px solid {PRIMARY_COLOR.name()}; border-radius: 4px; padding: 6px; }}"
            f"QComboBox::drop-down {{ border: none; }}"
            f"QComboBox QAbstractItemView {{ background-color: #1f1f1f; color: {TEXT_COLOR.name()}; "
            f"selection-background-color: {PRIMARY_COLOR.name()}; selection-color: {TEXT_COLOR.name()}; "
            f"border: 1px solid {PRIMARY_COLOR.name()}; }}"
        )

        host.model_type_combo = QComboBox()
        host.model_type_combo.addItem("All Models", "all")
        host.model_type_combo.addItem("Checkpoints", "Checkpoint")
        host.model_type_combo.addItem("LoRAs", "LORA")
        host.model_type_combo.addItem("Textures", "Textures")
        host.model_type_combo.addItem("Hypernetworks", "Hypernetwork")
        host.model_type_combo.addItem("Embeddings", "TextualInversion")
        host.model_type_combo.addItem("Aesthetic Gradients", "AestheticGradient")
        host.model_type_combo.setStyleSheet(combo_style)

        host.base_model_combo = QComboBox()
        host.base_model_combo.addItem("Any Base", None)
        host.base_model_combo.addItem("SD 1.5", "SD 1.5")
        host.base_model_combo.addItem("Illustrious", "illustrious")
        host.base_model_combo.addItem("SDXL", "SDXL 1.0")
        host.base_model_combo.addItem("Pony", "pony")
        host.base_model_combo.addItem("NoobAI (NAI)", "NoobAI")
        host.base_model_combo.setStyleSheet(combo_style)

        filters_layout.addWidget(host.model_type_combo)
        filters_layout.addWidget(host.base_model_combo)

        host.sort_combo = QComboBox()
        host.sort_combo.addItem("Relevance", None)
        host.sort_combo.addItem("Newest", "Newest")
        host.sort_combo.addItem("Most Downloaded", "Most Downloaded")
        host.sort_combo.addItem("Most Liked", "MostLiked")
        host.sort_combo.setStyleSheet(combo_style)
        filters_layout.addWidget(host.sort_combo)

        host.period_combo = QComboBox()
        host.period_combo.addItem("Any", None)
        host.period_combo.addItem("Week", "Week")
        host.period_combo.addItem("Month", "Month")
        host.period_combo.addItem("Year", "Year")
        host.period_combo.setStyleSheet(combo_style)
        filters_layout.addWidget(host.period_combo)

        host.nsfw_checkbox = QCheckBox("Include NSFW")
        host.nsfw_checkbox.setStyleSheet(f"color: {TEXT_COLOR.name()}; padding: 6px;")
        filters_layout.addWidget(host.nsfw_checkbox)

        filters_layout.addStretch()
        model_list_layout.addWidget(filters_container)

        id_container = QWidget()
        id_layout = QHBoxLayout(id_container)
        id_layout.setContentsMargins(0, 8, 0, 8)
        id_layout.setSpacing(8)
        host.model_id_input = QLineEdit()
        host.model_id_input.setPlaceholderText("Load by Model ID")
        host.model_id_input.setStyleSheet(
            f"background-color: {BACKGROUND_COLOR.name()}; color: {TEXT_COLOR.name()}; "
            f"border: 1px solid {PRIMARY_COLOR.name()}; padding: 6px;"
        )
        id_layout.addWidget(host.model_id_input)
        host.model_id_btn = QPushButton("Load")
        host.model_id_btn.setToolTip("Load model details by ID")
        host.model_id_btn.clicked.connect(host.load_model_by_id)
        id_layout.addWidget(host.model_id_btn)
        model_list_layout.addWidget(id_container)

        host.scroll_area = QScrollArea()
        host.scroll_area.setWidgetResizable(True)
        host.scroll_area.setStyleSheet(f"background-color: {BACKGROUND_COLOR.name()}; border: none;")
        host.scroll_area.verticalScrollBar().valueChanged.connect(host.check_scroll)

        host.model_grid_container = QWidget()
        host.model_grid_layout = QGridLayout(host.model_grid_container)
        host.model_grid_layout.setAlignment(Qt.AlignTop)
        host.model_grid_layout.setContentsMargins(5, 5, 5, 5)
        host.model_grid_layout.setSpacing(15)

        host.scroll_area.setWidget(host.model_grid_container)
        model_list_layout.addWidget(host.scroll_area)

        host.model_cards = []

        splitter.addWidget(host.model_list_container)
        return host.model_list_container
