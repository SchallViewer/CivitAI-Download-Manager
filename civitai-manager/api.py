import requests
import logging
from urllib.parse import quote
from constants import API_BASE_URL

class CivitaiAPI:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.base_url = API_BASE_URL
    
    def search_models(self, query="", model_type=None, base_model=None, nsfw=False, sort=None, period=None, limit=20, page=1, cursor=None, timeout=30):
        # Build params only with non-empty values to avoid sending empty keys
        params = {}

        if query:
            params["query"] = query

        if model_type:
            type_map = {
                "checkpoint": "Checkpoint",
                "lora": "LORA",
                "lor a": "LORA",
                "textualinversion": "TextualInversion",
                "textual inversion": "TextualInversion",
                "embedding": "TextualInversion",
                "embeddings": "TextualInversion",
                "hypernetwork": "Hypernetwork",
                "aesthetic": "AestheticGradient",
                "aestheticgradient": "AestheticGradient",
                "locon": "LoCon",
                "controlnet": "Controlnet",
                "poses": "Poses",
            }
            model_types = (
                model_type.split(",") if isinstance(model_type, str)
                else list(model_type)
            )
            api_types = [
                type_map.get(str(value).strip().lower(), str(value).strip())
                for value in model_types
                if str(value).strip() and str(value).strip().lower() != "all"
            ]
            if api_types:
                params["types"] = api_types

        if base_model:
            base_models = (
                base_model.split(",") if isinstance(base_model, str)
                else list(base_model)
            )
            base_models = [
                str(value).strip() for value in base_models
                if str(value).strip()
                and str(value).strip().lower() not in ("all", "any base")
            ]
            if base_models:
                params["baseModels"] = base_models

        # Include NSFW param when explicitly set; allow None to mean omit
        if nsfw is not None:
            params["nsfw"] = str(nsfw).lower()
        if sort:
            params["sort"] = sort
        if period:
            params["period"] = period
        params["limit"] = limit
        # Use cursor for query-based searches (cursor-based pagination required)
        if query:
            if cursor:
                params["cursor"] = cursor
        else:
            params["page"] = page

        url = f"{self.base_url}/models"
        # Prepare a full URL for debugging (shows encoded query params)
        try:
            prep = requests.Request('GET', url, params=params, headers=self.headers).prepare()
            full_url = prep.url
        except Exception:
            full_url = url

        # Print debug info to terminal to help trace 400/param issues
        print(f"CivitaiAPI.search_models -> Request URL: {full_url}")
        print(f"CivitaiAPI.search_models -> Params: {params}")
        logging.debug("CivitaiAPI.search_models -> URL: %s, params: %s", url, params)

        response = requests.get(url, params=params, headers=self.headers, timeout=timeout)
        try:
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.HTTPError as e:
            # include response body in exception for easier debugging
            body = None
            try:
                body = response.text
            except Exception:
                body = '<unreadable body>'
            msg = f"HTTPError {response.status_code} for URL: {response.url} - body: {body}"
            # Extra prints for immediate terminal debugging
            print("CivitaiAPI.search_models -> HTTPError", response.status_code)
            try:
                print("CivitaiAPI.search_models -> Response URL:", response.url)
            except Exception:
                pass
            try:
                print("CivitaiAPI.search_models -> Response body:", body)
            except Exception:
                pass
            logging.error(msg)
            raise requests.exceptions.HTTPError(msg) from e
        except ValueError:
            data = None

        if not data:
            return {"items": [], "metadata": {}}

        return data
    
    def get_popular_models(self, period="Week", limit=20):
        """Fetch popular models by period (Week or Month)"""
        params = {
            "period": period,
            "limit": limit,
            "sort": "Most Downloaded"
        }
        response = requests.get(
            f"{self.base_url}/models",
            params=params,
            headers=self.headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    
    def get_model_details(self, model_id, timeout=30):
        model_id = self._positive_id(model_id, "model_id")
        response = requests.get(
            f"{self.base_url}/models/{model_id}",
            headers=self.headers,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()
    
    def get_model_version(self, version_id):
        version_id = self._positive_id(version_id, "version_id")
        response = requests.get(
            f"{self.base_url}/model-versions/{version_id}",
            headers=self.headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_model_version_by_hash(self, file_hash, timeout=30):
        if not file_hash:
            raise ValueError("file_hash must not be empty")
        path_hash = quote(str(file_hash), safe="")
        response = requests.get(
            f"{self.base_url}/model-versions/by-hash/{path_hash}",
            headers=self.headers,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _positive_id(value, name):
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be a positive integer")
        if parsed <= 0:
            raise ValueError(f"{name} must be a positive integer")
        return parsed