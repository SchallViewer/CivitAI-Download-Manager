# delegation_mixin.py


class DelegationMixin:
    def show_downloaded_explorer(self):
        self.downloaded_manager.show_downloaded_explorer()

    def load_downloaded_models(self):
        self.downloaded_manager.load_downloaded_models()

    def load_downloaded_models_left(self):
        self.downloaded_manager.load_downloaded_models_left()

    def show_downloaded_model_details(self, model_data):
        self.downloaded_manager.show_downloaded_model_details(model_data)

    def download_selected_version(self):
        self.download_handler.download_selected_version()

    def delete_selected_version(self):
        self.download_handler.delete_selected_version()
