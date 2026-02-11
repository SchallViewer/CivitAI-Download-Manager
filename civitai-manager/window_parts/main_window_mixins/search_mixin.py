# search_mixin.py
from PyQt5.QtWidgets import QMessageBox
from ui_components import ModelCard


class SearchMixin:
    def on_model_card_clicked(self, model_data):
        self.show_model_details(model_data)

    def load_popular_models(self):
        try:
            if not self.api_key:
                self.show_api_key_warning()
                return

            popular_models = self.api.get_popular_models()
            self.clear_model_grid()

            for i, model in enumerate(popular_models.get('items', [])):
                row = i // 4
                col = i % 4
                card = ModelCard(model)
                card.clicked.connect(self.show_model_details)
                self.model_grid_layout.addWidget(card, row, col)

                image_url = self._extract_image_url(model)
                if image_url:
                    self.load_model_image(card, image_url)

            self.status_bar.showMessage(
                f"Loaded {len(popular_models.get('items', []))} popular models"
            )
            self.right_panel.setCurrentIndex(0)
        except Exception as e:
            self.status_bar.showMessage(f"Error loading popular models: {str(e)}")

    def load_model_by_id(self):
        model_id = self.model_id_input.text().strip() if hasattr(self, 'model_id_input') else ''
        if not model_id:
            return
        try:
            mid = int(model_id) if model_id.isdigit() else model_id
            model_data = self.api.get_model_details(mid)
            if model_data and isinstance(model_data, dict) and model_data.get('id'):
                self.show_model_details(model_data)
            else:
                self.right_panel.setCurrentIndex(0)
                self.model_name.setText(f"No model found using ID {model_id}")
                self.model_creator.setText("")
                self.downloads_count.setText("0")
                self.ratings_count.setText("0")
                self.description.clear()
                self.version_list.clear()
                self.trigger_words.clear()
                self.model_image.clear()
        except Exception as e:
            print(f"Error fetching model by id {model_id}:", e)
            self.right_panel.setCurrentIndex(0)
            self.model_name.setText(f"No model found using ID {model_id}")
            self.model_creator.setText("")
            self.downloads_count.setText("0")
            self.ratings_count.setText("0")
            self.description.clear()
            self.version_list.clear()
            self.trigger_words.clear()
            self.model_image.clear()

    def search_models(self):
        try:
            self.search_manager.search_models()
            self.right_panel.setCurrentIndex(0)
        except Exception as e:
            print(f"Error in search_models: {e}")
            self.status_bar.showMessage(f"Search error: {e}")

    def check_scroll(self, value):
        try:
            self.search_manager.load_more_models_if_needed()
        except Exception as e:
            print(f"Error in scroll check: {e}")

    def load_more_models(self):
        try:
            self.search_manager.load_models()
        except Exception as e:
            print(f"Error loading more models: {e}")
            self.status_bar.showMessage(f"Error loading more models: {e}")

    def add_models_to_grid(self, models):
        for model in models:
            card = ModelCard(model)
            card.clicked.connect(lambda checked, m=model: self.show_model_details(m))
            self.model_cards.append(card)

            image_url = self._extract_image_url(model)
            if image_url:
                self.load_model_image(card, image_url)

        self.relayout_model_cards()

    def clear_model_grid(self):
        try:
            self.search_manager.clear_model_grid()
        except Exception as e:
            print(f"Error clearing model grid: {e}")
