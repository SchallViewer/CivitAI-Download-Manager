# model_utils.py - Utility functions for model data processing
import re
import json
from typing import Dict, List, Any, Optional


class ModelDataUtils:
    """Utility class for processing model data and metadata."""

    @staticmethod
    def normalize_version_payload(version: Dict[str, Any]) -> Dict[str, Any]:
        """Return a normalized version payload with stable keys used by UI."""
        if not isinstance(version, dict):
            return {
                'id': None,
                'version_id': None,
                'name': 'Unknown',
                'baseModel': '',
                'publishedAt': '',
                'updatedAt': '',
                'trainedWords': [],
                'images': [],
                'files': [],
            }

        normalized = dict(version)
        version_id = version.get('id') or version.get('version_id')
        base_model = version.get('baseModel') or version.get('base_model') or ''
        published = version.get('publishedAt') or version.get('createdAt') or version.get('created_at') or version.get('published_at') or ''
        updated = version.get('updatedAt') or version.get('updated_at') or ''
        trained_words = version.get('trainedWords') or version.get('trained_words') or []
        images = version.get('images') or []
        files = version.get('files') or []

        normalized['id'] = version_id
        normalized['version_id'] = version_id
        normalized['name'] = version.get('name') or 'Unknown'
        normalized['baseModel'] = base_model
        normalized['publishedAt'] = published
        normalized['updatedAt'] = updated
        normalized['trainedWords'] = trained_words if isinstance(trained_words, list) else []
        normalized['images'] = images if isinstance(images, list) else []
        normalized['files'] = files if isinstance(files, list) else []
        return normalized

    @staticmethod
    def normalize_model_payload(model: Dict[str, Any]) -> Dict[str, Any]:
        """Return a normalized model payload with stable keys used by UI."""
        if not isinstance(model, dict):
            return {
                'id': None,
                'model_id': None,
                'name': 'Untitled Model',
                'type': '',
                'creator': {},
                'creator_name': 'Unknown',
                'baseModel': '',
                'description': '',
                'tags': [],
                'publishedAt': '',
                'updatedAt': '',
                'stats': {},
                'modelVersions': [],
            }

        normalized = dict(model)
        model_id = model.get('id') or model.get('model_id')
        raw_creator = model.get('creator')
        creator_name = (
            raw_creator.get('username') if isinstance(raw_creator, dict)
            else str(raw_creator) if raw_creator else 'Unknown'
        )

        versions = model.get('modelVersions') or model.get('versions') or []
        normalized_versions = []
        for version in versions:
            normalized_versions.append(ModelDataUtils.normalize_version_payload(version))

        normalized['id'] = model_id
        normalized['model_id'] = model_id
        normalized['name'] = model.get('name') or 'Untitled Model'
        normalized['type'] = model.get('type') or model.get('modelType') or model.get('model_type') or ''
        normalized['creator'] = raw_creator if isinstance(raw_creator, dict) else {'username': creator_name}
        normalized['creator_name'] = creator_name
        normalized['baseModel'] = model.get('baseModel') or model.get('base_model') or ''
        normalized['description'] = model.get('description') or 'No description available'
        normalized['tags'] = model.get('tags') or []
        normalized['publishedAt'] = model.get('publishedAt') or model.get('createdAt') or model.get('created_at') or model.get('published_at') or ''
        normalized['updatedAt'] = model.get('updatedAt') or model.get('updated_at') or ''
        normalized['stats'] = model.get('stats') or {}
        normalized['modelVersions'] = normalized_versions
        return normalized
    
    @staticmethod
    def extract_image_url(model: Dict[str, Any]) -> Optional[str]:
        """Extract the first available image URL from model data, avoiding videos."""
        def is_video_url(u):
            if not u or not isinstance(u, str):
                return False
            lower = u.lower()
            video_exts = ('.mp4', '.webm', '.mov', '.mkv', '.avi', '.gif')
            return any(ext in lower for ext in video_exts)
        
        # Try model-level images first
        for key in ('images', 'gallery', 'modelImages'):
            items = model.get(key, []) or []
            for item in items:
                if isinstance(item, dict):
                    url = item.get('url') or item.get('thumbnail')
                elif isinstance(item, str):
                    url = item
                else:
                    continue
                if url and not is_video_url(url):
                    return url
        
        # Try version-level images
        for version in (model.get('modelVersions') or []):
            for img in (version.get('images') or []):
                if isinstance(img, dict):
                    url = img.get('url') or img.get('thumbnail')
                elif isinstance(img, str):
                    url = img
                else:
                    continue
                if url and not is_video_url(url):
                    return url
        
        return None
    
    @staticmethod
    def matches_base_model(model: Dict[str, Any], base_model: str) -> bool:
        """Check if model matches the specified base model."""
        try:
            base_model_lower = base_model.lower()
            if base_model_lower in ['all', 'any base', '']:
                return True
            
            # Check model-level base model
            bm = model.get('baseModel') or model.get('base_model')
            if isinstance(bm, str) and bm.lower() == base_model_lower:
                return True
            
            # Check version-level base models
            versions = model.get('modelVersions') or model.get('versions') or []
            for v in versions:
                if not isinstance(v, dict):
                    continue
                vb = v.get('baseModel') or v.get('base_model')
                if isinstance(vb, str) and vb.lower() == base_model_lower:
                    return True
        except Exception:
            pass
        return False
    
    @staticmethod
    def safe_get_number(d: Dict[str, Any], keys: List[str], default: int = 0) -> int:
        """Return first numeric-like value found in dict for any key in keys."""
        if not d or not isinstance(d, dict):
            return default
        for k in keys:
            v = d.get(k)
            if isinstance(v, (int, float)):
                return int(v)
            try:
                if v is not None:
                    return int(v)
            except Exception:
                continue
        return default
    
    @staticmethod
    def extract_date(d: Dict[str, Any], keys: List[str]) -> str:
        """Return first non-empty ISO-like date string for keys or empty string."""
        if not d or not isinstance(d, dict):
            return ''
        for k in keys:
            v = d.get(k)
            if isinstance(v, str) and v:
                return v
        return ''
    
    @staticmethod
    def sanitize_filename(s: str) -> str:
        """Sanitize string for use as Windows filename."""
        if not isinstance(s, str):
            s = str(s or '')
        # Replace invalid characters with underscore
        s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', s)
        # Collapse multiple spaces and trim
        s = re.sub(r'\s+', ' ', s).strip()
        # Avoid names that end with dot or space
        s = s.rstrip('. ')
        # Limit length to reasonable size
        return s[:200]
