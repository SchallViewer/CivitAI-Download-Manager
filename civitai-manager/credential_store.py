import keyring


class CredentialStoreError(Exception):
    pass


class WindowsCredentialStore:
    SERVICE_NAME = "CivitaiManager"
    USERNAME = "api_key"

    @classmethod
    def is_available(cls) -> bool:
        try:
            backend_name = keyring.get_keyring().__class__.__name__.lower()
            return "windows" in backend_name or "winvault" in backend_name
        except Exception:
            return False

    @classmethod
    def get_api_key(cls) -> str:
        try:
            value = keyring.get_password(cls.SERVICE_NAME, cls.USERNAME)
            return value or ""
        except Exception as e:
            raise CredentialStoreError(f"Failed to read API key from Windows Credential Manager: {e}")

    @classmethod
    def set_api_key(cls, api_key: str) -> None:
        try:
            keyring.set_password(cls.SERVICE_NAME, cls.USERNAME, str(api_key or ""))
        except Exception as e:
            raise CredentialStoreError(f"Failed to save API key to Windows Credential Manager: {e}")

    @classmethod
    def delete_api_key(cls) -> None:
        try:
            keyring.delete_password(cls.SERVICE_NAME, cls.USERNAME)
        except keyring.errors.PasswordDeleteError:
            pass
        except Exception as e:
            raise CredentialStoreError(f"Failed to delete API key from Windows Credential Manager: {e}")

    @classmethod
    def has_api_key(cls) -> bool:
        return bool(cls.get_api_key().strip())
