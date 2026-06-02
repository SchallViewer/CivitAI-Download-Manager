# settings_mixin.py
from PyQt5.QtWidgets import QMessageBox, QDialog
from settings_dialog import SettingsDialog
from api import CivitaiAPI


class SettingsMixin:
    def show_api_key_warning(self):
        QMessageBox.warning(
            self,
            "API Key Required",
            "A Civitai API key is required to access model data.\n\n"
            "Please go to Settings > API Configuration to add your API key.",
            QMessageBox.Ok,
        )
        self.open_settings()

    def open_settings(self):
        dialog = SettingsDialog(self.settings_manager, self)
        dialog.exec_()
        new_api_key = self.settings_manager.get("api_key")
        if new_api_key != self.api_key:
            self.api_key = new_api_key
            self.api = CivitaiAPI(api_key=self.api_key)
            if self.model_grid_layout.count() > 0:
                self.load_popular_models()
