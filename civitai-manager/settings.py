# settings.py
import json
import os
from PyQt5.QtCore import QSettings

class SettingsManager:
    def __init__(self):
        self.settings = QSettings("CivitaiManager", "DownloadManager")
        # location of external JSON config (parent directory of this package)
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config.json')
        self.defaults = {
            "api_key": "",
            "download_dir": os.path.expanduser("~/CivitaiDownloads"),
            "max_concurrent": 3,
            "nsfw_filter": True,
            "auto_import": True,
            # Comma-separated ordered list of tag priorities (highest first) used for filename primary tag selection
            "priority_tags": "meme,concept,character,style,clothing,pose",
            # workspace images directory is fixed to 'images' under workspace; not user-configurable
        }
        # load external config first (if exists) so QSettings picks up values
        self._load_external_config()
        # Initialize default values if not set (after external merge)
        for key, default_value in self.defaults.items():
            if self.settings.value(key) is None:
                self.settings.setValue(key, default_value)
    
    def get(self, key: str, default=None) -> str:
        """
        Get a setting value with optional default.
        
        Args:
            key: The setting key to retrieve
            default: The default value if the setting doesn't exist
            
        Returns:
            The setting value or the default
        """
        value = self.settings.value(key)
        if value is None:
            return default if default is not None else self.defaults.get(key)
        return value
    
    def set(self, key: str, value) -> None:
        """
        Set a setting value.
        
        Args:
            key: The setting key to set
            value: The value to set
        """
        self.settings.setValue(key, value)
        self.settings.sync()  # Ensure settings are saved immediately
        self._write_external_config()
    
    def save_settings(self) -> None:
        """Force save settings to disk."""
        self.settings.sync()
        # Also persist consolidated settings to external JSON file
        self._write_external_config()
    
    def export_settings(self, file_path: str) -> None:
        """
        Export settings to a JSON file.
        
        Args:
            file_path: Path to save the settings JSON file
        """
        settings_data = {}
        for key in self.defaults.keys():
            value = self.settings.value(key)
            if value is not None:
                settings_data[key] = value
            else:
                settings_data[key] = self.defaults[key]
                
        with open(file_path, 'w') as f:
            json.dump(settings_data, f, indent=4)
    
    def import_settings(self, file_path: str) -> None:
        """
        Import settings from a JSON file.
        
        Args:
            file_path: Path to the settings JSON file to import
        """
        try:
            with open(file_path, 'r') as f:
                settings_data = json.load(f)
            
            for key, value in settings_data.items():
                if key in self.defaults:
                    self.set(key, value)
            
            self.settings.sync()  # Ensure imported settings are saved
            self._write_external_config()
        except Exception as e:
            raise Exception(f"Failed to import settings: {str(e)}")
    
    def clear(self) -> None:
        """Clear all settings and restore defaults."""
        self.settings.clear()
        # Restore defaults
        for key, value in self.defaults.items():
            self.settings.setValue(key, value)
        self.settings.sync()
        self._write_external_config()

    # --- External JSON config helpers ---
    def _load_external_config(self):
        try:
            path = os.path.normpath(self.config_path)
            if os.path.isfile(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # Map legacy keys if needed
                key_map = {
                    'download_folder': 'download_dir',
                    'api_key': 'api_key',
                    'priority_tags': 'priority_tags'
                }
                for legacy, new_key in key_map.items():
                    if legacy in data and data[legacy] is not None:
                        self.settings.setValue(new_key, data[legacy])
        except Exception:
            pass

    def _write_external_config(self):
        try:
            path = os.path.normpath(self.config_path)
            # gather all known settings
            out = {}
            for key in self.defaults.keys():
                # external file uses 'download_folder' historically
                if key == 'download_dir':
                    out['download_folder'] = self.get(key)
                else:
                    out[key] = self.get(key)
            # ensure priority_tags present even if empty
            out.setdefault('priority_tags', self.defaults['priority_tags'])
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(out, f, indent=2)
        except Exception:
            pass