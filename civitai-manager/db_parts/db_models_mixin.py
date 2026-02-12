import json


class DatabaseModelsMixin:
    def store_model(self, model_data, auto_commit=True):
        """Store model metadata in the database"""
        try:
            with self._lock:
                cursor = self.conn.cursor()
                model_id = model_data.get('id')
                if not model_id:
                    return False

                model_url = f"https://civitai.com/models/{model_id}"

                cursor.execute('''
                    INSERT INTO models (model_id, name, type, base_model, creator, url, description, tags, published_at, updated_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(model_id) DO UPDATE SET
                        name=excluded.name,
                        type=excluded.type,
                        base_model=excluded.base_model,
                        creator=excluded.creator,
                        url=excluded.url,
                        description=excluded.description,
                        tags=excluded.tags,
                        published_at=excluded.published_at,
                        updated_at=excluded.updated_at,
                        metadata=excluded.metadata
                ''', (
                    model_id,
                    model_data.get('name', 'Unknown'),
                    model_data.get('type'),
                    model_data.get('baseModel') or model_data.get('base_model'),
                    (model_data.get('creator') or {}).get('username') if isinstance(model_data.get('creator'), dict) else str(model_data.get('creator') or ''),
                    model_url,
                    model_data.get('description'),
                    json.dumps(model_data.get('tags', [])),
                    model_data.get('publishedAt') or model_data.get('createdAt') or model_data.get('created_at') or model_data.get('published_at'),
                    model_data.get('updatedAt') or model_data.get('updated_at'),
                    json.dumps(model_data)
                ))
                if auto_commit:
                    self.conn.commit()
                return True
        except Exception as e:
            print(f"Error storing model: {e}")
            return False

    def store_version(self, version_data, auto_commit=True):
        """Store version metadata in the database"""
        try:
            with self._lock:
                cursor = self.conn.cursor()
                version_id = version_data.get('id')
                model_id = version_data.get('modelId') or (version_data.get('model') or {}).get('id')

                if not version_id or not model_id:
                    return False

                cursor.execute('''
                    INSERT INTO versions (version_id, model_id, name, base_model, published_at, updated_at, trained_words, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(version_id) DO UPDATE SET
                        model_id=excluded.model_id,
                        name=excluded.name,
                        base_model=excluded.base_model,
                        published_at=excluded.published_at,
                        updated_at=excluded.updated_at,
                        trained_words=excluded.trained_words,
                        metadata=excluded.metadata
                ''', (
                    version_id,
                    model_id,
                    version_data.get('name', 'Unknown'),
                    version_data.get('baseModel') or version_data.get('base_model'),
                    version_data.get('publishedAt') or version_data.get('createdAt') or version_data.get('created_at') or version_data.get('published_at'),
                    version_data.get('updatedAt') or version_data.get('updated_at'),
                    json.dumps(version_data.get('trainedWords') or []),
                    json.dumps(version_data)
                ))
                if auto_commit:
                    self.conn.commit()
                return True
        except Exception as e:
            print(f"Error storing version: {e}")
            return False

    def store_image(self, model_id, version_id, url, local_path, position=0, nsfw=False, width=None, height=None, is_gif=False, auto_commit=True):
        """Store image metadata in the database"""
        try:
            with self._lock:
                cursor = self.conn.cursor()

                cursor.execute("PRAGMA table_info(images)")
                columns_info = cursor.fetchall()
                available_columns = [col[1] for col in columns_info]

                base_columns = ['model_id', 'version_id', 'url', 'local_path', 'position', 'is_gif']
                values = [model_id, version_id, url, local_path, position, int(is_gif)]

                if 'nsfw' in available_columns:
                    base_columns.append('nsfw')
                    values.append(int(nsfw))
                if 'width' in available_columns and width is not None:
                    base_columns.append('width')
                    values.append(width)
                if 'height' in available_columns and height is not None:
                    base_columns.append('height')
                    values.append(height)

                placeholders = ', '.join(['?'] * len(values))
                columns_str = ', '.join(base_columns)

                cursor.execute(f'''
                    INSERT OR REPLACE INTO images ({columns_str})
                    VALUES ({placeholders})
                ''', values)

                if auto_commit:
                    self.conn.commit()
                return True
        except Exception as e:
            print(f"Error storing image: {e}")
            return False

    def get_model_versions(self, model_id):
        """Return list of versions for a given model with essential metadata (offline reconstruction)."""
        out = []
        try:
            with self._lock:
                cur = self.conn.cursor()
                cur.execute('''SELECT version_id, name, base_model, published_at, updated_at, trained_words, metadata FROM versions WHERE model_id=? ORDER BY published_at DESC, name ASC''', (model_id,))
                rows = cur.fetchall()
                for (vid, name, base_model, pub, upd, trained_words_json, meta_json) in rows:
                    try:
                        trained_words = json.loads(trained_words_json) if trained_words_json else []
                    except Exception:
                        trained_words = []
                    try:
                        meta = json.loads(meta_json) if meta_json else {}
                    except Exception:
                        meta = {}
                    v = {
                        'id': vid,
                        'name': name,
                        'baseModel': base_model,
                        'publishedAt': pub,
                        'updatedAt': upd,
                        'trainedWords': trained_words,
                    }
                    for k, val in meta.items():
                        if k not in v:
                            v[k] = val
                    out.append(v)
        except Exception:
            pass
        return out
