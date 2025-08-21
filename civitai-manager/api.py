import requests
import logging
from urllib.parse import urlencode
from constants import API_BASE_URL, ModelType, MainTag

class CivitaiAPI:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.base_url = API_BASE_URL
    
    def search_models(self, query="", model_type=None, base_model=None, nsfw=False, sort=None, period=None, limit=20, page=1, cursor=None):
        # Build params only with non-empty values to avoid sending empty keys
        params = {}

        if query:
            params["query"] = query

        if model_type and str(model_type).lower() != "all":
            # Convert to Civitai's expected type names
            type_map = {
                # common canonical -> API value
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
                "textures": "Textures",
                "locon": "LoCon",
                "controlnet": "Controlnet",
                "poses": "Poses",
            }
            api_type = type_map.get(model_type, model_type)
            params["types"] = api_type

        if base_model:
            # API expects baseModels as a comma-separated or single value
            params["baseModels"] = base_model

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

        response = requests.get(url, params=params, headers=self.headers, timeout=30)
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
        response = requests.get(f"{self.base_url}/models", 
                               params=params, 
                               headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def get_model_details(self, model_id):
        response = requests.get(f"{self.base_url}/models/{model_id}", 
                               headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def get_model_version(self, version_id):
        response = requests.get(f"{self.base_url}/model-versions/{version_id}", 
                               headers=self.headers)
        response.raise_for_status()
        return response.json()