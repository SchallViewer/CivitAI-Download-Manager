# utils_mixin.py


class UtilsMixin:
    def _extract_image_url(self, model):
        return self.utils.extract_image_url(model)

    def _matches_base_model(self, model, base_model):
        return self.utils.matches_base_model(model, base_model)

    def _safe_get_number(self, d, keys, default=0):
        return self.utils.safe_get_number(d, keys, default)

    def _extract_date(self, d, keys):
        return self.utils.extract_date(d, keys)
