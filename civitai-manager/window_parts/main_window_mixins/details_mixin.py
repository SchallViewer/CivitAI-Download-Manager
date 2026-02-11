# details_mixin.py
import os
from PyQt5.QtGui import QPixmap, QColor, QDesktopServices, QGuiApplication
from PyQt5.QtCore import Qt, QUrl, QPropertyAnimation, QSequentialAnimationGroup
from PyQt5.QtWidgets import QGraphicsColorizeEffect, QListWidgetItem
from ui_helpers import ImageLoaderThread


class DetailsMixin:
    def show_model_details(self, model_data):
        self.current_model = model_data
        try:
            self._last_details_model_data = model_data
            self._last_details_from_downloaded = bool(
                getattr(self, '_incoming_show_from_downloaded', False)
            )
        except Exception:
            pass
        self.right_panel.setCurrentIndex(0)
        try:
            self._showing_downloaded_details = False
        except Exception:
            pass

        if not getattr(self, '_suppress_details_initial_load', False):
            self.details_images_urls = self._collect_details_images(model_data, max_images=5)
            self.details_image_index = 0
            self._load_details_image_by_index(self.details_image_index)

        self.model_name.setText(model_data.get('name', 'Untitled Model'))
        creator = model_data.get('creator') or {}
        creator_name = (
            creator.get('username') if isinstance(creator, dict) else str(creator) if creator else 'Unknown'
        )
        self.model_creator.setText(f"by {creator_name}")

        try:
            raw_type = model_data.get('type') or model_data.get('modelType') or model_data.get('model_type') or ''
            type_map = {
                'LORA': 'LoRA',
                'Embeddings': 'Embedding',
                'TextualInversion': 'Textual Inversion',
                'Hypernetwork': 'Hypernetwork',
                'Checkpoint': 'Checkpoint',
                'Aesthetic': 'Aesthetic Gradient',
                'Textures': 'Textures',
            }
            type_label = type_map.get(raw_type, str(raw_type)) if raw_type else ''
            try:
                self.model_type_label.setText(type_label)
                self.model_type_label.setVisible(bool(type_label))
            except Exception:
                pass

            tags = model_data.get('tags') or []
            primary_tag = ''
            if tags:
                names = []
                for t in tags:
                    if isinstance(t, dict):
                        n = t.get('name') or ''
                    else:
                        n = str(t or '')
                    if n:
                        names.append(n)
                try:
                    if hasattr(self, 'settings_manager'):
                        pri_raw = self.settings_manager.get('priority_tags', '') or ''
                        priority = [p.strip().lower() for p in pri_raw.split(',') if p.strip()]
                        if not priority:
                            priority = ['meme', 'concept', 'character', 'style', 'clothing', 'pose']
                    else:
                        priority = ['meme', 'concept', 'character', 'style', 'clothing', 'pose']
                except Exception:
                    priority = ['meme', 'concept', 'character', 'style', 'clothing', 'pose']
                lower_map = {n.lower(): n for n in names}
                chosen = None
                for p in priority:
                    if p in lower_map:
                        chosen = lower_map[p]
                        break
                if not chosen and names:
                    chosen = names[0]
                primary_tag = chosen or ''
            self._current_primary_tag = primary_tag
            try:
                self.model_primary_tag_label.setText(primary_tag)
                self.model_primary_tag_label.setVisible(bool(primary_tag))
            except Exception:
                pass

            base_model_name = ''
            if isinstance(model_data.get('baseModel'), str):
                base_model_name = model_data.get('baseModel')
            else:
                versions = model_data.get('modelVersions') or model_data.get('versions') or []
                if versions and isinstance(versions[0], dict):
                    bm = versions[0].get('baseModel') or versions[0].get('base_model')
                    if isinstance(bm, str):
                        base_model_name = bm
            try:
                self.model_base_tag.setText(base_model_name)
                self.model_base_tag.setVisible(bool(base_model_name))
            except Exception:
                pass
        except Exception:
            pass

        try:
            model_id = str(model_data.get('id') or model_data.get('model_id') or '')
            if model_id:
                self.model_id_label.setText(f"ID: {model_id}")
                self.model_id_label.setVisible(True)

                def _on_id_click(event, mid=model_id):
                    try:
                        QGuiApplication.clipboard().setText(str(mid))
                    except Exception:
                        pass
                    try:
                        effect = QGraphicsColorizeEffect()
                        effect.setColor(QColor('#4caf50'))
                        effect.setStrength(0.0)
                        self.model_id_label.setGraphicsEffect(effect)
                        anim_in = QPropertyAnimation(effect, b"strength")
                        anim_in.setStartValue(0.0)
                        anim_in.setEndValue(1.0)
                        anim_in.setDuration(220)
                        anim_out = QPropertyAnimation(effect, b"strength")
                        anim_out.setStartValue(1.0)
                        anim_out.setEndValue(0.0)
                        anim_out.setDuration(700)
                        seq = QSequentialAnimationGroup(self)
                        seq.addAnimation(anim_in)
                        seq.addAnimation(anim_out)
                        seq.start()
                    except Exception:
                        pass

                try:
                    self.model_id_label.mousePressEvent = _on_id_click
                except Exception:
                    pass
            else:
                self.model_id_label.setVisible(False)
        except Exception:
            try:
                self.model_id_label.setVisible(False)
            except Exception:
                pass

        downloads = self._safe_get_number(
            model_data, ('downloadCount', 'downloads', 'download_count', 'downloadCount')
        )
        ratings = self._safe_get_number(
            model_data, ('ratingCount', 'rating_count', 'ratings', 'ratingsCount')
        )
        try:
            if (not downloads) or downloads == 0:
                stats = model_data.get('stats') or {}
                downloads = self._safe_get_number(stats, ('downloadCount', 'downloads')) or downloads
            if (not ratings) or ratings == 0:
                stats = model_data.get('stats') or {}
                ratings = self._safe_get_number(stats, ('ratingCount', 'ratings')) or ratings
        except Exception:
            pass
        try:
            if (not downloads) or downloads == 0:
                v_total = 0
                for v in model_data.get('modelVersions') or []:
                    sv = v.get('stats') or {}
                    v_total += self._safe_get_number(sv, ('downloadCount', 'downloads'))
                if v_total:
                    downloads = v_total
            if (not ratings) or ratings == 0:
                r_total = 0
                for v in model_data.get('modelVersions') or []:
                    sv = v.get('stats') or {}
                    r_total += self._safe_get_number(sv, ('ratingCount', 'ratings'))
                if r_total:
                    ratings = r_total
        except Exception:
            pass
        self.downloads_count.setText(str(downloads))
        self.ratings_count.setText(str(ratings))
        self.description.setHtml(model_data.get('description', 'No description available'))

        base_model_val = model_data.get('baseModel') or model_data.get('base_model') or ''
        self.model_base_model.setText(f"Base model: {base_model_val}" if base_model_val else "")
        pub = self._extract_date(model_data, ('publishedAt', 'createdAt', 'created_at', 'published_at'))
        upd = self._extract_date(model_data, ('updatedAt', 'updated_at'))
        self.model_published.setText(f"Published: {pub}" if pub else "")
        self.model_updated.setText(f"Updated: {upd}" if upd else "")

        self.version_list.clear()
        versions = model_data.get('modelVersions', [])
        model_id = model_data.get('id') if isinstance(model_data, dict) else None
        for version in versions:
            vname = version.get('name', 'Unknown')
            vb = version.get('baseModel') or version.get('base_model') or ''
            extra = f" — base: {vb}" if vb else ''
            downloaded_flag = False
            try:
                vid = version.get('id')
                if model_id and vid and hasattr(self, 'db_manager'):
                    downloaded_flag = self.db_manager.is_model_downloaded(model_id, vid)
            except Exception:
                downloaded_flag = False

            label = f"Version {vname}{extra}"
            if downloaded_flag:
                label = label + "  (Downloaded)"

            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, version)
            try:
                item.setData(Qt.UserRole + 1, bool(downloaded_flag))
            except Exception:
                pass
            self.version_list.addItem(item)

        self.trigger_words.clear()
        try:
            self.download_btn.setVisible(True)
        except Exception:
            pass
        self.download_btn.setEnabled(False)

    def _collect_details_images(self, model_data, max_images=5):
        urls = []
        seen = set()

        def add_url(u):
            if not u or not isinstance(u, str):
                return
            low = u.lower()
            for ext in ('.mp4', '.webm', '.mov', '.mkv', '.avi'):
                if low.endswith(ext) or ext in low:
                    return
            if u in seen:
                return
            seen.add(u)
            urls.append(u)

        for key in ('images', 'gallery', 'modelImages'):
            imgs = model_data.get(key) or []
            for img in imgs:
                if isinstance(img, dict):
                    add_url(img.get('url') or img.get('thumbnail'))
                else:
                    add_url(str(img))
                if len(urls) >= max_images:
                    return urls

        for version in model_data.get('modelVersions', []):
            for img in (version.get('images') or []):
                if isinstance(img, dict):
                    add_url(img.get('url') or img.get('thumbnail'))
                else:
                    add_url(str(img))
                if len(urls) >= max_images:
                    return urls

        showcase = self._extract_image_url(model_data)
        add_url(showcase)
        return urls

    def _load_details_image_by_index(self, index):
        try:
            if not self.details_images_urls:
                self.model_image.clear()
                self.details_index_label.setText("")
                self.prev_image_btn.setEnabled(False)
                self.next_image_btn.setEnabled(False)
                return

            index = max(0, min(index, len(self.details_images_urls) - 1))
            url = self.details_images_urls[index]
            self.details_index_label.setText(f"{index+1} / {len(self.details_images_urls)}")
            self.prev_image_btn.setEnabled(index > 0)
            self.next_image_btn.setEnabled(index < len(self.details_images_urls) - 1)

            self.details_image_attempts = set()
            headers = self.api.headers if hasattr(self, 'api') else None
            try:
                self._expected_details_image = url
            except Exception:
                self._expected_details_image = None
            thread = ImageLoaderThread(url, self.model_image, headers=headers)
            thread.image_loaded.connect(self.set_details_image)
            thread.start()
            self.image_loader_threads.append(thread)
        except Exception:
            pass

    def _change_details_image(self, delta):
        if not self.details_images_urls:
            return
        self.details_image_index = max(
            0, min(self.details_image_index + delta, len(self.details_images_urls) - 1)
        )
        self._load_details_image_by_index(self.details_image_index)

    def set_details_image(self, url, data_bytes, target):
        try:
            if target != self.model_image:
                return

            expected = getattr(self, '_expected_details_image', None)
            if expected and url != expected:
                return

            if isinstance(data_bytes, (bytes, bytearray)):
                b = bytes(data_bytes)
                if b[:6] in (b'GIF87a', b'GIF89a'):
                    tried = self.details_image_attempts

                    def _is_video(u):
                        if not u or not isinstance(u, str):
                            return False
                        low = u.lower()
                        for ext in ('.mp4', '.webm', '.mov', '.mkv', '.avi'):
                            if low.endswith(ext) or ext in low:
                                return True
                        return False

                    if self.current_version:
                        images = self.current_version.get('images') or []
                        for img in images:
                            if isinstance(img, dict):
                                candidate = img.get('url') or img.get('thumbnail')
                            else:
                                candidate = str(img)
                            if candidate and (not _is_video(candidate)) and candidate not in tried:
                                try:
                                    tried.add(candidate)
                                    headers = self.api.headers if hasattr(self, 'api') else None
                                    try:
                                        self._expected_details_image = candidate
                                    except Exception:
                                        self._expected_details_image = None
                                    thread = ImageLoaderThread(candidate, self.model_image, headers=headers)
                                    thread.image_loaded.connect(self.set_details_image)
                                    thread.start()
                                    self.image_loader_threads.append(thread)
                                    return
                                except Exception:
                                    continue
                    return

                pixmap = QPixmap()
                pixmap.loadFromData(b)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.model_image.setPixmap(scaled)
            else:
                scaled = data_bytes.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.model_image.setPixmap(scaled)
        except Exception:
            pass

    def version_selected(self):
        selected_items = self.version_list.selectedItems()
        if selected_items:
            version = selected_items[0].data(Qt.UserRole)
            self.current_version = version
            in_downloaded = getattr(self, 'current_left_view', 'search') == 'downloaded'
            try:
                if hasattr(self, 'custom_tags_input'):
                    if in_downloaded:
                        filename_text = "No file downloaded for this version"
                        try:
                            mid = (self.current_model or {}).get('id') or (self.current_model or {}).get('model_id')
                            vid = version.get('id') or version.get('version_id')
                            if mid and vid and hasattr(self, 'db_manager'):
                                info = self.db_manager.get_downloaded_file_info(mid, vid)
                                if info:
                                    if info.get('file_path'):
                                        filename_text = os.path.basename(info.get('file_path'))
                                    elif info.get('original_file_name'):
                                        filename_text = info.get('original_file_name')
                        except Exception:
                            pass
                        self.custom_tags_input.setReadOnly(True)
                        self.custom_tags_input.setPlaceholderText("Downloaded filename")
                        self.custom_tags_input.setText(filename_text)
                    else:
                        self.custom_tags_input.setReadOnly(False)
            except Exception:
                pass
            try:
                if getattr(self, 'delete_version_btn', None):
                    self.delete_version_btn.setVisible(in_downloaded)
                    if in_downloaded and self.current_model:
                        mid = self.current_model.get('id') or self.current_model.get('model_id')
                        vid = version.get('id') or version.get('version_id')
                        is_downloaded = False
                        try:
                            if mid and vid and hasattr(self, 'db_manager'):
                                is_downloaded = self.db_manager.has_download_record(mid, vid)
                        except Exception:
                            is_downloaded = False
                        self.delete_version_btn.setEnabled(is_downloaded)
                    else:
                        self.delete_version_btn.setEnabled(False)
            except Exception:
                pass

            trigger_words = version.get('trainedWords', [])
            if trigger_words:
                self.trigger_words.setText("\n".join(trigger_words))
            else:
                self.trigger_words.setText("No trigger words available")

            unsafe = False
            try:
                files = version.get('files') or []
                for f in files:
                    if not isinstance(f, dict):
                        continue
                    if f.get('type') == 'Model':
                        name = (f.get('name') or '').lower()
                        if name.endswith('.pt') or name.endswith('.pth'):
                            unsafe = True
                            break
            except Exception:
                unsafe = False

            if unsafe:
                self.security_warning_label.setText(
                    "Security warning: This version only provides PickleTensor files (.pt/.pth), "
                    "which can execute code when loaded and are not supported here. "
                    "Use 'Open on Civitai' to download at your own risk."
                )
                self.security_warning_label.setVisible(True)
                self.download_btn.setEnabled(False)
            else:
                self.security_warning_label.setVisible(False)
                self.download_btn.setEnabled(True)
            self.details_image_attempts = set()
            vb = version.get('baseModel') or version.get('base_model') or ''
            if vb:
                self.model_base_model.setText(f"Base model: {vb}")
            pubv = self._extract_date(version, ('publishedAt', 'createdAt', 'created_at', 'published_at'))
            updv = self._extract_date(version, ('updatedAt', 'updated_at'))
            self.model_published.setText(
                f"Published: {pubv}" if pubv else self.model_published.text()
            )
            self.model_updated.setText(f"Updated: {updv}" if updv else self.model_updated.text())

            def _is_video(u: str) -> bool:
                if not u or not isinstance(u, str):
                    return False
                low = u.lower()
                for ext in ('.mp4', '.webm', '.mov', '.mkv', '.avi'):
                    if low.endswith(ext) or ext in low:
                        return True
                return False

            urls = []
            seen = set()

            def _add(u: str):
                if not u or not isinstance(u, str):
                    return
                if _is_video(u):
                    return
                if u in seen:
                    return
                seen.add(u)
                urls.append(u)

            used_local = False
            try:
                if getattr(self, '_showing_downloaded_details', False) and hasattr(self, 'db_manager'):
                    mid = (self.current_model or {}).get('id') or (self.current_model or {}).get('model_id')
                    vid = version.get('id')
                    if mid and vid:
                        rec = self.db_manager.find_downloaded_model(mid, vid)
                        local_imgs = (rec.get('images') if rec else []) or []
                        for u in local_imgs:
                            _add(u)
                        used_local = len(urls) > 0
            except Exception:
                used_local = False

            if not used_local:
                for img in (version.get('images') or []):
                    if isinstance(img, dict):
                        _add(img.get('url') or img.get('thumbnail'))
                    else:
                        _add(str(img))

            if not urls:
                for key in ('images', 'gallery', 'modelImages'):
                    for img in (self.current_model or {}).get(key, []) or []:
                        if isinstance(img, dict):
                            _add(img.get('url') or img.get('thumbnail'))
                        else:
                            _add(str(img))
                        if len(urls) >= 5:
                            break
                    if len(urls) >= 5:
                        break

            self.details_images_urls = urls[:5]
            self.details_image_index = 0
            self._load_details_image_by_index(self.details_image_index)

    def open_model_in_browser(self):
        if self.current_model:
            model_id = self.current_model.get('id')
            if model_id:
                url = f"https://civitai.com/models/{model_id}"
                QDesktopServices.openUrl(QUrl(url))
