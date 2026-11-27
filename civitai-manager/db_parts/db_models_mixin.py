import json
from .db_normalization import upsert_model, upsert_version


class DatabaseModelsMixin:
    def store_model(self, model_data, auto_commit=True):
        """Store model metadata in the database"""
        try:
            with self._lock:
                cursor = self.conn.cursor()
                if not upsert_model(cursor, model_data):
                    if auto_commit:
                        self.conn.rollback()
                    return False
                if auto_commit:
                    self.conn.commit()
                return True
        except Exception as e:
            if auto_commit:
                self.conn.rollback()
            print(f"Error storing model: {e}")
            return False

    def store_version(self, version_data, auto_commit=True):
        """Store version metadata in the database"""
        try:
            with self._lock:
                cursor = self.conn.cursor()
                if not upsert_version(cursor, version_data):
                    if auto_commit:
                        self.conn.rollback()
                    return False
                if auto_commit:
                    self.conn.commit()
                return True
        except Exception as e:
            if auto_commit:
                self.conn.rollback()
            print(f"Error storing version: {e}")
            return False

    def store_image(self, model_id, version_id, url, local_path, position=0, nsfw=False, width=None, height=None, is_gif=False, auto_commit=True):
        """Store image metadata in the database"""
        try:
            with self._lock:
                cursor = self.conn.cursor()
                if not version_id:
                    cursor.execute(
                        "INSERT INTO legacy_model_images (model_id, url, local_path, position, is_gif, width, height, nsfw_level) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (model_id, url, local_path, position, int(is_gif), width, height, int(nsfw)),
                    )
                else:
                    cursor.execute(
                        "INSERT INTO images (version_id, url, local_path, position, is_gif, width, height, nsfw_level) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (version_id, url, local_path, position, int(is_gif), width, height, int(nsfw)),
                    )

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
                cur.execute('''SELECT version_id, name, base_model, published_at, updated_at, raw_json FROM versions WHERE model_id=? ORDER BY published_at DESC, name ASC''', (model_id,))
                rows = cur.fetchall()
                for (vid, name, base_model, pub, upd, meta_json) in rows:
                    cur.execute('SELECT word FROM version_trained_words WHERE version_id=? ORDER BY position', (vid,))
                    trained_words = [row[0] for row in cur.fetchall()]
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
