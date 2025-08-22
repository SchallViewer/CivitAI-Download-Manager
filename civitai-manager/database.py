import sqlite3
import os
import json
from datetime import datetime
from constants import ModelType, MainTag
import hashlib
import threading

class DatabaseManager:
    def __init__(self, db_path="civitai_manager.db"):
        # Set check_same_thread False so we can guard access with our own lock
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        try:
            # Improve concurrency & reduce locking issues
            self.conn.execute('PRAGMA journal_mode=WAL;')
            self.conn.execute('PRAGMA synchronous=NORMAL;')
            self.conn.execute('PRAGMA temp_store=MEMORY;')
            self.conn.execute('PRAGMA busy_timeout=5000;')  # 5s wait if locked
        except Exception:
            pass
        self._lock = threading.Lock()
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        # Schema versioning (simple meta table)
        cursor.execute('''CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT)''')
        cursor.execute('SELECT value FROM schema_meta WHERE key = "schema_version"')
        row = cursor.fetchone()
        current_version = int(row[0]) if row and row[0] and row[0].isdigit() else 0

        target_version = 4
        if current_version < target_version:
            # If version is 0 -> fresh create all tables (destructive path already expected earlier)
            if current_version == 0:
                for tbl in ("downloads", "downloaded_models", "models", "versions", "files", "images"):
                    try:
                        cursor.execute(f"DROP TABLE IF EXISTS {tbl}")
                    except sqlite3.Error:
                        pass
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS models (
                    model_id INTEGER PRIMARY KEY,
                    name TEXT,
                    type TEXT,
                    base_model TEXT,
                    creator TEXT,
                    url TEXT,
                    description TEXT,
                    tags TEXT,
                    published_at TEXT,
                    updated_at TEXT,
                    metadata TEXT
                )''')
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS versions (
                    version_id INTEGER PRIMARY KEY,
                    model_id INTEGER,
                    name TEXT,
                    base_model TEXT,
                    published_at TEXT,
                    updated_at TEXT,
                    trained_words TEXT,
                    metadata TEXT,
                    FOREIGN KEY(model_id) REFERENCES models(model_id)
                )''')
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version_id INTEGER,
                    name TEXT,
                    type TEXT,
                    size REAL,
                    download_url TEXT,
                    format TEXT,
                    sha256 TEXT,
                    path TEXT,
                    FOREIGN KEY(version_id) REFERENCES versions(version_id)
                )''')
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_id INTEGER,
                    version_id INTEGER,
                    url TEXT,
                    local_path TEXT,
                    position INTEGER,
                    is_gif INTEGER,
                    FOREIGN KEY(model_id) REFERENCES models(model_id),
                    FOREIGN KEY(version_id) REFERENCES versions(version_id)
                )''')
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_id INTEGER,
                    model_name TEXT,
                    model_type TEXT,
                    version TEXT,
                    version_id INTEGER,
                    main_tag TEXT,
                    download_date TEXT,
                    original_file_name TEXT,
                    file_path TEXT,
                    file_size REAL,
                    status TEXT,
                    file_sha256 TEXT,
                    restored INTEGER DEFAULT 0
                )''')
            else:
                # incremental migrations
                if current_version < 3:
                    # prior destructive path would have handled earlier; skip
                    pass
                if current_version < 4:
                    # add restored column if missing
                    try:
                        cursor.execute('ALTER TABLE downloads ADD COLUMN restored INTEGER DEFAULT 0')
                    except sqlite3.Error:
                        pass
            cursor.execute('INSERT OR REPLACE INTO schema_meta (key, value) VALUES ("schema_version", ?)', (str(target_version),))
            self.conn.commit()

    def save_downloaded_model(self, model_data, version, image_paths=None):
        """Upsert model/version, store cached local images. image_paths: list of local image file paths."""
        try:
            cursor = self.conn.cursor()
            model_id = model_data.get('id')
            if not model_id:
                return False

            # Upsert model
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

            # Upsert version
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

            # Save local images (per-version). Keep other versions' images intact.
            if image_paths:
                # Remove only existing entries for this specific version_id (not other versions)
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
                SELECT d.download_date,
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
            (download_date, mid, model_name, model_type, model_url, model_meta, vid, version_name, version_meta) = row
            try:
                mmeta = json.loads(model_meta or '{}')
            except Exception:
                mmeta = {}
            try:
                vmeta = json.loads(version_meta or '{}')
            except Exception:
                vmeta = {}
            # collect local images
            cursor.execute('''SELECT local_path FROM images WHERE model_id = ? AND (version_id = ? OR ? IS NULL) AND local_path IS NOT NULL ORDER BY position ASC''', (model_id, version_id, version_id))
            imgs = [r[0] for r in cursor.fetchall() if r and r[0]]
            return {
                'download_date': download_date,
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
        # lightweight debug logging to help trace lifecycle issues
        try:
            _log_path = os.path.join(os.path.expanduser('~'), 'civitai_manager_debug.log')
            with open(_log_path, 'a', encoding='utf-8') as _lf:
                _lf.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - is_model_downloaded check for {model_id}/{version_id} file_path={file_path}\n")
        except Exception:
            pass
        try:
            # consider it downloaded if a Completed download exists
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
            # check downloads table for a file_path entry for same model/version
            if r and r[0]:
                exists = os.path.exists(r[0])
                try:
                    with open(_log_path, 'a', encoding='utf-8') as _lf:
                        _lf.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - is_model_downloaded: downloads table file_path exists={exists} -> {r[0]}\n")
                except Exception:
                    pass
                return exists
            # fallback: consider it downloaded if downloaded_models row exists
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

    def get_downloaded_models(self):
        """Return a list of downloaded entries (one per model-version) with metadata and local images.
        Shape compatible with previous callers: each dict has keys
          id (row id surrogate), model_id, model_name, version, version_id, metadata, images, download_date
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT d.id, d.download_date,
                       m.model_id, m.name AS model_name, m.metadata AS model_metadata,
                       v.version_id, v.name AS version
                FROM downloads d
                JOIN models m ON m.model_id = d.model_id
                JOIN versions v ON v.version_id = d.version_id
                WHERE d.status = 'Completed'
                ORDER BY d.download_date DESC
            ''')
            rows = cursor.fetchall()
            results = []
            for (row_id, download_date, model_id, model_name, model_meta, version_id, version_name) in rows:
                try:
                    mmeta = json.loads(model_meta or '{}')
                except Exception:
                    mmeta = {}
                # collect local images for model (prefer) or for version
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
                })
            return results
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []
    
    def record_download(self, model_data, version, file_path, file_size, status="Completed", original_file_name=None, file_sha256=None, primary_tag=None):
        if not model_data or not version:
            return False
        # Normalize status to a known set to avoid CHECK constraint failures on older DBs
        allowed = ("Queued", "Downloading", "Completed", "Failed")
        if status not in allowed:
            # map common error-style statuses to Failed
            status = "Failed"
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            INSERT INTO downloads (
                model_id, model_name, model_type, version, version_id, main_tag,
                download_date, original_file_name, file_path, file_size, status, file_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
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
                    item.get('status', 'Completed'),
                    item.get('file_sha256'),
                    item.get('restored', 0)
                ))
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

    def update_file_statuses(self, download_dir: str):
        """Update download entries:
         - If file missing -> status 'Missing', restored=0
         - If status Missing and file present at recorded path -> status 'Completed', restored=1
         - If status Missing, file renamed/moved within download_dir but same SHA-256 found -> update file_path, status 'Completed', restored=1
        Returns dict counts including scanned files.
        """
        counts = {"missing":0, "restored":0, "renamed_restored":0, "scanned_files":0, "hashed_files":0}
        print("[refresh] ==== BEGIN update_file_statuses ====")
        print(f"[refresh] download_dir='{download_dir}'")
        with self._lock:
            try:
                cursor = self.conn.cursor()
                print("[refresh] Querying downloads table...")
                cursor.execute('SELECT id, file_path, status, file_sha256 FROM downloads')
                rows = cursor.fetchall()
                print(f"[refresh] Retrieved {len(rows)} download rows")
                # First pass: direct path existence checks
                missing_sha_targets = {}
                for idx, (did, fpath, status, sha) in enumerate(rows):
                    print(f"[refresh] Row {idx+1}/{len(rows)} id={did} status={status} path={fpath} sha={(sha or '')[:12]}")
                    exists = bool(fpath and os.path.exists(fpath))
                    if not exists and status not in ('Queued','Downloading','Failed','Missing'):
                        print(f"[refresh] -> Mark Missing (not found)")
                        cursor.execute('UPDATE downloads SET status = ?, restored = 0 WHERE id = ?', ('Missing', did))
                        counts['missing'] += 1
                        if sha:
                            missing_sha_targets[sha.lower()] = did
                    elif status == 'Missing' and exists:
                        print(f"[refresh] -> Mark Restored (path exists again)")
                        cursor.execute('UPDATE downloads SET status = ?, restored = 1 WHERE id = ?', ('Completed', did))
                        counts['restored'] += 1
                    elif status == 'Missing' and not exists and sha:
                        print(f"[refresh] -> Candidate for renamed search (has SHA-256)")
                        missing_sha_targets[sha.lower()] = did
                print(f"[refresh] First pass complete. missing_sha_targets={len(missing_sha_targets)}")

                # Second pass: locate renamed/moved files by SHA-256 if needed
                if missing_sha_targets and download_dir and os.path.isdir(download_dir):
                    wanted = set(missing_sha_targets.keys())
                    print(f"[refresh] Starting SHA-256 scan for {len(wanted)} hashes under {download_dir}")
                    for root, dirs, files in os.walk(download_dir):
                        for name in files:
                            counts['scanned_files'] += 1
                            low = name.lower()
                            if not (low.endswith('.safetensors') or low.endswith('.pt') or low.endswith('.pth')):
                                continue
                            path = os.path.join(root, name)
                            try:
                                print(f"[refresh] Hashing candidate: {path}")
                                h = hashlib.sha256()
                                with open(path, 'rb') as f:
                                    while True:
                                        chunk = f.read(1024*512)
                                        if not chunk:
                                            break
                                        h.update(chunk)
                                file_hash = h.hexdigest().lower()
                                counts['hashed_files'] += 1
                                if file_hash in wanted:
                                    did = missing_sha_targets[file_hash]
                                    print(f"[refresh] -> MATCH hash for id={did}. Updating path to {path}")
                                    cursor.execute('UPDATE downloads SET status = ?, restored = 1, file_path = ? WHERE id = ?', ('Completed', path, did))
                                    counts['renamed_restored'] += 1
                                    wanted.remove(file_hash)
                                    if not wanted:
                                        print("[refresh] All missing hashes resolved early; stopping scan")
                                        break
                            except Exception as e:
                                print(f"[refresh] Hash error for {path}: {e}")
                        if not wanted:
                            break
                else:
                    if not missing_sha_targets:
                        print("[refresh] No SHA targets to scan for renamed files")
                    else:
                        print("[refresh] Download directory invalid or not provided; skipping renamed scan")
                print(f"[refresh] Committing changes...")
                self.conn.commit()
            except sqlite3.Error as e:
                print(f"Database error updating file statuses: {e}")
            except Exception as e:
                print(f"[refresh] Unexpected error: {e}")
        print(f"[refresh] Summary: {counts}")
        print("[refresh] ==== END update_file_statuses ====")
        return counts

    def get_missing_status_map(self):
        """Return dict mapping model_id -> True if any download row is Missing for that model."""
        out = {}
        try:
            with self._lock:
                cur = self.conn.cursor()
                cur.execute('SELECT model_id, status FROM downloads')
                for mid, status in cur.fetchall():
                    if status == 'Missing':
                        out[mid] = True
        except Exception:
            pass
        return out