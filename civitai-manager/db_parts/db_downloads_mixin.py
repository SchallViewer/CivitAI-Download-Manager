import os
import json
import sqlite3
from datetime import datetime


class DatabaseDownloadsMixin:
    def save_downloaded_model(self, model_data, version, image_paths=None):
        """Upsert model/version, store cached local images. image_paths: list of local image file paths."""
        try:
            cursor = self.conn.cursor()
            model_id = model_data.get('id')
            if not model_id:
                return False

            model_url = model_data.get('url') or f"https://civitai.com/models/{model_id}"
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

            version_id = version.get('id') if isinstance(version, dict) else None
            if version_id:
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
                    version.get('name', 'Unknown'),
                    version.get('baseModel') or version.get('base_model'),
                    version.get('publishedAt') or version.get('createdAt') or version.get('created_at') or version.get('published_at'),
                    version.get('updatedAt') or version.get('updated_at'),
                    json.dumps(version.get('trainedWords') or []),
                    json.dumps(version)
                ))

            if image_paths:
                try:
                    if version_id:
                        cursor.execute('DELETE FROM images WHERE model_id = ? AND version_id = ? AND local_path IS NOT NULL', (model_id, version_id))
                    else:
                        cursor.execute('DELETE FROM images WHERE model_id = ? AND version_id IS NULL AND local_path IS NOT NULL', (model_id,))
                except sqlite3.Error:
                    pass
                for idx, p in enumerate(image_paths):
                    cursor.execute('''
                        INSERT INTO images (model_id, version_id, url, local_path, position, is_gif)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (model_id, version_id, None, p, idx, 1 if str(p).lower().endswith('.gif') else 0))

            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error saving downloaded model: {e}")
            return False

    def find_downloaded_model(self, model_id, version_id):
        """Return a dict with model/version metadata and local images if this version was downloaded."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT d.download_date, d.file_path,
                       m.model_id, m.name AS model_name, m.type AS model_type, m.url AS model_url, m.metadata AS model_metadata,
                       v.version_id, v.name AS version, v.metadata AS version_metadata
                FROM downloads d
                JOIN models m ON m.model_id = d.model_id
                JOIN versions v ON v.version_id = d.version_id
                WHERE d.model_id = ? AND d.version_id = ? AND d.status = 'Completed'
                ORDER BY d.download_date DESC LIMIT 1
            ''', (model_id, version_id))
            row = cursor.fetchone()
            if not row:
                return None
            (download_date, file_path, mid, model_name, model_type, model_url, model_meta, vid, version_name, version_meta) = row
            try:
                mmeta = json.loads(model_meta or '{}')
            except Exception:
                mmeta = {}
            try:
                vmeta = json.loads(version_meta or '{}')
            except Exception:
                vmeta = {}
            cursor.execute('''SELECT local_path FROM images WHERE model_id = ? AND (version_id = ? OR ? IS NULL) AND local_path IS NOT NULL ORDER BY position ASC''', (model_id, version_id, version_id))
            imgs = [r[0] for r in cursor.fetchall() if r and r[0]]
            return {
                'download_date': download_date,
                'file_path': file_path,
                'model_id': mid,
                'model_name': model_name,
                'model_type': model_type,
                'model_url': model_url,
                'version': version_name,
                'version_id': vid,
                'metadata': mmeta,
                'version_metadata': vmeta,
                'images': imgs,
            }
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None

    def is_model_downloaded(self, model_id, version_id, file_path=None):
        """Return True if DB shows the model+version downloaded and (if file_path provided) file exists.
        If file_path omitted, will check for registered file paths in downloads table.
        """
        try:
            _log_path = os.path.join(os.path.expanduser('~'), 'civitai_manager_debug.log')
            with open(_log_path, 'a', encoding='utf-8') as _lf:
                _lf.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - is_model_downloaded check for {model_id}/{version_id} file_path={file_path}\n")
        except Exception:
            pass
        try:
            cursor = self.conn.cursor()
            cursor.execute('''SELECT file_path FROM downloads WHERE model_id = ? AND version_id = ? AND status = 'Completed' ORDER BY download_date DESC LIMIT 1''', (model_id, version_id))
            r = cursor.fetchone()
            if not r:
                try:
                    with open(_log_path, 'a', encoding='utf-8') as _lf:
                        _lf.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - is_model_downloaded: no downloaded_models row for {model_id}/{version_id}\n")
                except Exception:
                    pass
                return False
            if file_path:
                exists = os.path.exists(file_path)
                try:
                    with open(_log_path, 'a', encoding='utf-8') as _lf:
                        _lf.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - is_model_downloaded: file_path exists={exists} for {file_path}\n")
                except Exception:
                    pass
                return exists
            if r and r[0]:
                exists = os.path.exists(r[0])
                try:
                    with open(_log_path, 'a', encoding='utf-8') as _lf:
                        _lf.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - is_model_downloaded: downloads table file_path exists={exists} -> {r[0]}\n")
                except Exception:
                    pass
                return exists
            try:
                with open(_log_path, 'a', encoding='utf-8') as _lf:
                    _lf.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - is_model_downloaded: fallback True for {model_id}/{version_id}\n")
            except Exception:
                pass
            return True
        except Exception as e:
            try:
                with open(_log_path, 'a', encoding='utf-8') as _lf:
                    _lf.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - is_model_downloaded error for {model_id}/{version_id}: {e}\n")
            except Exception:
                pass
            print(f"Database error checking downloaded: {e}")
            return False

    def get_downloaded_file_info(self, model_id, version_id):
        """Return latest file info for a downloaded model/version."""
        try:
            with self._lock:
                cur = self.conn.cursor()
                cur.execute(
                    '''
                    SELECT d.original_file_name, d.file_path
                    FROM downloads d
                    WHERE d.model_id = ? AND d.version_id = ?
                      AND d.status IN ('Completed','Imported','Missing')
                    ORDER BY d.download_date DESC LIMIT 1
                    ''',
                    (model_id, version_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                original_file_name, file_path = row
                return {
                    'original_file_name': original_file_name,
                    'file_path': file_path,
                }
        except Exception as e:
            print(f"Database error fetching file info: {e}")
            return None

    def get_downloaded_models(self):
        """Return a list of downloaded entries (one per model-version) with metadata and local images.
        Shape compatible with previous callers: each dict has keys
          id (row id surrogate), model_id, model_name, version, version_id, metadata, images, download_date
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT d.id, d.download_date, d.main_tag,
                       m.model_id, m.name AS model_name, m.metadata AS model_metadata, m.tags,
                       v.version_id, v.name AS version
                FROM downloads d
                JOIN models m ON m.model_id = d.model_id
                JOIN versions v ON v.version_id = d.version_id
                WHERE d.status IN ('Completed','Imported','Missing')
                ORDER BY d.download_date DESC
            ''')
            rows = cursor.fetchall()
            results = []
            for (row_id, download_date, main_tag, model_id, model_name, model_meta, tags_json, version_id, version_name) in rows:
                try:
                    mmeta = json.loads(model_meta or '{}')
                except Exception:
                    mmeta = {}

                try:
                    db_tags = json.loads(tags_json or '[]')
                    if db_tags and ('tags' not in mmeta or not mmeta['tags']):
                        mmeta['tags'] = db_tags
                except Exception:
                    pass
                cursor.execute('SELECT local_path FROM images WHERE model_id = ? AND local_path IS NOT NULL ORDER BY position ASC', (model_id,))
                img_rows = cursor.fetchall()
                images = [r[0] for r in img_rows if r and r[0]]
                results.append({
                    'id': row_id,
                    'model_id': model_id,
                    'model_name': model_name,
                    'version': version_name,
                    'version_id': version_id,
                    'metadata': mmeta,
                    'images': images,
                    'download_date': download_date,
                    'main_tag': main_tag,
                })
            return results
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []

    def record_download(self, model_data, version, file_path, file_size, status="Completed", original_file_name=None, file_sha256=None, primary_tag=None):
        if not model_data or not version:
            return False
        allowed = ("Queued", "Downloading", "Completed", "Failed", "Imported", "Missing")
        if status not in allowed:
            status = "Failed"
        try:
            cursor = self.conn.cursor()
            try:
                cursor.execute('''SELECT id, status, file_sha256, file_path FROM downloads WHERE model_id=? AND version_id=? ORDER BY download_date DESC LIMIT 1''', (
                    model_data.get('id'), version.get('id')))
                existing = cursor.fetchone()
            except sqlite3.Error:
                existing = None
            if existing:
                ex_id, ex_status, ex_sha, ex_path = existing
                if ex_status in ('Imported','Missing') and (not ex_path):
                    cursor.execute('''UPDATE downloads SET 
                        model_name=?, model_type=?, version=?, main_tag=?, original_file_name=?, file_path=?, file_size=?, status=?, file_sha256=?, restored=1
                        WHERE id=?''', (
                        model_data.get('name','Unknown'),
                        model_data.get('type','Unknown'),
                        version.get('name','Unknown'),
                        primary_tag or (model_data.get('tags', ['Other'])[0] if model_data.get('tags') else 'Other'),
                        original_file_name,
                        file_path,
                        file_size,
                        'Completed',
                        file_sha256,
                        ex_id
                    ))
                    self.conn.commit()
                    return True
            cursor.execute('''INSERT INTO downloads (
                model_id, model_name, model_type, version, version_id, main_tag,
                download_date, original_file_name, file_path, file_size, status, file_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                model_data.get('id'),
                model_data.get('name', 'Unknown'),
                model_data.get('type', 'Unknown'),
                version.get('name', 'Unknown'),
                version.get('id'),
                primary_tag or (model_data.get('tags', ['Other'])[0] if model_data.get('tags') else 'Other'),
                datetime.now().isoformat(),
                original_file_name,
                file_path,
                file_size,
                status,
                file_sha256
            ))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def get_downloaded_base_models(self):
        """Return sorted list of base_model values for downloaded versions."""
        try:
            with self._lock:
                cur = self.conn.cursor()
                cur.execute(
                    '''
                    SELECT DISTINCT v.base_model
                    FROM versions v
                    JOIN downloads d ON d.version_id = v.version_id
                    WHERE d.status IN ('Completed','Imported','Missing')
                      AND v.base_model IS NOT NULL
                      AND TRIM(v.base_model) <> ''
                    ORDER BY v.base_model ASC
                    '''
                )
                return [row[0] for row in cur.fetchall() if row and row[0]]
        except Exception as e:
            print(f"Database error fetching base models: {e}")
            return []

    def get_downloaded_model_types(self):
        """Return sorted list of model types present in downloaded models."""
        try:
            with self._lock:
                cur = self.conn.cursor()
                cur.execute(
                    '''
                    SELECT DISTINCT m.type
                    FROM models m
                    JOIN downloads d ON d.model_id = m.model_id
                    WHERE d.status IN ('Completed','Imported','Missing')
                      AND m.type IS NOT NULL
                      AND TRIM(m.type) <> ''
                    ORDER BY m.type ASC
                    '''
                )
                return [row[0] for row in cur.fetchall() if row and row[0]]
        except Exception as e:
            print(f"Database error fetching model types: {e}")
            return []

    def has_download_record(self, model_id: int, version_id: int) -> bool:
        """Return True if there is a downloads row indicating the version was downloaded/imported/missing."""
        try:
            with self._lock:
                cur = self.conn.cursor()
                cur.execute("SELECT 1 FROM downloads WHERE model_id=? AND version_id=? AND status IN ('Completed','Imported','Missing') LIMIT 1", (model_id, version_id))
                return cur.fetchone() is not None
        except Exception:
            return False
