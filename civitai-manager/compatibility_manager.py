from credential_store import WindowsCredentialStore, CredentialStoreError


class CompatibilityManager:
    """Runs one-way compatibility migrations for legacy configurations."""

    def __init__(self, settings_manager):
        self.settings_manager = settings_manager

    def run_all(self) -> bool:
        changed = False
        changed = self._migrate_download_folder_key() or changed
        changed = self._migrate_legacy_download_dir_to_model_paths() or changed
        changed = self._enforce_api_key_manager_version() or changed
        changed = self._cleanup_compatibility_keys() or changed

        if changed:
            self.settings_manager.save_settings()
        return changed

    def _migrate_download_folder_key(self) -> bool:
        cfg = self.settings_manager._config_data
        if "download_folder" not in cfg:
            return False

        changed = False
        legacy_folder = str(cfg.get("download_folder") or "").strip()
        current_dir = str(cfg.get("download_dir") or "").strip()
        source_had_download_dir = "download_dir" in getattr(self.settings_manager, "_loaded_keys", set())

        if legacy_folder and (not source_had_download_dir or not current_dir):
            cfg["download_dir"] = legacy_folder
            changed = True

        del cfg["download_folder"]
        return True

    def _migrate_legacy_download_dir_to_model_paths(self) -> bool:
        legacy_dir = str(self.settings_manager.get("download_dir", "") or "").strip()
        defs = self.settings_manager.get_model_download_paths()
        if not isinstance(defs, list):
            defs = []

        changed = False
        checkpoint = None
        for row in defs:
            if str(row.get("model_type") or "").strip().lower() == "checkpoint":
                checkpoint = row
                break

        if not defs:
            defs = [{"model_type": "Checkpoint", "download_dir": legacy_dir}]
            changed = True
        elif checkpoint is not None and legacy_dir and not str(checkpoint.get("download_dir") or "").strip():
            checkpoint["download_dir"] = legacy_dir
            changed = True

        if changed:
            self.settings_manager.set_model_download_paths(defs)
        return changed

    def _enforce_api_key_manager_version(self) -> bool:
        cfg = self.settings_manager._config_data
        version = cfg.get("api_key_manager_version", 0)
        if not isinstance(version, int):
            version = 0

        if version < 2:
            try:
                WindowsCredentialStore.delete_api_key()
            except CredentialStoreError:
                pass
            cfg["api_key_manager_version"] = 2
            return True
        return False

    def _cleanup_compatibility_keys(self) -> bool:
        cfg = self.settings_manager._config_data
        changed = False
        if "download_folder" in cfg:
            del cfg["download_folder"]
            changed = True
        return changed
