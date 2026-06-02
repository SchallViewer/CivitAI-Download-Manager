import os
import hashlib


class DatabaseMaintenanceMixin:
    def update_file_statuses(self, download_dir: str):
        """Update download entries:
         - If file missing -> status 'Missing', restored=0
         - If status Missing and file present at recorded path -> status 'Completed', restored=1
         - If status Missing, file renamed/moved within download_dir but same SHA-256 found -> update file_path, status 'Completed', restored=1
        Returns dict counts including scanned files.
        """
        counts = {"missing": 0, "restored": 0, "renamed_restored": 0, "scanned_files": 0, "hashed_files": 0}
        print("[refresh] ==== BEGIN update_file_statuses ====")
        print(f"[refresh] download_dir='{download_dir}'")
        with self._lock:
            try:
                cursor = self.conn.cursor()
                print("[refresh] Querying downloads table...")
                cursor.execute('SELECT id, file_path, status, file_sha256 FROM downloads')
                rows = cursor.fetchall()
                print(f"[refresh] Retrieved {len(rows)} download rows")
                missing_sha_targets = {}
                for idx, (did, fpath, status, sha) in enumerate(rows):
                    print(f"[refresh] Row {idx+1}/{len(rows)} id={did} status={status} path={fpath} sha={(sha or '')[:12]}")
                    exists = bool(fpath and os.path.exists(fpath))
                    if not exists and status == 'Completed':
                        print(f"[refresh] -> Mark Missing (Completed file not found)")
                        cursor.execute('UPDATE downloads SET status = ?, restored = 0 WHERE id = ?', ('Missing', did))
                        counts['missing'] += 1
                        if sha:
                            missing_sha_targets[sha.lower()] = did
                    elif status == 'Missing' and exists:
                        print(f"[refresh] -> Mark Restored (Missing file found again)")
                        cursor.execute('UPDATE downloads SET status = ?, restored = 1 WHERE id = ?', ('Completed', did))
                        counts['restored'] += 1
                    elif status == 'Imported':
                        if exists:
                            print(f"[refresh] -> Upgrade Imported to Completed (file now exists)")
                            cursor.execute('UPDATE downloads SET status = ?, restored = 1 WHERE id = ?', ('Completed', did))
                    elif status == 'Missing' and not exists and sha:
                        print(f"[refresh] -> Candidate for renamed search (has SHA-256)")
                        missing_sha_targets[sha.lower()] = did
                print(f"[refresh] First pass complete. missing_sha_targets={len(missing_sha_targets)}")

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

    def delete_model_version(self, model_id: int, version_id: int):
        """Delete a specific model version and its related rows/files."""
        summary = {"deleted_files": 0, "deleted_image_files": 0, "history_marked": 0, "version_rows": 0, "model_deleted": False}
        with self._lock:
            try:
                cur = self.conn.cursor()
                cur.execute('SELECT id, file_path, status FROM downloads WHERE model_id=? AND version_id=?', (model_id, version_id))
                drows = cur.fetchall()
                for (did, fpath, status) in drows:
                    if status in ('Completed','Imported','Missing'):
                        try:
                            cur.execute('UPDATE downloads SET status=? WHERE id=?', ('Deleted', did))
                            summary['history_marked'] += 1
                        except Exception:
                            pass
                    if fpath and os.path.exists(fpath):
                        try:
                            os.remove(fpath)
                            summary['deleted_files'] += 1
                        except Exception:
                            pass
                try:
                    cur.execute('SELECT local_path FROM images WHERE version_id=? AND local_path IS NOT NULL', (version_id,))
                    img_rows = cur.fetchall()
                    for (ipath,) in img_rows:
                        if ipath and os.path.exists(ipath):
                            try:
                                os.remove(ipath)
                                summary['deleted_image_files'] += 1
                            except Exception:
                                pass
                except Exception:
                    pass
                try:
                    cur.execute('DELETE FROM files WHERE version_id=?', (version_id,))
                except Exception:
                    pass
                try:
                    cur.execute('DELETE FROM images WHERE version_id=?', (version_id,))
                except Exception:
                    pass
                cur.execute('DELETE FROM versions WHERE version_id=?', (version_id,))
                summary['version_rows'] = cur.rowcount
                cur.execute('SELECT 1 FROM versions WHERE model_id=? LIMIT 1', (model_id,))
                if cur.fetchone() is None:
                    try:
                        try:
                            cur.execute('SELECT local_path FROM images WHERE model_id=? AND local_path IS NOT NULL', (model_id,))
                            mimg_rows = cur.fetchall()
                            for (mpath,) in mimg_rows:
                                if mpath and os.path.exists(mpath):
                                    try:
                                        os.remove(mpath)
                                        summary['deleted_image_files'] += 1
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        cur.execute('DELETE FROM images WHERE model_id=?', (model_id,))
                    except Exception:
                        pass
                    cur.execute('DELETE FROM models WHERE model_id=?', (model_id,))
                    summary['model_deleted'] = cur.rowcount > 0
                self.conn.commit()
            except Exception as e:
                print('Error deleting model version:', e)
        return summary
