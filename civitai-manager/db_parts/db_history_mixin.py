import json
import sqlite3


class DatabaseHistoryMixin:
    def get_download_history(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT 
                model_id, model_name, model_type, version, version_id, main_tag,
                download_date, original_file_name, file_path, file_size, status, file_sha256, restored
            FROM downloads
            ORDER BY download_date DESC
            ''')

            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []

    def import_history(self, history):
        try:
            cursor = self.conn.cursor()
            for item in history:
                try:
                    model_id = item.get('model_id')
                    model_meta = item.get('model_metadata') or item.get('model_meta')
                    if model_id and model_meta:
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
                            model_meta.get('name'),
                            model_meta.get('type'),
                            model_meta.get('baseModel') or model_meta.get('base_model'),
                            (model_meta.get('creator') or {}).get('username') if isinstance(model_meta.get('creator'), dict) else str(model_meta.get('creator') or ''),
                            model_meta.get('url') or f"https://civitai.com/models/{model_id}",
                            model_meta.get('description'),
                            json.dumps(model_meta.get('tags') or []),
                            model_meta.get('publishedAt') or model_meta.get('createdAt') or model_meta.get('published_at'),
                            model_meta.get('updatedAt') or model_meta.get('updated_at'),
                            json.dumps(model_meta)
                        ))
                except Exception:
                    pass
                try:
                    version_id = item.get('version_id')
                    version_meta = item.get('version_metadata') or item.get('version_meta')
                    if version_id and version_meta:
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
                            item.get('model_id'),
                            version_meta.get('name'),
                            version_meta.get('baseModel') or version_meta.get('base_model'),
                            version_meta.get('publishedAt') or version_meta.get('createdAt') or version_meta.get('published_at'),
                            version_meta.get('updatedAt') or version_meta.get('updated_at'),
                            json.dumps(version_meta.get('trainedWords') or []),
                            json.dumps(version_meta)
                        ))
                except Exception:
                    pass
                try:
                    mid = item.get('model_id')
                    if mid and not (item.get('model_metadata') or item.get('model_meta')):
                        cursor.execute('SELECT 1 FROM models WHERE model_id=? LIMIT 1', (mid,))
                        if cursor.fetchone() is None:
                            cursor.execute('''INSERT INTO models (model_id, name, type, base_model, creator, url, description, tags, published_at, updated_at, metadata)
                                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                                mid,
                                item.get('model_name'),
                                item.get('model_type'),
                                item.get('base_model'),
                                '',
                                item.get('url') or (f"https://civitai.com/models/{mid}" if mid else None),
                                None,
                                json.dumps(item.get('tags') or []),
                                item.get('published_at'),
                                item.get('updated_at'),
                                json.dumps({})
                            ))
                except Exception:
                    pass
                try:
                    vid = item.get('version_id')
                    if vid and not (item.get('version_metadata') or item.get('version_meta')):
                        cursor.execute('SELECT 1 FROM versions WHERE version_id=? LIMIT 1', (vid,))
                        if cursor.fetchone() is None:
                            cursor.execute('''INSERT INTO versions (version_id, model_id, name, base_model, published_at, updated_at, trained_words, metadata)
                                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (
                                vid,
                                item.get('model_id'),
                                item.get('version'),
                                item.get('base_model'),
                                item.get('version_published_at'),
                                item.get('version_updated_at'),
                                json.dumps(item.get('trained_words') or []),
                                json.dumps({})
                            ))
                except Exception:
                    pass
                try:
                    imgs = item.get('images') or []
                    if imgs and item.get('model_id'):
                        for lp in imgs:
                            try:
                                cursor.execute('''INSERT INTO images (model_id, version_id, url, local_path, position, is_gif) VALUES (?, ?, ?, ?, ?, ?)''', (
                                    item.get('model_id'),
                                    item.get('version_id'),
                                    None,
                                    lp,
                                    0,
                                    1 if str(lp).lower().endswith('.gif') else 0
                                ))
                            except Exception:
                                continue
                except Exception:
                    pass
                try:
                    incoming_status = item.get('status', 'Completed')
                    if not item.get('file_path') and incoming_status == 'Completed':
                        incoming_status = 'Imported'
                    incoming_sha = item.get('file_sha256') or None
                    cursor.execute('''SELECT id, status, file_sha256 FROM downloads WHERE model_id=? AND version_id=? ORDER BY download_date DESC LIMIT 1''', (
                        item.get('model_id'), item.get('version_id')))
                    existing = cursor.fetchone()
                    if existing:
                        ex_id, ex_status, ex_sha = existing
                        if (incoming_sha and incoming_sha == ex_sha) or (not incoming_sha and not ex_sha):
                            if ex_status in ('Imported','Missing') and incoming_status == 'Completed' and item.get('file_path'):
                                cursor.execute('UPDATE downloads SET status=?, file_path=?, file_size=?, file_sha256=?, restored=? WHERE id=?', (
                                    'Completed', item.get('file_path'), item.get('file_size'), incoming_sha, item.get('restored',0), ex_id))
                            continue
                        if ex_status == 'Completed' and incoming_status in ('Imported','Missing'):
                            continue
                    cursor.execute('''
                        INSERT INTO downloads (
                            model_id, model_name, model_type, version, version_id, main_tag,
                            download_date, original_file_name, file_path, file_size, status, file_sha256, restored
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        item.get('model_id'),
                        item.get('model_name'),
                        item.get('model_type'),
                        item.get('version'),
                        item.get('version_id'),
                        item.get('main_tag'),
                        item.get('download_date'),
                        item.get('original_file_name'),
                        item.get('file_path'),
                        item.get('file_size'),
                        incoming_status,
                        item.get('file_sha256'),
                        item.get('restored', 0)
                    ))
                except Exception:
                    pass
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def clear_history(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM downloads')
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def get_full_download_export(self):
        """Return enriched list of downloads with model/version metadata and local images.
        This enables reconstruction of downloaded explorer cards and details panel offline."""
        results = []
        try:
            with self._lock:
                cur = self.conn.cursor()
                cur.execute('''
                SELECT d.id, d.model_id, d.model_name, d.model_type, d.version, d.version_id, d.main_tag,
                       d.download_date, d.original_file_name, d.file_path, d.file_size, d.status, d.file_sha256, d.restored,
                       m.metadata AS model_metadata, v.metadata AS version_metadata
                FROM downloads d
                LEFT JOIN models m ON m.model_id = d.model_id
                LEFT JOIN versions v ON v.version_id = d.version_id
                ORDER BY d.download_date DESC
                ''')
                rows = cur.fetchall()
                for r in rows:
                    (row_id, model_id, model_name, model_type, version_name, version_id, main_tag,
                     download_date, original_file_name, file_path, file_size, status, file_sha256, restored,
                     model_meta_json, version_meta_json) = r
                    try:
                        model_meta = json.loads(model_meta_json) if model_meta_json else {}
                    except Exception:
                        model_meta = {}
                    try:
                        version_meta = json.loads(version_meta_json) if version_meta_json else {}
                    except Exception:
                        version_meta = {}
                    cur2 = self.conn.cursor()
                    cur2.execute('SELECT local_path FROM images WHERE model_id = ? AND local_path IS NOT NULL ORDER BY position ASC LIMIT 10', (model_id,))
                    imgs = [rr[0] for rr in cur2.fetchall() if rr and rr[0]]
                    results.append({
                        'id': row_id,
                        'model_id': model_id,
                        'model_name': model_name,
                        'model_type': model_type,
                        'version': version_name,
                        'version_id': version_id,
                        'main_tag': main_tag,
                        'download_date': download_date,
                        'original_file_name': original_file_name,
                        'file_path': file_path,
                        'file_size': file_size,
                        'status': status,
                        'file_sha256': file_sha256,
                        'restored': restored,
                        'model_metadata': model_meta,
                        'version_metadata': version_meta,
                        'images': imgs,
                    })
        except Exception as e:
            print('Error building full export:', e)
        return results

    def get_minimal_download_export(self):
        """Return minimal list with only fields needed to reconstruct basic cards/history.
        Excludes local file paths and image paths to keep it portable and privacy-safe."""
        minimal = []
        try:
            with self._lock:
                cur = self.conn.cursor()
                cur.execute('''
                SELECT d.model_id, d.model_name, d.model_type, d.version, d.version_id, d.main_tag,
                       d.download_date, d.original_file_name, d.file_size, d.status, d.file_sha256, d.restored,
                       m.base_model, m.url, m.tags, m.published_at, m.updated_at,
                       v.published_at AS version_published_at, v.updated_at AS version_updated_at, v.trained_words
                FROM downloads d
                LEFT JOIN models m ON m.model_id = d.model_id
                LEFT JOIN versions v ON v.version_id = d.version_id
                ORDER BY d.download_date DESC
                ''')
                rows = cur.fetchall()
                for (model_id, model_name, model_type, version_name, version_id, main_tag,
                     download_date, original_file_name, file_size, status, file_sha256, restored,
                     base_model, url, tags_json, published_at, updated_at, version_published_at, version_updated_at, trained_words_json) in rows:
                    try:
                        tags = json.loads(tags_json) if tags_json else []
                    except Exception:
                        tags = []
                    try:
                        trained_words = json.loads(trained_words_json) if trained_words_json else []
                    except Exception:
                        trained_words = []
                    minimal.append({
                        'model_id': model_id,
                        'model_name': model_name,
                        'model_type': model_type,
                        'version': version_name,
                        'version_id': version_id,
                        'main_tag': main_tag,
                        'download_date': download_date,
                        'original_file_name': original_file_name,
                        'file_size': file_size,
                        'status': status,
                        'file_sha256': file_sha256,
                        'restored': restored,
                        'base_model': base_model,
                        'url': url or (f"https://civitai.com/models/{model_id}" if model_id else None),
                        'tags': tags[:25],
                        'published_at': published_at,
                        'updated_at': updated_at,
                        'version_published_at': version_published_at,
                        'version_updated_at': version_updated_at,
                        'trained_words': trained_words,
                    })
        except Exception as e:
            print('Error building minimal export:', e)
        return minimal
