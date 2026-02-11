# model_filter_utils.py
from typing import Dict, Any, List, Tuple


class ModelFilterUtils:
    @staticmethod
    def get_model_type(model_data: Dict[str, Any]) -> str:
        try:
            return model_data.get('type') or model_data.get('modelType') or model_data.get('model_type') or ''
        except Exception:
            return ''

    @staticmethod
    def matches_model_type(model_type: str, filter_type: str) -> bool:
        try:
            if not model_type or not filter_type:
                return True

            type_mapping = {
                'LORA': 'LORA',
                'LoRA': 'LORA',
                'Embeddings': 'TextualInversion',
                'TextualInversion': 'TextualInversion',
                'Hypernetwork': 'Hypernetwork',
                'Checkpoint': 'Checkpoint',
                'AestheticGradient': 'AestheticGradient',
                'Aesthetic': 'AestheticGradient',
                'Textures': 'Textures',
            }
            normalized_model_type = type_mapping.get(model_type, model_type)
            return normalized_model_type == filter_type
        except Exception:
            return True

    @staticmethod
    def get_base_model(model_data: Dict[str, Any]) -> str:
        try:
            base_model = model_data.get('baseModel')
            if base_model:
                return str(base_model)

            versions = model_data.get('modelVersions') or model_data.get('versions') or []
            if versions and isinstance(versions[0], dict):
                base_model = versions[0].get('baseModel') or versions[0].get('base_model')
                if base_model:
                    return str(base_model)

            return ''
        except Exception:
            return ''

    @staticmethod
    def matches_base_model(model_base: str, filter_base: str) -> bool:
        try:
            if not model_base or not filter_base:
                return True

            model_base_lower = model_base.lower()
            filter_base_lower = filter_base.lower()

            if model_base_lower == filter_base_lower:
                return True

            if 'sd 1.5' in filter_base_lower and ('sd1.5' in model_base_lower or 'sd 1.5' in model_base_lower):
                return True
            if 'sdxl' in filter_base_lower and 'sdxl' in model_base_lower:
                return True
            if 'illustrious' in filter_base_lower and 'illustrious' in model_base_lower:
                return True
            if 'pony' in filter_base_lower and 'pony' in model_base_lower:
                return True
            if 'noobai' in filter_base_lower and ('noobai' in model_base_lower or 'nai' in model_base_lower):
                return True

            return False
        except Exception:
            return True

    @staticmethod
    def has_tag(model_data: Dict[str, Any], target_tag: str) -> bool:
        try:
            if not target_tag or target_tag.lower() in ['all tags', 'all']:
                return True

            main_tag = model_data.get('main_tag')
            if main_tag:
                return main_tag.lower() == target_tag.lower()

            return False
        except Exception:
            return False

    @staticmethod
    def sort_downloaded_models(models_list: List[Tuple], sort_type: str) -> List[Tuple]:
        try:
            if not sort_type or sort_type == "newest":
                def sort_key(item):
                    k, md = item
                    try:
                        return md.get('createdAt') or md.get('created_at') or '1970-01-01'
                    except Exception:
                        return '1970-01-01'

                return sorted(models_list, key=sort_key, reverse=True)

            if sort_type == "title":
                def sort_key(item):
                    k, md = item
                    return (md.get('name') or '').lower()

                return sorted(models_list, key=sort_key)

            return models_list
        except Exception:
            return models_list
