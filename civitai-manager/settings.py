# settings.py
import json
import os
from PyQt5.QtCore import QSettings

class SettingsManager:
    def __init__(self):
        self.settings = QSettings("CivitaiManager", "DownloadManager")
        self.defaults = {
            "api_key": "",
            "download_dir": os.path.expanduser("~/CivitaiDownloads"),
            "max_concurrent": 3,
            "nsfw_filter": True,
            "auto_import": True,
            "popular_period": "Week"  # Default to weekly popular models
        }
        # Initialize default values if not set
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
    
    def save_settings(self) -> None:
        """Force save settings to disk."""
        self.settings.sync()
    
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
        except Exception as e:
            raise Exception(f"Failed to import settings: {str(e)}")
    
    def clear(self) -> None:
        """Clear all settings and restore defaults."""
        self.settings.clear()
        # Restore defaults
        for key, value in self.defaults.items():
            self.settings.setValue(key, value)
        self.settings.sync()