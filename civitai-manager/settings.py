import copy
import json
import os
from credential_store import WindowsCredentialStore, CredentialStoreError


class ConfigValidationError(Exception):
    """Raised when config.json is missing/invalid for startup."""


class SettingsManager:
    MODEL_PATH_TYPES = [
        "Checkpoint",
        "LORA",
        "TextualInversion",
        "Hypernetwork",
        "AestheticGradient",
        "VAE",
        "Upscaler",
        "Controlnet",
        "LoCon",
        "Poses",
        "Textures",
    ]

    MODEL_TYPE_ALIASES = {
        "checkpoint": "Checkpoint",
        "lora": "LORA",
        "textualinversion": "TextualInversion",
        "textual inversion": "TextualInversion",
        "embedding": "TextualInversion",
        "embeddings": "TextualInversion",
        "hypernetwork": "Hypernetwork",
        "aestheticgradient": "AestheticGradient",
        "aesthetic gradient": "AestheticGradient",
        "vae": "VAE",
        "upscaler": "Upscaler",
        "controlnet": "Controlnet",
        "locon": "LoCon",
        "poses": "Poses",
        "textures": "Textures",
    }

    def __init__(self, validate_on_init=True):
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json")
        self._loaded_keys = set()
        self.defaults = {
            "api_key": "",
            "download_dir": os.path.expanduser("~/CivitaiDownloads"),
            "model_download_paths": [{"model_type": "Checkpoint", "download_dir": ""}],
            "model_type_enabled": {"Checkpoint": True},
            "api_key_manager_version": 2,
            "max_concurrent": 3,
            "nsfw_filter": True,
            "auto_import": True,
            "auto_load_popular": False,
            "priority_tags": "meme,concept,character,style,clothing,pose",
            "tag_aliases": "meme,concept,chr,style,clothing,pose",
            "registry_path": r"HKCU\\Software\\CivitaiManager\\DownloadManager",
        }
        self._config_data = self._load_or_create_config()
        if validate_on_init:
            self.validate_config_integrity(raise_on_error=True)
        self._write_config()

    def _canonical_model_type(self, raw_type: str) -> str:
        t = str(raw_type or "").strip()
        if not t:
            return ""
        return self.MODEL_TYPE_ALIASES.get(t.lower(), t)

    def get_model_type_enabled_map(self):
        """Return per-model-type enable flags used to authorize downloads."""
        raw = self.get("model_type_enabled")
        defaults = {mt: (mt == "Checkpoint") for mt in self.MODEL_PATH_TYPES}
        out = dict(defaults)
        if isinstance(raw, dict):
            for key, value in raw.items():
                canonical = self._canonical_model_type(key)
                if canonical:
                    out[canonical] = bool(value)
        return out

    def set_model_type_enabled_map(self, enabled_map):
        if not isinstance(enabled_map, dict):
            enabled_map = {}
        normalized = {mt: False for mt in self.MODEL_PATH_TYPES}
        for key, value in enabled_map.items():
            canonical = self._canonical_model_type(key)
            if canonical:
                normalized[canonical] = bool(value)
        self.set("model_type_enabled", normalized)

    def is_model_type_enabled(self, model_type: str) -> bool:
        canonical = self._canonical_model_type(model_type)
        if not canonical:
            return False
        return bool(self.get_model_type_enabled_map().get(canonical, False))
    
    def get(self, key: str, default=None):
        """
        Get a setting value with optional default.
        
        Args:
            key: The setting key to retrieve
            default: The default value if the setting doesn't exist
            
        Returns:
            The setting value or the default
        """
        if key == "api_key":
            try:
                return WindowsCredentialStore.get_api_key()
            except CredentialStoreError:
                return default if default is not None else self.defaults.get("api_key")

        if key in self._config_data:
            return self._config_data.get(key)

        if key == "download_folder":
            return self._config_data.get("download_dir")

        return default if default is not None else self.defaults.get(key)
    
    def set(self, key: str, value) -> None:
        """
        Set a setting value.
        
        Args:
            key: The setting key to set
            value: The value to set
        """
        if key == "api_key":
            normalized = str(value or "").strip()
            WindowsCredentialStore.set_api_key(normalized)
            return

        target_key = "download_dir" if key == "download_folder" else key
        normalized_value = self._normalize_value(target_key, value)
        self._config_data[target_key] = normalized_value
        self._write_config()
    
    def save_settings(self) -> None:
        """Force save settings to disk."""
        self._write_config()
    
    def export_settings(self, file_path: str) -> None:
        """
        Export settings to a JSON file.
        
        Args:
            file_path: Path to save the settings JSON file
        """
        settings_data = copy.deepcopy(self._config_data)
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
                if key == "download_folder":
                    self.set("download_dir", value)
                elif key == "api_key":
                    continue
                elif key in self.defaults:
                    self.set(key, value)

            self.validate_config_integrity(raise_on_error=True)
            self._write_config()
        except Exception as e:
            raise Exception(f"Failed to import settings: {str(e)}")
    
    def clear(self) -> None:
        """Clear all settings and restore defaults."""
        try:
            WindowsCredentialStore.delete_api_key()
        except CredentialStoreError:
            pass
        self._config_data = self._build_default_config()
        self.validate_config_integrity(raise_on_error=True)
        self._write_config()

    def get_model_download_paths(self):
        """Return list of per-model-type download path definitions."""
        raw = self.get("model_download_paths")
        default_rows = [{"model_type": "Checkpoint", "download_dir": ""}]
        data = raw if isinstance(raw, list) else default_rows

        cleaned = []
        seen = set()
        for row in data or []:
            if not isinstance(row, dict):
                continue
            mt = str(row.get("model_type") or "").strip()
            dd = str(row.get("download_dir") or "").strip()
            if not mt:
                continue
            key = mt.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append({"model_type": mt, "download_dir": dd})

        if not cleaned:
            cleaned = default_rows

        return cleaned

    def set_model_download_paths(self, definitions):
        """Persist per-model-type download path definitions."""
        if not isinstance(definitions, list):
            definitions = []

        cleaned = []
        seen = set()
        for row in definitions:
            if not isinstance(row, dict):
                continue
            mt = str(row.get("model_type") or "").strip()
            dd = str(row.get("download_dir") or "").strip()
            if not mt:
                continue
            key = mt.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append({"model_type": mt, "download_dir": dd})

        if not cleaned:
            cleaned = [{"model_type": "Checkpoint", "download_dir": ""}]

        enabled_map = {mt: False for mt in self.MODEL_PATH_TYPES}
        for row in cleaned:
            canonical = self._canonical_model_type(row.get("model_type"))
            if canonical:
                enabled_map[canonical] = True

        # Keep legacy download_dir synchronized with Checkpoint for compatibility with
        # features that still read download_dir (e.g., recovery/maintenance flows).
        checkpoint_dir = ""
        for row in cleaned:
            if str(row.get("model_type") or "").strip().lower() == "checkpoint":
                checkpoint_dir = str(row.get("download_dir") or "").strip()
                break

        self.set("model_download_paths", cleaned)
        self.set_model_type_enabled_map(enabled_map)
        if checkpoint_dir:
            self.set("download_dir", checkpoint_dir)

    def get_download_dir_for_model_type(self, model_type: str):
        """Return configured download directory for a specific model type, or None if undefined."""
        canonical_target = self._canonical_model_type(model_type)
        target = str(canonical_target or "").strip().lower()
        if not target:
            return None
        for row in self.get_model_download_paths():
            mt = self._canonical_model_type(row.get("model_type")).lower()
            if mt == target:
                resolved = str(row.get("download_dir") or "").strip()
                if resolved:
                    return resolved
                break
        return None

    def delete_api_key(self) -> None:
        """Remove the api_key from Windows Credential Manager."""
        try:
            WindowsCredentialStore.delete_api_key()
        except CredentialStoreError:
            pass

    def has_api_key(self) -> bool:
        try:
            return WindowsCredentialStore.has_api_key()
        except CredentialStoreError:
            return False

    def _build_default_config(self):
        default_download_dir = str(self.defaults["download_dir"])
        try:
            os.makedirs(default_download_dir, exist_ok=True)
        except Exception:
            pass

        cfg = {
            "download_dir": default_download_dir,
            "model_download_paths": [{"model_type": "Checkpoint", "download_dir": default_download_dir}],
            "model_type_enabled": copy.deepcopy(self.defaults["model_type_enabled"]),
            "api_key_manager_version": int(self.defaults["api_key_manager_version"]),
            "max_concurrent": int(self.defaults["max_concurrent"]),
            "nsfw_filter": bool(self.defaults["nsfw_filter"]),
            "auto_import": bool(self.defaults["auto_import"]),
            "auto_load_popular": bool(self.defaults["auto_load_popular"]),
            "priority_tags": str(self.defaults["priority_tags"]),
            "tag_aliases": str(self.defaults["tag_aliases"]),
            "registry_path": str(self.defaults["registry_path"]),
        }
        return cfg

    def _load_or_create_config(self):
        path = os.path.normpath(self.config_path)
        if not os.path.isfile(path):
            self._loaded_keys = set()
            cfg = self._build_default_config()
            self._config_data = cfg
            self._write_config()
            return cfg

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigValidationError(f"Invalid JSON syntax in config file: {e}")
        except Exception as e:
            raise ConfigValidationError(f"Cannot read config file: {e}")

        if not isinstance(data, dict):
            raise ConfigValidationError("Config file root must be a JSON object.")

        self._loaded_keys = set(data.keys())

        cfg = self._build_default_config()

        for key in cfg.keys():
            if key in data:
                cfg[key] = data[key]

        # Keep unknown keys so compatibility runners can migrate/remove them.
        for key, value in data.items():
            if key not in cfg:
                cfg[key] = value

        return cfg

    def _write_config(self):
        out = {
            "download_folder": self._config_data.get("download_dir", self.defaults["download_dir"]),
            "model_download_paths": self._config_data.get("model_download_paths", []),
            "model_type_enabled": self._config_data.get("model_type_enabled", {}),
            "api_key_manager_version": self._config_data.get("api_key_manager_version", self.defaults["api_key_manager_version"]),
            "max_concurrent": self._config_data.get("max_concurrent", self.defaults["max_concurrent"]),
            "nsfw_filter": self._config_data.get("nsfw_filter", self.defaults["nsfw_filter"]),
            "auto_import": self._config_data.get("auto_import", self.defaults["auto_import"]),
            "auto_load_popular": self._config_data.get("auto_load_popular", self.defaults["auto_load_popular"]),
            "priority_tags": self._config_data.get("priority_tags", self.defaults["priority_tags"]),
            "tag_aliases": self._config_data.get("tag_aliases", self.defaults["tag_aliases"]),
            "registry_path": self._config_data.get("registry_path", self.defaults["registry_path"]),
        }

        with open(os.path.normpath(self.config_path), "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)

    def _normalize_value(self, key, value):
        if key in ("download_dir", "priority_tags", "tag_aliases", "registry_path"):
            return str(value or "").strip()
        if key == "api_key_manager_version":
            if isinstance(value, int):
                return value
            raise ValueError("'api_key_manager_version' must be an integer.")
        if key in ("nsfw_filter", "auto_import", "auto_load_popular"):
            if isinstance(value, bool):
                return value
            raise ValueError(f"'{key}' must be a boolean.")
        if key == "max_concurrent":
            if isinstance(value, int):
                return value
            raise ValueError("'max_concurrent' must be an integer.")
        if key == "model_download_paths":
            if isinstance(value, list):
                return value
            raise ValueError("'model_download_paths' must be a list.")
        if key == "model_type_enabled":
            if isinstance(value, dict):
                return value
            raise ValueError("'model_type_enabled' must be a dictionary.")
        return value

    def validate_config_integrity(self, raise_on_error=False):
        errors = []
        cfg = self._config_data

        download_dir = cfg.get("download_dir")
        if not isinstance(download_dir, str) or not download_dir.strip():
            errors.append("'download_folder' must be a non-empty string.")
        elif not os.path.isdir(download_dir):
            errors.append(f"Download folder does not exist: {download_dir}")

        model_paths = cfg.get("model_download_paths")
        if not isinstance(model_paths, list):
            errors.append("'model_download_paths' must be a list of objects.")
        else:
            seen_types = set()
            for i, row in enumerate(model_paths):
                if not isinstance(row, dict):
                    errors.append(f"model_download_paths[{i}] must be an object.")
                    continue
                model_type = row.get("model_type")
                path = row.get("download_dir")
                if not isinstance(model_type, str) or not model_type.strip():
                    errors.append(f"model_download_paths[{i}].model_type must be a non-empty string.")
                    continue
                canonical = self._canonical_model_type(model_type)
                if canonical not in self.MODEL_PATH_TYPES:
                    errors.append(f"model_download_paths[{i}].model_type is unsupported: {model_type}")
                key = canonical.lower()
                if key in seen_types:
                    errors.append(f"model_download_paths has duplicate model_type: {canonical}")
                seen_types.add(key)

                if not isinstance(path, str) or not path.strip():
                    errors.append(f"model_download_paths[{i}].download_dir must be a non-empty string.")
                elif not os.path.isdir(path):
                    errors.append(f"model_download_paths[{i}].download_dir does not exist: {path}")

        enabled_map = cfg.get("model_type_enabled")
        if not isinstance(enabled_map, dict):
            errors.append("'model_type_enabled' must be an object/dictionary.")
        else:
            for key, value in enabled_map.items():
                canonical = self._canonical_model_type(key)
                if canonical not in self.MODEL_PATH_TYPES:
                    errors.append(f"model_type_enabled has unsupported key: {key}")
                if not isinstance(value, bool):
                    errors.append(f"model_type_enabled['{key}'] must be boolean.")

        max_concurrent = cfg.get("max_concurrent")
        if not isinstance(max_concurrent, int):
            errors.append("'max_concurrent' must be an integer.")
        elif max_concurrent <= 0:
            errors.append("'max_concurrent' must be greater than 0.")

        api_key_manager_version = cfg.get("api_key_manager_version")
        if not isinstance(api_key_manager_version, int):
            errors.append("'api_key_manager_version' must be an integer.")

        for bool_key in ("nsfw_filter", "auto_import", "auto_load_popular"):
            if not isinstance(cfg.get(bool_key), bool):
                errors.append(f"'{bool_key}' must be a boolean.")

        for str_key in ("priority_tags", "tag_aliases"):
            if not isinstance(cfg.get(str_key), str):
                errors.append(f"'{str_key}' must be a string.")

        if errors and raise_on_error:
            raise ConfigValidationError("\n".join(errors))
        return errors