# image_mixin.py
from ui_helpers import ImageLoaderThread
from ui_components import ModelCard


class ImageMixin:
    def load_model_image(self, card, image_url):
        headers = self.api.headers if hasattr(self, 'api') else None
        try:
            setattr(card, '_expected_image_url', image_url)
        except Exception:
            pass
        thread = ImageLoaderThread(image_url, card, headers=headers)
        thread.image_loaded.connect(self.set_card_image)
        thread.start()
        self.image_loader_threads.append(thread)

    def set_card_image(self, url, data_bytes, card):
        try:
            try:
                expected = getattr(card, '_expected_image_url', None)
                if expected and url != expected:
                    return
            except Exception:
                pass

            if isinstance(card, ModelCard) and isinstance(data_bytes, (bytes, bytearray)):
                b = bytes(data_bytes)
                if b[:6] in (b'GIF87a', b'GIF89a'):
                    tried = self.card_image_attempts.setdefault(id(card), set())
                    candidates = []
                    mdl = getattr(card, 'model_data', {}) or {}

                    def _is_video(u):
                        if not u or not isinstance(u, str):
                            return False
                        low = u.lower()
                        for ext in ('.mp4', '.webm', '.mov', '.mkv', '.avi'):
                            if low.endswith(ext) or ext in low:
                                return True
                        return False

                    images = mdl.get('images') or []
                    if not images:
                        versions = mdl.get('modelVersions') or mdl.get('versions') or []
                        if versions and isinstance(versions[0], dict):
                            images = versions[0].get('images') or []
                    for img in images:
                        if isinstance(img, dict):
                            cand = img.get('url') or img.get('thumbnail')
                        else:
                            cand = str(img)
                        if cand and (not _is_video(cand)) and cand not in tried:
                            candidates.append(cand)

                    for cand in candidates:
                        try:
                            tried.add(cand)
                            headers = self.api.headers if hasattr(self, 'api') else None
                            try:
                                setattr(card, '_expected_image_url', cand)
                            except Exception:
                                pass
                            thread = ImageLoaderThread(cand, card, headers=headers)
                            thread.image_loaded.connect(self.set_card_image)
                            thread.start()
                            self.image_loader_threads.append(thread)
                            return
                        except Exception:
                            continue

                    return

                card.set_image_from_bytes(b)
                return

            if isinstance(card, ModelCard):
                card.set_image(data_bytes)
        except Exception:
            pass
