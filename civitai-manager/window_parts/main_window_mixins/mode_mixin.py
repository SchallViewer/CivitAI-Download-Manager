from constants import PRIMARY_COLOR, CARD_BACKGROUND


class ModeMixin:
    MODE_SEARCH = 'search'
    MODE_DOWNLOADED = 'downloaded'

    def is_downloaded_mode(self):
        return getattr(self, 'current_left_view', self.MODE_SEARCH) == self.MODE_DOWNLOADED

    def _bump_ui_generation(self):
        try:
            self._ui_generation = int(getattr(self, '_ui_generation', 0)) + 1
        except Exception:
            self._ui_generation = 1

    def enter_search_mode(self):
        self._bump_ui_generation()
        self.current_left_view = self.MODE_SEARCH
        self.title_label.setText("Model Explorer")
        self.title_container.setStyleSheet(
            f"background-color: {PRIMARY_COLOR.name()}; border-radius: 6px; padding: 10px;"
        )
        self.search_input.setPlaceholderText("Search models...")
        self._apply_detail_controls_for_mode()

    def enter_downloaded_mode(self):
        self._bump_ui_generation()
        self.current_left_view = self.MODE_DOWNLOADED
        self.title_label.setText("Downloaded Models")
        self.title_container.setStyleSheet(
            f"background-color: {CARD_BACKGROUND.name()}; border-radius: 6px; padding: 10px;"
        )
        self.search_input.setPlaceholderText("Filter downloaded models...")
        self._apply_detail_controls_for_mode()

    def _apply_detail_controls_for_mode(self):
        if self.is_downloaded_mode():
            try:
                self.download_btn.setVisible(False)
                self.download_btn.setEnabled(False)
            except Exception as e:
                self._log_exception('mode:apply downloaded download_btn', e)
            try:
                if hasattr(self, 'custom_tags_input'):
                    self.custom_tags_input.setReadOnly(True)
                    self.custom_tags_input.setPlaceholderText("Select a version to view filename")
                    self.custom_tags_input.setText("")
            except Exception as e:
                self._log_exception('mode:apply downloaded custom_tags_input', e)
        else:
            try:
                self.download_btn.setVisible(True)
                self.download_btn.setEnabled(bool(getattr(self, 'current_version', None)))
            except Exception as e:
                self._log_exception('mode:apply search download_btn', e)
            try:
                if hasattr(self, 'custom_tags_input'):
                    self.custom_tags_input.setReadOnly(False)
                    self.custom_tags_input.setPlaceholderText(
                        "Add custom tags (comma separated) to append to filename"
                    )
                    if hasattr(self, '_saved_custom_tags'):
                        self.custom_tags_input.setText(self._saved_custom_tags or "")
            except Exception as e:
                self._log_exception('mode:apply search custom_tags_input', e)
            try:
                self.delete_version_btn.setVisible(False)
            except Exception as e:
                self._log_exception('mode:apply search delete_version_btn', e)
            try:
                if hasattr(self, 'show_in_folder_btn'):
                    self.show_in_folder_btn.setVisible(False)
                    self.show_in_folder_btn.setEnabled(False)
            except Exception as e:
                self._log_exception('mode:apply search show_in_folder_btn', e)
            try:
                if hasattr(self, 'downloaded_filename_group'):
                    self.downloaded_filename_group.setVisible(False)
            except Exception as e:
                self._log_exception('mode:apply search downloaded_filename_group', e)
