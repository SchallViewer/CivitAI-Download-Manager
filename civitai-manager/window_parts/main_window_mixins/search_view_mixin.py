# search_view_mixin.py
from ui_components import ModelCard
from constants import PRIMARY_COLOR


class SearchViewMixin:
    def handle_filter_change(self):
        current_view = getattr(self, 'current_left_view', 'search')
        print(f"DEBUG: handle_filter_change called - current_view: {current_view}")
        if current_view == 'downloaded':
            print("DEBUG: Filtering downloaded models")
            self.downloaded_manager.filter_downloaded_models()
        else:
            print("DEBUG: Performing API search")
            self.search_models()

    def handle_search_input(self):
        current_view = getattr(self, 'current_left_view', 'search')
        print(f"DEBUG: handle_search_input called - current_view: {current_view}")
        if current_view == 'downloaded':
            print("DEBUG: In downloaded explorer - no action needed")
            return
        print("DEBUG: In search explorer - performing API search")
        self.search_models()

    def handle_search_text_changed(self):
        current_view = getattr(self, 'current_left_view', 'search')
        print(f"DEBUG: handle_search_text_changed called - current_view: {current_view}")
        if current_view == 'downloaded':
            try:
                self.progressive_render_timer.stop()
            except Exception:
                pass

            try:
                self.download_filter_timer.stop()
                self.download_filter_timer.start(300)
            except Exception:
                self.downloaded_manager.filter_downloaded_models()
        else:
            print("DEBUG: In search explorer - text changed (no immediate action)")

    def show_search_panel(self):
        print("DEBUG: show_search_panel called - switching to search explorer")
        current_model_id = None
        current_version_id = None
        try:
            if hasattr(self, 'current_model') and self.current_model:
                current_model_id = self.current_model.get('id')
            if hasattr(self, 'current_version') and self.current_version:
                current_version_id = self.current_version.get('id')
        except Exception:
            pass

        try:
            print("DEBUG: Setting current_left_view to 'search'")
            self.current_left_view = 'search'
            self.title_label.setText("Model Explorer")
            self.title_container.setStyleSheet(
                f"background-color: {PRIMARY_COLOR.name()}; border-radius: 6px; padding: 10px;"
            )
        except Exception:
            pass

        try:
            print("DEBUG: Updating search input placeholder")
            self.search_input.setPlaceholderText("Search models...")
        except Exception:
            pass

        try:
            print("DEBUG: Restoring search filters")
            self.downloaded_manager.restore_search_filters()
        except Exception as e:
            print(f"DEBUG: Error restoring search filters: {e}")

        try:
            print("DEBUG: Re-enabling search functionality")
            if hasattr(self, 'download_filter_timer'):
                print("DEBUG: Stopping download_filter_timer")
                self.download_filter_timer.stop()
            if hasattr(self, 'progressive_render_timer'):
                print("DEBUG: Stopping progressive_render_timer")
                self.progressive_render_timer.stop()

            try:
                print("DEBUG: Disconnecting existing search handlers")
                self.search_input.textChanged.disconnect()
            except Exception:
                pass
            try:
                self.search_input.returnPressed.disconnect()
            except Exception:
                pass

            print("DEBUG: Reconnecting search handlers")
            self.search_input.textChanged.connect(self.handle_search_text_changed)
            self.search_input.returnPressed.connect(self.handle_search_input)

        except Exception as e:
            print(f"Error re-enabling search functionality: {e}")

        try:
            self.download_btn.setVisible(True)
            self.download_btn.setEnabled(bool(getattr(self, 'current_version', None)))
        except Exception:
            pass

        try:
            if hasattr(self, 'custom_tags_input'):
                self.custom_tags_input.setReadOnly(False)
                self.custom_tags_input.setPlaceholderText(
                    "Add custom tags (comma separated) to append to filename"
                )
                if hasattr(self, '_saved_custom_tags'):
                    self.custom_tags_input.setText(self._saved_custom_tags or "")
        except Exception:
            pass

        try:
            self.delete_version_btn.setVisible(False)
        except Exception:
            pass

        try:
            if hasattr(self, 'show_in_folder_btn'):
                self.show_in_folder_btn.setVisible(False)
                self.show_in_folder_btn.setEnabled(False)
        except Exception:
            pass

        try:
            if hasattr(self, 'downloaded_filename_group'):
                self.downloaded_filename_group.setVisible(False)
        except Exception:
            pass

        try:
            if getattr(self, '_search_cache', None):
                try:
                    self.clear_model_grid()
                except Exception:
                    pass
                for md in self._search_cache:
                    try:
                        card = ModelCard(md)
                        card.clicked.connect(lambda checked=False, m=md: self.show_model_details(m))
                        self.model_cards.append(card)
                        try:
                            url = self._extract_image_url(md)
                            if url:
                                self.load_model_image(card, url)
                        except Exception:
                            pass
                    except Exception:
                        continue
                try:
                    self.relayout_model_cards()
                except Exception:
                    pass
        except Exception:
            pass

        try:
            saved_selection = getattr(self, '_saved_selection', {})
            if (
                saved_selection.get('view') == 'downloaded'
                and saved_selection.get('model_id')
                and current_model_id != saved_selection.get('model_id')
            ):
                self.restore_model_selection(
                    saved_selection.get('model_id'),
                    saved_selection.get('version_id'),
                )
        except Exception:
            pass

        self.right_panel.setCurrentIndex(0)

    def restore_model_selection(self, target_model_id, target_version_id=None):
        try:
            if not self.model_cards:
                return

            for card in self.model_cards:
                card_model_data = getattr(card, 'model_data', {})
                if card_model_data.get('id') == target_model_id:
                    if hasattr(card, 'clicked'):
                        card.clicked.emit()
                    break
        except Exception:
            pass
