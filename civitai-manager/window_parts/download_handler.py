# download_handler.py - Download functionality and file management
import os
from typing import Dict, List, Any
from PyQt5.QtWidgets import QMessageBox, QDialog
from PyQt5.QtCore import QTimer, Qt
from download_manager import DownloadTask
from ui_helpers import FileSelectionDialog
from window_parts.model_utils import ModelDataUtils


class DownloadHandler:
    """Handles download operations and file management."""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.utils = ModelDataUtils()
    
    def download_selected_version(self):
        """Download the currently selected model version."""
        main = self.main_window
        
        if not main.current_version or not main.current_model:
            print("DEBUG: No current version or model")
            return
        
        # Must be in search view to allow new downloads
        try:
            if getattr(main, 'current_left_view', 'search') != 'search':
                print("DEBUG: Not in search view")
                return
        except Exception:
            pass
        
        print("DEBUG: Starting download process")
        
        # Get download directory
        download_dir = main.settings_manager.get("download_dir")
        if not os.path.exists(download_dir):
            try:
                os.makedirs(download_dir)
            except Exception:
                print("DEBUG: Could not create download directory")
                return
        
        model_name = main.current_model.get('name', 'model')
        version_name = main.current_version.get('name', 'version')
        
        # Get available files
        files_list = [f for f in (main.current_version.get('files') or []) 
                     if isinstance(f, dict) and f.get('type') == 'Model']
        safetensors = [f for f in files_list if (f.get('name') or '').lower().endswith('.safetensors')]
        
        selected_files = []
        if not files_list:
            QMessageBox.warning(main, "Download Error", "No files available for this version")
            return
        
        if len(files_list) == 1:
            if safetensors:
                selected_files = safetensors
            else:
                QMessageBox.warning(
                    main,
                    "Unsafe File Type",
                    "This version only provides PickleTensor files (.pt/.pth), which are blocked due to security risks.\n"
                    "Use 'Open on Civitai' to download at your own risk."
                )
                return
        else:
            # Show file selection dialog
            dlg = FileSelectionDialog(main, files_list)
            if dlg.exec_() == QDialog.Accepted:
                selected_files = dlg.get_selected_files()
            else:
                return
            
            # Prefer safetensors over pickle files
            if any((f.get('name') or '').lower().endswith('.safetensors') for f in selected_files):
                selected_files = [f for f in selected_files if (f.get('name') or '').lower().endswith('.safetensors')]
            
            if not selected_files:
                return
        
        # Get custom tags
        custom_tags_raw = ''
        try:
            if hasattr(main, 'custom_tags_input'):
                custom_tags_raw = main.custom_tags_input.text().strip()
        except Exception:
            pass
        
        custom_tags = []
        if custom_tags_raw:
            for part in custom_tags_raw.split(','):
                p = part.strip()
                if p:
                    custom_tags.append(p)
        
        primary_tag = getattr(main, '_current_primary_tag', '') or ''
        
        # Get tag alias for filename
        def get_tag_alias(tag: str) -> str:
            """Get the filename alias for a priority tag from settings"""
            try:
                if not tag:
                    return tag
                    
                # Get priority tags and aliases from settings
                pri_raw = main.settings_manager.get("priority_tags", "") or ""
                ali_raw = main.settings_manager.get("tag_aliases", "") or ""
                priority_tags = [t.strip() for t in pri_raw.split(',') if t.strip()]
                alias_tags = [t.strip() for t in ali_raw.split(',') if t.strip()]
                
                # Find the tag in priority list and return corresponding alias
                tag_lower = tag.lower()
                for i, priority_tag in enumerate(priority_tags):
                    if priority_tag.lower() == tag_lower:
                        if i < len(alias_tags):
                            return alias_tags[i]
                        break
                
                # Fallback to original tag if no alias found
                return tag
            except Exception:
                return tag
        
        # Create download tasks
        any_added = False
        for f in selected_files:
            # Build filename
            base_fname = f"{self.utils.sanitize_filename(model_name)} - {self.utils.sanitize_filename(version_name)}"
            parts = [base_fname]
            if primary_tag:
                # Use alias for filename
                tag_alias = get_tag_alias(primary_tag)
                parts.append(self.utils.sanitize_filename(tag_alias))
            for ct in custom_tags:
                parts.append(self.utils.sanitize_filename(ct))
            fname = " - ".join(parts) + ".safetensors"
            
            url = f.get('downloadUrl')
            save_path = os.path.join(download_dir, fname)
            
            # Check if already downloaded
            try:
                model_id = main.current_model.get('id')
                version_id = main.current_version.get('id')
                if main.db_manager.is_model_downloaded(model_id, version_id, file_path=save_path):
                    continue
            except Exception:
                pass
            
            # Prepare file metadata
            original_name = f.get('name') or fname
            file_sha256 = None
            try:
                hashes = f.get('hashes') if isinstance(f, dict) else None
                if isinstance(hashes, dict):
                    file_sha256 = hashes.get('SHA256') or hashes.get('sha256')
            except Exception:
                pass
            
            # Create download task
            task = DownloadTask(
                fname,
                url,
                save_path,
                main.api_key,
                model_data=main.current_model,
                version=main.current_version
            )
            task.original_file_name = original_name
            task.file_sha256 = file_sha256
            task.primary_tag = primary_tag
            
            try:
                main.download_manager.add_download(task)
                any_added = True
            except Exception:
                pass
        
        if any_added:
            main.status_bar.showMessage("Added selected file(s) to download queue", 6000)
    
    def delete_selected_version(self):
        """Delete the currently selected model version."""
        main = self.main_window
        
        try:
            # Only allow deletion in Downloaded Explorer context
            if getattr(main, 'current_left_view', 'search') != 'downloaded':
                return
            
            if not main.current_model or not main.current_version:
                return
            
            model_id = main.current_model.get('id') or main.current_model.get('model_id')
            version_id = main.current_version.get('id') or main.current_version.get('version_id')
            if not model_id or not version_id:
                return
            
            # Verify version has download record
            try:
                if not main.db_manager.has_download_record(model_id, version_id):
                    return
            except Exception:
                return
            
            # Confirm with user
            from PyQt5.QtWidgets import QMessageBox
            ret = QMessageBox.question(
                main,
                "Confirm Delete",
                f"Delete version '{main.current_version.get('name','Unknown')}' of model '{main.current_model.get('name','Unknown')}'?\n\nThis will:\n - Remove the model file from disk (if present)\n - Remove version & model DB metadata (model removed if last version)\n - Mark history entries as 'Deleted' (not removed).",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if ret != QMessageBox.Yes:
                return
            
            # Perform deletion
            summary = main.db_manager.delete_model_version(model_id, version_id)
            
            # Refresh UI
            remaining = main.db_manager.get_model_versions(model_id)
            if not remaining:
                # Clear details panel since model removed
                main.version_list.clear()
                main.delete_version_btn.setEnabled(False)
                main.download_btn.setEnabled(False)
                main.trigger_words.clear()
                try:
                    main.model_name.setText("Model deleted")
                except Exception:
                    pass
                
                # Refresh downloaded explorer grid
                try:
                    if getattr(main, 'current_left_view', 'search') == 'downloaded':
                        if hasattr(main, '_left_agg_downloaded'):
                            try:
                                del main._left_agg_downloaded
                            except Exception:
                                pass
                        from window_parts.downloaded_manager import DownloadedManager
                        dm = DownloadedManager(main)
                        dm.load_downloaded_models_left()
                except Exception:
                    pass
            else:
                # Repopulate version list
                main.version_list.clear()
                for v in remaining:
                    from PyQt5.QtWidgets import QListWidgetItem
                    item = QListWidgetItem(v.get('name','Unnamed'))
                    item.setData(Qt.UserRole, v)
                    main.version_list.addItem(item)
                
                main.delete_version_btn.setEnabled(False)
                main.download_btn.setEnabled(False)
                main.trigger_words.clear()
                
                # Refresh card if still exists
                try:
                    if getattr(main, 'current_left_view', 'search') == 'downloaded':
                        if hasattr(main, '_left_agg_downloaded'):
                            try:
                                del main._left_agg_downloaded
                            except Exception:
                                pass
                        from window_parts.downloaded_manager import DownloadedManager
                        dm = DownloadedManager(main)
                        dm.load_downloaded_models_left()
                except Exception:
                    pass
            
            # Update history panel
            try:
                main.load_download_history()
            except Exception:
                pass
            
            # Status feedback
            try:
                main.status_bar.showMessage(
                    f"Deleted version {version_id} (files: {summary.get('deleted_files')}, images: {summary.get('deleted_image_files')})",
                    7000
                )
            except Exception:
                pass
                
        except Exception as e:
            try:
                main.status_bar.showMessage(f"Error deleting version: {e}", 7000)
            except Exception:
                pass
