# history_mixin.py
import json
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QFileDialog, QMessageBox, QTreeWidgetItem
from ui_components import DownloadProgressWidget
from constants import SECONDARY_TEXT


class HistoryMixin:
    def show_downloads_panel(self):
        self.right_panel.setCurrentIndex(1)
        self.update_downloads_panel()
        try:
            has_last = bool(getattr(self, '_last_details_model_data', None))
            if hasattr(self, 'back_to_details_from_downloads_btn'):
                self.back_to_details_from_downloads_btn.setEnabled(has_last)
        except Exception:
            pass

    def show_history_panel(self):
        self.right_panel.setCurrentIndex(2)
        self.load_download_history()
        try:
            has_last = bool(getattr(self, '_last_details_model_data', None))
            if hasattr(self, 'back_to_details_from_history_btn'):
                self.back_to_details_from_history_btn.setEnabled(has_last)
        except Exception:
            pass

    def back_to_last_details(self):
        try:
            data = getattr(self, '_last_details_model_data', None)
            if not data:
                return
            if bool(getattr(self, '_last_details_from_downloaded', False)):
                self.show_downloaded_model_details(data)
            else:
                self.show_model_details(data)
        except Exception:
            pass

    def update_downloads_panel(self):
        while self.active_downloads_list.count():
            child = self.active_downloads_list.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        while self.queue_list.count():
            child = self.queue_list.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        active_downloads = self.download_manager.get_active_downloads()
        queued_downloads = self.download_manager.get_queued_downloads()

        if active_downloads:
            for task in active_downloads:
                widget = DownloadProgressWidget(task, self.download_manager)
                try:
                    widget.cancel_requested.connect(
                        lambda fn, mgr=self.download_manager: (mgr.cancel_download(fn), self.update_downloads_panel())
                    )
                except Exception:
                    pass
                self.active_downloads_list.addWidget(widget)
        else:
            placeholder = QLabel("No active downloads")
            placeholder.setStyleSheet(f"color: {SECONDARY_TEXT.name()}; font-style: italic;")
            placeholder.setAlignment(Qt.AlignCenter)
            self.active_downloads_list.addWidget(placeholder)

        if queued_downloads:
            for task in queued_downloads:
                widget = QLabel(f"{task.file_name} - Queued")
                widget.setStyleSheet(f"color: {SECONDARY_TEXT.name()}; padding: 8px;")
                widget.setMinimumHeight(40)
                self.queue_list.addWidget(widget)
        else:
            placeholder = QLabel("Download queue is empty")
            placeholder.setStyleSheet(f"color: {SECONDARY_TEXT.name()}; font-style: italic;")
            placeholder.setAlignment(Qt.AlignCenter)
            self.queue_list.addWidget(placeholder)

    def load_download_history(self):
        self.history_tree.clear()
        history = self.db_manager.get_download_history()
        try:
            if getattr(self, 'hide_failed_checkbox', None) and self.hide_failed_checkbox.isChecked():
                history = [h for h in history if (h.get('status') or '').lower() not in ('failed', 'deleted')]
        except Exception:
            pass

        tag_groups = {}
        for item in history:
            tag = item.get('main_tag', 'Other')
            if tag not in tag_groups:
                tag_groups[tag] = []
            tag_groups[tag].append(item)

        for tag, items in tag_groups.items():
            group_item = QTreeWidgetItem(self.history_tree, [tag])
            group_item.setExpanded(True)

            for item in items:
                model_name = item.get('model_name', 'Unknown')
                model_id = str(item.get('model_id', ''))
                version = item.get('version', 'Unknown')
                date = item.get('download_date', 'Unknown')
                size = f"{item.get('file_size', 0):.1f} MB"
                status = item.get('status', 'Completed')

                QTreeWidgetItem(group_item, [
                    model_name, model_id, version, date, size, status
                ])

        self.history_tree.expandAll()

    def refresh_download_history_status(self):
        counts = {"missing": 0, "restored": 0}
        try:
            download_dir = self.settings_manager.get("download_dir") or ''
            counts = self.db_manager.update_file_statuses(download_dir)
        except Exception:
            pass
        self.load_download_history()
        try:
            self.status_bar.showMessage(
                "History refreshed. Missing: {missing} Restored(existing): {restored} "
                "Renamed restored: {renamed_restored} (hashed {hashed_files}/{scanned_files} files)".format(
                    missing=counts.get('missing', 0),
                    restored=counts.get('restored', 0),
                    renamed_restored=counts.get('renamed_restored', 0),
                    hashed_files=counts.get('hashed_files', 0),
                    scanned_files=counts.get('scanned_files', 0),
                ),
                8000,
            )
        except Exception:
            pass

    def export_history(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export History", "", "JSON Files (*.json)"
        )
        if file_path:
            try:
                history = self.db_manager.get_minimal_download_export()
            except Exception:
                history = self.db_manager.get_download_history()
            try:
                with open(file_path, 'w') as f:
                    json.dump(history, f, indent=2)
                self.status_bar.showMessage(f"History exported to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export history: {str(e)}")

    def import_history(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import History", "", "JSON Files (*.json)"
        )
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    history = json.load(f)
                self.db_manager.import_history(history)
                self.load_download_history()
                self.status_bar.showMessage(f"History imported from {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import history: {str(e)}")

    def clear_history(self):
        reply = QMessageBox.question(
            self, "Clear History", "Are you sure you want to clear all download history?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db_manager.clear_history()
            self.history_tree.clear()
            self.status_bar.showMessage("Download history cleared")
