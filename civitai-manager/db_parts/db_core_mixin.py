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
        cursor.execute('''CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT)''')
        cursor.execute('SELECT value FROM schema_meta WHERE key = "schema_version"')
        row = cursor.fetchone()
        current_version = int(row[0]) if row and row[0] and row[0].isdigit() else 0

        target_version = 4
        if current_version < target_version:
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
                if current_version < 3:
                    pass
                if current_version < 4:
                    try:
                        cursor.execute('ALTER TABLE downloads ADD COLUMN restored INTEGER DEFAULT 0')
                    except sqlite3.Error:
                        pass
            cursor.execute(
                'INSERT OR REPLACE INTO schema_meta (key, value) VALUES ("schema_version", ?)',
                (str(target_version),),
            )
            self.conn.commit()
