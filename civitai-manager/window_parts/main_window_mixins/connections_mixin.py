# connections_mixin.py
from PyQt5.QtCore import QTimer


class ConnectionsMixin:
    def init_connections(self):
        self.search_action.triggered.connect(self.show_search_panel)
        self.downloads_action.triggered.connect(self.show_downloads_panel)
        self.history_action.triggered.connect(self.show_history_panel)
        self.settings_action.triggered.connect(self.open_settings)
        self.search_input.returnPressed.connect(self.handle_search_input)
        self.search_input.textChanged.connect(self.handle_search_text_changed)

        self.download_filter_timer = QTimer()
        self.download_filter_timer.setSingleShot(True)
        self.download_filter_timer.timeout.connect(self.downloaded_manager.filter_downloaded_models)

        self.progressive_render_timer = QTimer()
        self.progressive_render_timer.timeout.connect(self.downloaded_manager.render_next_batch)

        self.model_type_combo.currentIndexChanged.connect(self.handle_filter_change)
        self.base_model_combo.currentIndexChanged.connect(self.handle_filter_change)
        self.sort_combo.currentIndexChanged.connect(self.handle_filter_change)
        self.period_combo.currentIndexChanged.connect(self.handle_filter_change)
        try:
            self.nsfw_checkbox.stateChanged.connect(self.search_models)
        except Exception:
            pass
