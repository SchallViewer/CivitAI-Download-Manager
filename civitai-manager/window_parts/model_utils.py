# model_utils.py - Utility functions for model data processing
import re
import json
from typing import Dict, List, Any, Optional


class ModelDataUtils:
    """Utility class for processing model data and metadata."""
    
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
            if base_model.lower() == 'all':
                return True
            
            # Check model-level base model
            bm = model.get('baseModel') or model.get('base_model')
            if isinstance(bm, str) and bm.lower() == str(base_model).lower():
                return True
            
            # Check version-level base models
            versions = model.get('modelVersions') or model.get('versions') or []
            for v in versions:
                if not isinstance(v, dict):
                    continue
                vb = v.get('baseModel') or v.get('base_model')
                if isinstance(vb, str) and vb.lower() == str(base_model).lower():
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
