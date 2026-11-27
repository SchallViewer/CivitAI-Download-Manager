import os
import sqlite3
import threading


class DatabaseCoreMixin:
    def _init_db(self, db_path=None):
        if db_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(script_dir, "..", "civitai_manager.db")
            db_path = os.path.normpath(db_path)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        try:
            self.conn.execute('PRAGMA journal_mode=WAL;')
            self.conn.execute('PRAGMA synchronous=NORMAL;')
            self.conn.execute('PRAGMA temp_store=MEMORY;')
            self.conn.execute('PRAGMA busy_timeout=5000;')
        except Exception:
            pass
        self._lock = threading.Lock()
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        self.conn.execute('PRAGMA foreign_keys = ON')
        cursor.execute('''CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT)''')
        cursor.execute('SELECT value FROM schema_meta WHERE key = "schema_version"')
        row = cursor.fetchone()
        current_version = int(row[0]) if row and row[0] and row[0].isdigit() else 0

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {r[0] for r in cursor.fetchall()}
        legacy_tables = {"models", "versions", "files", "images", "downloads"}
        populated_legacy = bool(legacy_tables.intersection(existing_tables))
        target_version = 5
        if current_version < target_version:
            try:
                self.conn.execute('BEGIN IMMEDIATE')
                if populated_legacy:
                    self._migrate_legacy_schema(cursor)
                else:
                    self._create_normalized_schema(cursor)
                cursor.execute(
                    'INSERT OR REPLACE INTO schema_meta (key, value) VALUES ("schema_version", ?)',
                    (str(target_version),),
                )
                violations = cursor.execute('PRAGMA foreign_key_check').fetchall()
                if violations:
                    raise sqlite3.IntegrityError("Foreign key violations after normalization migration")
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise
        else:
            self._create_normalized_schema(cursor)
            self.conn.commit()

    def _create_normalized_schema(self, cursor):
        cursor.execute('''CREATE TABLE IF NOT EXISTS creators (
            creator_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            username_key TEXT NOT NULL UNIQUE,
            image_url TEXT
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS tags (
            tag_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            name_key TEXT NOT NULL UNIQUE
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS models (
            model_id INTEGER PRIMARY KEY,
            creator_id INTEGER REFERENCES creators(creator_id),
            name TEXT,
            type TEXT,
            base_model TEXT,
            url TEXT,
            description TEXT,
            published_at TEXT,
            updated_at TEXT,
            nsfw_level INTEGER,
            availability TEXT,
            allow_no_credit INTEGER,
            allow_derivatives INTEGER,
            allow_different_license INTEGER,
            download_count INTEGER,
            thumbs_up_count INTEGER,
            raw_json TEXT
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS model_tags (
            model_id INTEGER NOT NULL REFERENCES models(model_id) ON DELETE CASCADE,
            tag_id INTEGER NOT NULL REFERENCES tags(tag_id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            PRIMARY KEY (model_id, tag_id),
            UNIQUE (model_id, position)
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS model_commercial_uses (
            model_id INTEGER NOT NULL REFERENCES models(model_id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            use_name TEXT NOT NULL,
            PRIMARY KEY (model_id, position)
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS versions (
            version_id INTEGER PRIMARY KEY,
            model_id INTEGER NOT NULL REFERENCES models(model_id) ON DELETE CASCADE,
            name TEXT,
            base_model TEXT,
            base_model_type TEXT,
            status TEXT,
            availability TEXT,
            published_at TEXT,
            updated_at TEXT,
            nsfw_level INTEGER,
            description TEXT,
            download_count INTEGER,
            thumbs_up_count INTEGER,
            raw_json TEXT
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS version_trained_words (
            version_id INTEGER NOT NULL REFERENCES versions(version_id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            word TEXT NOT NULL,
            PRIMARY KEY (version_id, position)
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_file_id INTEGER UNIQUE,
            version_id INTEGER NOT NULL REFERENCES versions(version_id) ON DELETE CASCADE,
            name TEXT,
            type TEXT,
            size_kb REAL,
            format TEXT,
            download_url TEXT,
            is_primary INTEGER,
            sha256 TEXT,
            path TEXT,
            pickle_scan TEXT,
            virus_scan TEXT,
            scanned_at TEXT
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id INTEGER NOT NULL REFERENCES versions(version_id) ON DELETE CASCADE,
            url TEXT,
            local_path TEXT,
            position INTEGER,
            is_gif INTEGER,
            media_type TEXT,
            width INTEGER,
            height INTEGER,
            nsfw_level INTEGER,
            blurhash TEXT
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS legacy_model_images (
            id INTEGER PRIMARY KEY,
            model_id INTEGER,
            url TEXT,
            local_path TEXT,
            position INTEGER,
            is_gif INTEGER,
            media_type TEXT,
            width INTEGER,
            height INTEGER,
            nsfw_level INTEGER,
            blurhash TEXT
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS legacy_file_paths (
            old_file_id INTEGER PRIMARY KEY,
            version_id INTEGER,
            name TEXT,
            sha256 TEXT,
            path TEXT
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS downloads (
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
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_model_tags_tag ON model_tags(tag_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_versions_model ON versions(model_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_version ON files(version_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_images_version ON images(version_id)')

    def _migrate_legacy_schema(self, cursor):
        import json
        import unicodedata

        def key(value):
            if not isinstance(value, str):
                return None
            value = unicodedata.normalize("NFC", value.strip())
            return value.casefold() if value else None

        cursor.execute("PRAGMA table_info(models)")
        model_cols = {r[1] for r in cursor.fetchall()}
        if "models" in {r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            if "raw_json" not in model_cols:
                cursor.execute("ALTER TABLE models RENAME TO legacy_models")
        cursor.execute("PRAGMA table_info(versions)")
        version_cols = {r[1] for r in cursor.fetchall()}
        if "versions" in {r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            if "raw_json" not in version_cols:
                cursor.execute("ALTER TABLE versions RENAME TO legacy_versions")
        cursor.execute("PRAGMA table_info(files)")
        file_cols = {r[1] for r in cursor.fetchall()}
        if "files" in {r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            if "api_file_id" not in file_cols:
                cursor.execute("ALTER TABLE files RENAME TO legacy_files")
        cursor.execute("PRAGMA table_info(images)")
        image_cols = {r[1] for r in cursor.fetchall()}
        if "images" in {r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            cursor.execute("ALTER TABLE images RENAME TO legacy_images")

        self._create_normalized_schema(cursor)

        if cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='legacy_models'").fetchone():
            cursor.execute("SELECT model_id, name, type, base_model, creator, url, description, tags, published_at, updated_at, metadata FROM legacy_models")
            for mid, name, type_name, base_model, creator, url, description, tags_json, published_at, updated_at, metadata in cursor.fetchall():
                try:
                    raw = json.loads(metadata) if metadata else {}
                    if not isinstance(raw, dict):
                        raw = {}
                except Exception:
                    raw = {}
                creator_id = None
                if isinstance(raw.get("creator"), dict):
                    creator_value = raw["creator"].get("username")
                    image_url = raw["creator"].get("image")
                else:
                    creator_value = creator
                    image_url = None
                if not isinstance(creator_value, str) or not creator_value.strip():
                    creator_value = creator
                if not isinstance(image_url, str) or not image_url.strip():
                    image_url = None
                if isinstance(creator_value, str) and creator_value.strip():
                    creator_key = key(creator_value)
                    row = cursor.execute("SELECT creator_id FROM creators WHERE username_key=?", (creator_key,)).fetchone()
                    if row:
                        creator_id = row[0]
                    else:
                        cursor.execute("INSERT INTO creators (username, username_key, image_url) VALUES (?, ?, ?)",
                                       (creator_value.strip(), creator_key, image_url or None))
                        creator_id = cursor.lastrowid
                cursor.execute("""INSERT INTO models (
                    model_id, creator_id, name, type, base_model, url, description,
                    published_at, updated_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (mid, creator_id, name, type_name, base_model, url, description, published_at, updated_at, json.dumps(raw, ensure_ascii=False)))
                try:
                    tag_values = json.loads(tags_json) if tags_json else []
                except Exception:
                    tag_values = []
                if not tag_values:
                    tag_values = raw.get("tags") if isinstance(raw.get("tags"), list) else []
                seen = set()
                position = 0
                for item in tag_values if isinstance(tag_values, list) else []:
                    tag_name = item.get("name") if isinstance(item, dict) else item
                    if not isinstance(tag_name, str):
                        continue
                    tag_name = tag_name.strip()
                    tag_key = key(tag_name)
                    if not tag_name or not tag_key or tag_key in seen:
                        continue
                    seen.add(tag_key)
                    cursor.execute("INSERT OR IGNORE INTO tags (name, name_key) VALUES (?, ?)", (tag_name, tag_key))
                    tag_id = cursor.execute("SELECT tag_id FROM tags WHERE name_key=?", (tag_key,)).fetchone()[0]
                    cursor.execute("INSERT INTO model_tags (model_id, tag_id, position) VALUES (?, ?, ?)",
                                   (mid, tag_id, position))
                    position += 1

        if cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='legacy_versions'").fetchone():
            cursor.execute("SELECT version_id, model_id, name, base_model, published_at, updated_at, trained_words, metadata FROM legacy_versions")
            for vid, mid, name, base_model, published_at, updated_at, words_json, metadata in cursor.fetchall():
                if cursor.execute("SELECT 1 FROM models WHERE model_id=?", (mid,)).fetchone() is None:
                    continue
                try:
                    raw = json.loads(metadata) if metadata else {}
                    if not isinstance(raw, dict):
                        raw = {}
                except Exception:
                    raw = {}
                cursor.execute("""INSERT INTO versions (
                    version_id, model_id, name, base_model, published_at, updated_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (vid, mid, name, base_model, published_at, updated_at, json.dumps(raw, ensure_ascii=False)))
                try:
                    words = json.loads(words_json) if words_json else []
                except Exception:
                    words = []
                if not words:
                    words = raw.get("trainedWords") if isinstance(raw.get("trainedWords"), list) else []
                for position, word in enumerate(words if isinstance(words, list) else []):
                    cursor.execute("INSERT INTO version_trained_words (version_id, position, word) VALUES (?, ?, ?)",
                                   (vid, position, word))

        if cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='legacy_files'").fetchone():
            cursor.execute("SELECT id, version_id, name, type, size, download_url, format, sha256, path FROM legacy_files")
            for old_id, vid, name, file_type, size, download_url, file_format, sha256, path in cursor.fetchall():
                if cursor.execute("SELECT 1 FROM versions WHERE version_id=?", (vid,)).fetchone() is None:
                    if path:
                        cursor.execute("""INSERT OR IGNORE INTO legacy_file_paths
                            (old_file_id, version_id, name, sha256, path) VALUES (?, ?, ?, ?, ?)""",
                            (old_id, vid, name, sha256, path))
                    continue
                size_kb = size
                if isinstance(size, (int, float)) and size and size > 100000:
                    size_kb = size / 1024.0
                cursor.execute("""INSERT INTO files (
                    version_id, name, type, size_kb, format, download_url, sha256, path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (vid, name, file_type, size_kb, file_format, download_url, sha256, path))
                if not path:
                    continue
                cursor.execute("""INSERT OR IGNORE INTO legacy_file_paths
                    (old_file_id, version_id, name, sha256, path) VALUES (?, ?, ?, ?, ?)""",
                    (old_id, vid, name, sha256, path))

        if cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='legacy_images'").fetchone():
            cursor.execute("SELECT id, model_id, version_id, url, local_path, position, is_gif FROM legacy_images")
            for old_id, model_id, version_id, url, local_path, position, is_gif in cursor.fetchall():
                if version_id is None:
                    cursor.execute("""INSERT OR IGNORE INTO legacy_model_images
                        (id, model_id, url, local_path, position, is_gif)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                        (old_id, model_id, url, local_path, position, is_gif))
                else:
                    if cursor.execute("SELECT 1 FROM versions WHERE version_id=?", (version_id,)).fetchone() is not None:
                        cursor.execute("""INSERT INTO images
                            (version_id, url, local_path, position, is_gif)
                            VALUES (?, ?, ?, ?, ?)""",
                            (version_id, url, local_path, position, is_gif))
                    else:
                        cursor.execute("""INSERT OR IGNORE INTO legacy_model_images
                            (id, model_id, url, local_path, position, is_gif)
                            VALUES (?, ?, ?, ?, ?, ?)""",
                            (old_id, model_id, url, local_path, position, is_gif))

        if cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='downloads'").fetchone():
            cursor.execute("PRAGMA table_info(downloads)")
            download_cols = {r[1] for r in cursor.fetchall()}
            if "restored" not in download_cols:
                cursor.execute("ALTER TABLE downloads ADD COLUMN restored INTEGER DEFAULT 0")

        cursor.execute("DROP TABLE IF EXISTS legacy_files")
        cursor.execute("DROP TABLE IF EXISTS legacy_images")
        cursor.execute("DROP TABLE IF EXISTS legacy_versions")
        cursor.execute("DROP TABLE IF EXISTS legacy_models")
