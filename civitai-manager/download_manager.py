import os
import requests
import math
from PyQt5.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool, QTimer, Qt
from PyQt5.QtGui import QImage

try:
    from PIL import Image as PILImage, ImageOps as PILImageOps
except Exception:
    PILImage = None

MAX_IMAGE_AREA = 120_000  # ~1.1 MP cap // Reduced to 100 KP

def _process_and_write_image_bytes(content: bytes, dest_path: str, ext: str) -> None:
    """Resize if larger than MAX_IMAGE_AREA and strip metadata, saving back to dest_path.
    Prefer Pillow for robust format handling; fallback to QImage if Pillow unavailable or fails.
    """
    # Try Pillow path first
    if PILImage is not None:
        try:
            from io import BytesIO
            bio = BytesIO(content)
            with PILImage.open(bio) as im:
                # Normalize orientation from EXIF before stripping metadata
                try:
                    im = PILImageOps.exif_transpose(im)
                except Exception:
                    pass
                # Convert to a sane mode for saving (preserve alpha for PNG/WebP)
                fmt_hint = ext.lower().lstrip('.')
                preserve_alpha = fmt_hint in ("png", "webp") and ("A" in im.getbands())
                if not preserve_alpha and im.mode not in ("RGB", "L"):
                    im = im.convert("RGB")
                # Resize if needed
                w, h = im.size
                if w > 0 and h > 0 and (w * h) > MAX_IMAGE_AREA:
                    scale = math.sqrt(MAX_IMAGE_AREA / float(w * h))
                    new_w = max(1, int(w * scale))
                    new_h = max(1, int(h * scale))
                    # Use LANCZOS for downscale quality
                    im = im.resize((new_w, new_h), resample=PILImage.LANCZOS)
                # Strip metadata by not passing any exif/info
                save_kwargs = {}
                if fmt_hint in ("jpg", "jpeg"):
                    save_kwargs.update({"format": "JPEG", "quality": 85, "optimize": True, "progressive": True})
                elif fmt_hint == "png":
                    # Ensure palette is handled
                    if im.mode == "P":
                        im = im.convert("RGBA") if preserve_alpha else im.convert("RGB")
                    save_kwargs.update({"format": "PNG", "optimize": True, "compress_level": 9})
                elif fmt_hint == "webp":
                    save_kwargs.update({"format": "WEBP", "quality": 85, "method": 6})
                elif fmt_hint == "bmp":
                    save_kwargs.update({"format": "BMP"})
                else:
                    # Default to JPEG for unknowns
                    if im.mode not in ("RGB", "L"):
                        im = im.convert("RGB")
                    save_kwargs.update({"format": "JPEG", "quality": 85, "optimize": True, "progressive": True})
                # Overwrite file
                im.save(dest_path, **save_kwargs)
                return
        except Exception:
            # Fall through to QImage path
            pass

    # Fallback: QImage path
    try:
        qimg = QImage.fromData(content)
        if not qimg.isNull():
            w, h = qimg.width(), qimg.height()
            if w > 0 and h > 0 and (w * h) > MAX_IMAGE_AREA:
                scale = math.sqrt(MAX_IMAGE_AREA / float(w * h))
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))
                qimg = qimg.scaled(new_w, new_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            # Choose format based on extension; QImage won't keep EXIF, so metadata is stripped
            fmt = None
            ext_lower = ext.lower().lstrip('.')
            if ext_lower in ('jpg', 'jpeg'):
                fmt = 'JPG'
            elif ext_lower == 'png':
                fmt = 'PNG'
            elif ext_lower == 'webp':
                fmt = 'WEBP'
            elif ext_lower == 'bmp':
                fmt = 'BMP'
            ok = qimg.save(dest_path, fmt if fmt else None)
            if ok:
                return
    except Exception:
        pass

    # Last resort: write raw bytes (no resize/metadata strip)
    with open(dest_path, 'wb') as f:
        f.write(content)
from database import DatabaseManager
from constants import MAX_CONCURRENT_DOWNLOADS
import time

_LOG_PATH = os.path.join(os.path.expanduser('~'), 'civitai_manager_debug.log')

def _append_log(msg: str):
    try:
        with open(_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {msg}\n")
        # Also print critical messages to console
        if any(keyword in msg.lower() for keyword in ['error', 'failed', 'exception', 'crash']):
            print(f"[ERROR] {msg}")
    except Exception:
        pass

def get_debug_log_path():
    """Get the path to the debug log file"""
    return _LOG_PATH

class DownloadSignals(QObject):
    progress = pyqtSignal(str, int, int)  # file_name, received, total
    completed = pyqtSignal(str, str, float)  # file_name, file_path, file_size
    error = pyqtSignal(str, str)  # file_name, error_message

class PostProcessSignals(QObject):
    finished = pyqtSignal(str)  # file_name when post-processing is done
    error = pyqtSignal(str, str)  # file_name, error_message

class PostProcessTask(QRunnable):
    def __init__(self, db_manager, model_data, version, file_path, file_size, task_metadata):
        super().__init__()
        self.db_manager = db_manager
        self.model_data = model_data
        self.version = version
        self.file_path = file_path
        self.file_size = file_size
        self.task_metadata = task_metadata
        self.signals = PostProcessSignals()
        
    def run(self):
        try:
            file_name = self.task_metadata.get('file_name', 'unknown')
            _append_log(f"PostProcessTask.run: starting post-processing for '{file_name}'")
            
            # Record download to database if metadata available
            if hasattr(self, 'db_manager') and self.model_data and self.version and self.file_path:
                # file_size is passed in MB
                try:
                    # If DB already knows this model+version and the file exists, avoid duplicate entries
                    model_id = self.model_data.get('id')
                    version_id = self.version.get('id')
                    try:
                        if not self.db_manager.is_model_downloaded(model_id, version_id, file_path=self.file_path):
                            try:
                                self.db_manager.record_download(
                                    self.model_data,
                                    self.version,
                                    self.file_path,
                                    self.file_size,
                                    status="Completed",
                                    original_file_name=self.task_metadata.get('original_file_name'),
                                    file_sha256=self.task_metadata.get('file_sha256'),
                                    primary_tag=self.task_metadata.get('primary_tag')
                                )
                            except Exception as e:
                                _append_log(f"PostProcessTask.run: record_download failed: {e}")
                        else:
                            _append_log(f"PostProcessTask.run: skipping record_download, already present for {model_id}/{version_id}")
                    except Exception as e:
                        _append_log(f"PostProcessTask.run: is_model_downloaded check failed: {e}")

                    # Upsert model/version and files into normalized tables (including model URL)
                    try:
                        # Save main file row
                        try:
                            file_entry = None
                            for f in (self.version.get('files') or []):
                                if f.get('type') == 'Model' and f.get('name', '').endswith('.safetensors'):
                                    file_entry = f
                                    break
                            if file_entry:
                                cur = self.db_manager.conn.cursor()
                                cur.execute('''
                                    INSERT INTO files (version_id, name, type, size, download_url, format, sha256, path)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (
                                    version_id,
                                    file_entry.get('name'),
                                    file_entry.get('type'),
                                    float(file_entry.get('sizeKB', 0)) * 1024.0 if isinstance(file_entry.get('sizeKB'), (int, float)) else None,
                                    file_entry.get('downloadUrl'),
                                    file_entry.get('format'),
                                    file_entry.get('hashes', {}).get('SHA256') if isinstance(file_entry.get('hashes'), dict) else None,
                                    self.file_path
                                ))
                                self.db_manager.conn.commit()
                        except Exception as e:
                            _append_log(f"PostProcessTask.run: files insert failed: {e}")
                    except Exception:
                        pass

                    # Save preview images (up to 5) for THIS VERSION under a per-model folder
                    try:
                        imgs = []
                        seen = set()

                        def _is_video(u: str) -> bool:
                            if not u or not isinstance(u, str):
                                return False
                            low = u.lower()
                            for ext in ('.mp4', '.webm', '.mov', '.mkv', '.avi'):
                                if low.endswith(ext) or ext in low:
                                    return True
                            return False

                        def add_url(u):
                            if not u or not isinstance(u, str) or _is_video(u):
                                return
                            if u in seen:
                                return
                            seen.add(u)
                            imgs.append(u)

                        # Prefer images from the exact version being downloaded
                        for img in (self.version.get('images') or []):
                            if isinstance(img, dict):
                                add_url(img.get('url') or img.get('thumbnail'))
                            else:
                                add_url(str(img))
                            if len(imgs) >= 5:
                                break

                        # Fallback to model-level gallery only if version has no images
                        if not imgs:
                            for key in ('images', 'gallery', 'modelImages'):
                                for img in (self.model_data.get(key) or []):
                                    if isinstance(img, dict):
                                        add_url(img.get('url') or img.get('thumbnail'))
                                    else:
                                        add_url(str(img))
                                    if len(imgs) >= 5:
                                        break
                                if len(imgs) >= 5:
                                    break

                        # Compute per-model images directory under the model's download directory
                        saved_paths = []
                        if imgs:
                            def _sanitize(s: str) -> str:
                                import re as _re
                                if not isinstance(s, str):
                                    s = str(s or '')
                                s = _re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', s)
                                s = _re.sub(r'\s+', ' ', s).strip().rstrip('. ')
                                return s[:150]

                            model_name = self.model_data.get('name', 'model')
                            model_id = self.model_data.get('id')
                            # Use fixed workspace 'images' folder under current working directory
                            images_root = os.path.join(os.getcwd(), 'images')
                            model_dir_name = f"{_sanitize(model_name)}_{model_id}"
                            images_dir = os.path.join(images_root, model_dir_name)
                            os.makedirs(images_dir, exist_ok=True)

                            for i, url in enumerate(imgs[:5]):
                                try:
                                    r = requests.get(url, timeout=20)
                                    if r.status_code == 200:
                                        ext = os.path.splitext(url.split('?')[0])[1] or '.jpg'
                                        img_path = os.path.join(images_dir, f"v{version_id}_img_{i+1}{ext}")
                                        # Resize (<=1.1MP), strip metadata, and save
                                        _process_and_write_image_bytes(r.content, img_path, ext)
                                        saved_paths.append(img_path)
                                except Exception:
                                    continue

                        # Persist full metadata and saved image paths (upsert)
                        try:
                            if hasattr(self, 'db_manager'):
                                # save_downloaded_model will upsert existing entries
                                self.db_manager.save_downloaded_model(self.model_data, self.version, image_paths=saved_paths)
                        except Exception as e:
                            _append_log(f"PostProcessTask.run: save_downloaded_model failed: {e}")
                    except Exception as e:
                        _append_log(f"PostProcessTask.run: image saving failed: {e}")
                except Exception as e:
                    _append_log(f"PostProcessTask.run: unexpected error: {e}")
                    
            _append_log(f"PostProcessTask.run: completed post-processing for '{file_name}'")
            self.signals.finished.emit(file_name)
            
        except Exception as e:
            file_name = self.task_metadata.get('file_name', 'unknown')
            _append_log(f"PostProcessTask.run: failed post-processing for '{file_name}': {e}")
            self.signals.error.emit(file_name, str(e))

class DownloadTask(QRunnable):
    def __init__(self, file_name, url, save_path, api_key=None, model_data=None, version=None):
        super().__init__()
        self.file_name = file_name
        self.url = url
        self.save_path = save_path
        self.api_key = api_key
        self.signals = DownloadSignals()
        self.is_cancelled = False
        # optional metadata used to record history
        self.model_data = model_data
        self.version = version
    
    def run(self):
        try:
            print(f"DownloadTask.run: starting download '{self.file_name}' from {self.url}")
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            response = requests.get(self.url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            file_size = total_size
            
            os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
            
            try:
                with open(self.save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if self.is_cancelled:
                            print(f"DownloadTask.run: cancelled '{self.file_name}', removing partial file")
                            f.close()  # Close file before attempting to remove it
                            try:
                                os.remove(self.save_path)
                                print(f"DownloadTask.run: successfully removed partial file '{self.save_path}'")
                            except Exception as e:
                                print(f"DownloadTask.run: failed to remove partial file '{self.save_path}': {e}")
                            return
                        
                        f.write(chunk)
                        downloaded += len(chunk)
                        progress = int((downloaded / total_size) * 100) if total_size > 0 else 0
                        self.signals.progress.emit(self.file_name, downloaded, total_size)
            except Exception as e:
                # If any error occurs during download, clean up partial file
                try:
                    if os.path.exists(self.save_path):
                        os.remove(self.save_path)
                        print(f"DownloadTask.run: cleaned up partial file after error: '{self.save_path}'")
                except Exception:
                    pass
                raise e  # Re-raise the original exception
            
            self.signals.completed.emit(self.file_name, self.save_path, file_size / 1024 / 1024)
        except Exception as e:
            # Ensure partial file cleanup on any error
            try:
                if hasattr(self, 'save_path') and os.path.exists(self.save_path):
                    os.remove(self.save_path)
                    print(f"DownloadTask.run: cleaned up partial file after exception: '{self.save_path}'")
            except Exception:
                pass
            self.signals.error.emit(self.file_name, str(e))
    
    def cancel(self):
        self.is_cancelled = True

class DownloadManager(QObject):
    downloads_changed = pyqtSignal()
    download_started = pyqtSignal(str)  # file_name
    download_queued = pyqtSignal(str)   # file_name
    download_file_completed = pyqtSignal(str)  # file_name - model file downloaded
    download_gathering_images = pyqtSignal(str)  # file_name - gathering images
    download_fully_completed = pyqtSignal(str)  # file_name - everything done

    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(MAX_CONCURRENT_DOWNLOADS)
        self.active_downloads = []
        self.queued_downloads = []
        self.download_tasks = {}
        self.download_status = {}  # Track download phases: 'downloading', 'gathering_images', 'completed'
    
    def add_download(self, task):
        print(f"DownloadManager.add_download: received task '{task.file_name}'")
        _append_log(f"add_download: received '{task.file_name}'")

        # connect signals to manage lifecycle and record history BEFORE starting
        try:
            task.signals.completed.connect(lambda fn, fp, fs, t=task: self._on_task_completed(t, fn, fp, fs))
            task.signals.error.connect(lambda fn, err, t=task: self._on_task_error(t, fn, err))
        except Exception:
            pass

        # Deduplicate: avoid adding a task if a task with same file_name or same model/version is already active or queued
        try:
            # check by file_name
            if task.file_name in self.download_tasks or any(getattr(t, 'file_name', None) == task.file_name for t in self.active_downloads + self.queued_downloads):
                _append_log(f"add_download: duplicate file_name detected, skipping: {task.file_name}")
                print(f"DownloadManager.add_download: skipping duplicate file_name '{task.file_name}'")
                return

            # check by model/version identifiers when metadata available
            if task.model_data and task.version:
                mid = task.model_data.get('id')
                vid = task.version.get('id')
                for t in self.active_downloads + self.queued_downloads:
                    try:
                        if getattr(t, 'model_data', None) and getattr(t, 'version', None):
                            if t.model_data.get('id') == mid and t.version.get('id') == vid:
                                _append_log(f"add_download: duplicate model/version detected, skipping: {mid}/{vid}")
                                print(f"DownloadManager.add_download: skipping duplicate model/version '{mid}/{vid}'")
                                return
                    except Exception:
                        continue
        except Exception:
            pass

        # Decide whether to start immediately based on our active_downloads tracking
        try:
            self.debug_queue_state()  # Log current state before making changes
            
            if len(self.active_downloads) < MAX_CONCURRENT_DOWNLOADS:
                print(f"DownloadManager.add_download: starting '{task.file_name}' immediately")
                _append_log(f"add_download: starting '{task.file_name}' immediately")
                
                # Validate task before starting
                if not hasattr(task, 'file_name') or not hasattr(task, 'url') or not hasattr(task, 'save_path'):
                    _append_log(f"add_download: task '{getattr(task, 'file_name', 'unknown')}' missing required attributes")
                    return
                    
                self.active_downloads.append(task)
                
                try:
                    # Prevent Qt from auto-deleting the C++ wrapper while we still hold Python refs
                    try:
                        task.setAutoDelete(False)
                    except Exception as e:
                        _append_log(f"add_download: setAutoDelete failed for '{task.file_name}': {e}")
                        
                    # Start the task
                    self.thread_pool.start(task)
                    self.download_tasks[task.file_name] = task
                    self.download_status[task.file_name] = 'downloading'  # Track initial status
                    
                    try:
                        self.download_started.emit(task.file_name)
                    except Exception as e:
                        _append_log(f"add_download: failed to emit download_started for '{task.file_name}': {e}")
                        
                except RuntimeError as re:
                    _append_log(f"add_download: RuntimeError starting '{task.file_name}': {re}")
                    # Fallback to queuing
                    try:
                        self.active_downloads.remove(task)
                    except Exception:
                        pass
                    self.queued_downloads.append(task)
                    try:
                        self.download_queued.emit(task.file_name)
                    except Exception:
                        pass
                except Exception as e:
                    _append_log(f"add_download: thread_pool.start failed for '{task.file_name}': {e}")
                    # Fallback to queuing
                    try:
                        self.active_downloads.remove(task)
                    except Exception:
                        pass
                    self.queued_downloads.append(task)
                    try:
                        self.download_queued.emit(task.file_name)
                    except Exception:
                        pass
            else:
                # Not enough capacity: queue the task
                print(f"DownloadManager.add_download: queuing '{task.file_name}'")
                _append_log(f"add_download: queuing '{task.file_name}'")
                self.queued_downloads.append(task)
                try:
                    self.download_queued.emit(task.file_name)
                except Exception as e:
                    _append_log(f"add_download: failed to emit download_queued for '{task.file_name}': {e}")
                    
        except Exception as e:
            _append_log(f"add_download: unexpected error in download logic: {e}")
            print(f"DownloadManager.add_download: unexpected error: {e}")
            return

        # notify UI that downloads changed
        try:
            self.downloads_changed.emit()
        except Exception:
            pass
    
    def get_active_downloads(self):
        return self.active_downloads
    
    def get_queued_downloads(self):
        return self.queued_downloads
        
    def get_download_status(self, file_name):
        """Get current status of a download: 'downloading', 'gathering_images', 'completed', or None"""
        return self.download_status.get(file_name)
    
    def cancel_download(self, file_name):
        if file_name in self.download_tasks:
            task = self.download_tasks[file_name]
            
            # Record cancellation in database before cleanup
            try:
                if hasattr(self, 'db_manager') and task.model_data and task.version:
                    # Log cancellation as "Failed" in database
                    self.db_manager.record_download(
                        task.model_data,
                        task.version,
                        task.save_path or '',
                        0,
                        status="Failed",
                        original_file_name=getattr(task, 'original_file_name', None),
                        file_sha256=getattr(task, 'file_sha256', None),
                        primary_tag=getattr(task, 'primary_tag', None)
                    )
                    _append_log(f"cancel_download: recorded cancellation for '{file_name}' as Failed")
            except Exception as e:
                _append_log(f"cancel_download: failed to record cancellation for '{file_name}': {e}")
            
            # request cancellation on the runnable
            try:
                task.cancel()
            except Exception:
                pass

            # remove from active or queued lists if present
            try:
                if task in self.active_downloads:
                    self.active_downloads.remove(task)
                elif task in self.queued_downloads:
                    self.queued_downloads.remove(task)
            except Exception:
                pass

            # remove mapping so a retried download can be re-added
            try:
                if file_name in self.download_tasks:
                    del self.download_tasks[file_name]
            except Exception:
                pass
                
            # Clean up status tracking
            try:
                if file_name in self.download_status:
                    del self.download_status[file_name]
            except Exception:
                pass
            
            # Start next download if available
            if self.queued_downloads:
                try:
                    next_task = self.queued_downloads.pop(0)
                    _append_log(f"cancel_download: promoting queued task '{next_task.file_name}' to active after cancellation")
                    
                    # Validate the task before proceeding
                    if not hasattr(next_task, 'file_name') or not hasattr(next_task, 'url'):
                        _append_log(f"cancel_download: invalid next_task structure, skipping")
                        return
                        
                    self.active_downloads.append(next_task)
                    
                    try:
                        try:
                            next_task.setAutoDelete(False)
                        except Exception as e:
                            _append_log(f"cancel_download: setAutoDelete failed for '{next_task.file_name}': {e}")
                            
                        # Connect signals before starting
                        try:
                            # Disconnect any existing connections to avoid duplicates
                            try:
                                next_task.signals.completed.disconnect()
                                next_task.signals.error.disconnect()
                            except:
                                pass
                                
                            next_task.signals.completed.connect(lambda fn, fp, fs, t=next_task: self._on_task_completed(t, fn, fp, fs))
                            next_task.signals.error.connect(lambda fn, err, t=next_task: self._on_task_error(t, fn, err))
                        except Exception as e:
                            _append_log(f"cancel_download: failed to connect signals for '{next_task.file_name}': {e}")
                            
                        self.thread_pool.start(next_task)
                        
                        # Set status for new task
                        self.download_status[next_task.file_name] = 'downloading'
                        
                        # Ensure mapping is updated so dedupe checks remain accurate
                        self.download_tasks[next_task.file_name] = next_task
                        
                        _append_log(f"cancel_download: successfully started '{next_task.file_name}'")
                        
                        try:
                            self.download_started.emit(next_task.file_name)
                        except Exception as e:
                            _append_log(f"cancel_download: failed to emit download_started for '{next_task.file_name}': {e}")
                            
                    except RuntimeError as re:
                        _append_log(f"cancel_download: RuntimeError starting '{next_task.file_name}': {re}")
                        # Clean up and restore to queue
                        self._cleanup_and_restore_task(next_task)
                    except Exception as e:
                        _append_log(f"cancel_download: failed to start '{next_task.file_name}': {e}")
                        # Clean up and restore to queue
                        self._cleanup_and_restore_task(next_task)
                        
                except IndexError:
                    _append_log("cancel_download: queued_downloads list was empty during pop")
                except Exception as e:
                    _append_log(f"cancel_download: error promoting queued download: {e}")
                    
    def _cleanup_and_restore_task(self, task):
        """Clean up a failed task and restore it to the queue"""
        try:
            if task and hasattr(task, 'file_name'):
                file_name = task.file_name
                
                # Remove from active downloads
                if task in self.active_downloads:
                    self.active_downloads.remove(task)
                    _append_log(f"_cleanup_and_restore_task: removed '{file_name}' from active_downloads")
                    
                # Remove from tracking
                if file_name in self.download_tasks:
                    del self.download_tasks[file_name]
                if file_name in self.download_status:
                    del self.download_status[file_name]
                    
                # Restore to front of queue
                self.queued_downloads.insert(0, task)
                _append_log(f"_cleanup_and_restore_task: restored '{file_name}' to queue")
                
        except Exception as e:
            _append_log(f"_cleanup_and_restore_task: error during cleanup and restore: {e}")
            
    def debug_queue_state(self):
        """Log current queue state for debugging"""
        try:
            _append_log(f"=== QUEUE STATE DEBUG ===")
            _append_log(f"Active downloads: {len(self.active_downloads)}")
            for i, task in enumerate(self.active_downloads):
                try:
                    name = getattr(task, 'file_name', '<no name>')
                    _append_log(f"  Active {i}: {name}")
                except:
                    _append_log(f"  Active {i}: <invalid task>")
                    
            _append_log(f"Queued downloads: {len(self.queued_downloads)}")
            for i, task in enumerate(self.queued_downloads):
                try:
                    name = getattr(task, 'file_name', '<no name>')
                    _append_log(f"  Queued {i}: {name}")
                except:
                    _append_log(f"  Queued {i}: <invalid task>")
                    
            _append_log(f"Download tasks mapping: {len(self.download_tasks)}")
            _append_log(f"Download status mapping: {len(self.download_status)}")
            _append_log(f"Thread pool active count: {self.thread_pool.activeThreadCount()}")
            _append_log(f"Thread pool max threads: {self.thread_pool.maxThreadCount()}")
            _append_log(f"=== END QUEUE STATE ===")
        except Exception as e:
            _append_log(f"debug_queue_state: error logging state: {e}")
            # emit change
            try:
                self.downloads_changed.emit()
            except Exception:
                pass

    def _on_task_completed(self, task, file_name, file_path, file_size):
        # Update status to indicate file download completed but post-processing starting
        self.download_status[file_name] = 'gathering_images'
        
        # Emit signal that file download is complete
        try:
            self.download_file_completed.emit(file_name)
        except Exception:
            pass
            
        # Remove finished task from active list and mapping
        try:
            if task in self.active_downloads:
                self.active_downloads.remove(task)
        except ValueError:
            pass
        try:
            if task.file_name in self.download_tasks:
                del self.download_tasks[task.file_name]
        except Exception:
            pass
            
        # Immediately start next queued download to keep the pipeline flowing
        if self.queued_downloads:
            try:
                next_task = self.queued_downloads.pop(0)
                _append_log(f"_on_task_completed: promoting queued task '{next_task.file_name}' to active")
                
                # Validate the task before adding to active downloads
                if not hasattr(next_task, 'file_name') or not hasattr(next_task, 'url'):
                    _append_log(f"_on_task_completed: invalid task structure, skipping")
                    return
                
                self.active_downloads.append(next_task)
                
                # Use QTimer to defer starting the task to avoid C++ wrapper deletion issues
                # and ensure we're in the main thread when starting
                try:
                    QTimer.singleShot(100, lambda t=next_task: self._start_next_task(t))
                    _append_log(f"_on_task_completed: scheduled next_task '{next_task.file_name}' to start")
                except Exception as e:
                    _append_log(f"_on_task_completed: failed to schedule next_task start: {e}")
                    # If scheduling fails, remove from active and put back in queue
                    try:
                        if next_task in self.active_downloads:
                            self.active_downloads.remove(next_task)
                        self.queued_downloads.insert(0, next_task)
                        _append_log(f"_on_task_completed: restored '{next_task.file_name}' to queue after scheduling failure")
                    except Exception as cleanup_e:
                        _append_log(f"_on_task_completed: failed to restore task to queue: {cleanup_e}")
                        
            except IndexError:
                _append_log("_on_task_completed: queued_downloads list was empty during pop")
            except Exception as e:
                _append_log(f"_on_task_completed: error promoting queued download: {e}")
                # Try to restore task to queue if possible
                try:
                    if 'next_task' in locals() and next_task:
                        if next_task in self.active_downloads:
                            self.active_downloads.remove(next_task)
                        self.queued_downloads.insert(0, next_task)
                        _append_log(f"_on_task_completed: restored task to queue after error")
                except Exception as restore_e:
                    _append_log(f"_on_task_completed: failed to restore task after error: {restore_e}")
        
        # Emit signal that we're gathering images
        try:
            self.download_gathering_images.emit(file_name)
        except Exception:
            pass
        
        # Offload heavy post-processing work to background thread
        if hasattr(self, 'db_manager') and task.model_data and task.version and file_path:
            try:
                # Create metadata for the post-processing task
                task_metadata = {
                    'file_name': file_name,
                    'original_file_name': getattr(task, 'original_file_name', None),
                    'file_sha256': getattr(task, 'file_sha256', None),
                    'primary_tag': getattr(task, 'primary_tag', None)
                }
                
                # Create and start post-processing task
                post_task = PostProcessTask(
                    self.db_manager,
                    task.model_data,
                    task.version,
                    file_path,
                    file_size,  # file_size is passed in MB
                    task_metadata
                )
                
                # Connect signals to handle completion
                post_task.signals.finished.connect(self._on_post_process_finished)
                post_task.signals.error.connect(self._on_post_process_error)
                
                # Start the post-processing in background
                try:
                    post_task.setAutoDelete(False)
                except Exception:
                    pass
                self.thread_pool.start(post_task)
                
                _append_log(f"_on_task_completed: started post-processing for '{file_name}'")
                
            except Exception as e:
                _append_log(f"_on_task_completed: failed to start post-processing for '{file_name}': {e}")
                # If post-processing fails to start, mark as completed anyway
                self._on_post_process_finished(file_name)
    def _on_post_process_finished(self, file_name):
        """Called when post-processing (DB updates, image downloads) completes in background"""
        _append_log(f"_on_post_process_finished: post-processing completed for '{file_name}'")
        
        # Mark download as fully completed
        self.download_status[file_name] = 'completed'
        
        # Emit signal that download is fully complete
        try:
            self.download_fully_completed.emit(file_name)
        except Exception:
            pass
            
        # Clean up status tracking
        try:
            if file_name in self.download_status:
                del self.download_status[file_name]
        except Exception:
            pass
            
        # Refresh UI
        try:
            self.downloads_changed.emit()
        except Exception:
            pass
            
    def _on_post_process_error(self, file_name, error_message):
        """Called when post-processing fails"""
        _append_log(f"_on_post_process_error: post-processing failed for '{file_name}': {error_message}")
        
        # Mark download as completed even if post-processing failed
        self.download_status[file_name] = 'completed'
        
        # Emit signal that download is complete (even with errors)
        try:
            self.download_fully_completed.emit(file_name)
        except Exception:
            pass
            
        # Clean up status tracking
        try:
            if file_name in self.download_status:
                del self.download_status[file_name]
        except Exception:
            pass
            
        # Still emit downloads_changed to update UI
        try:
            self.downloads_changed.emit()
        except Exception:
            pass

    def _start_next_task(self, task):
        """Start the next queued task with comprehensive error handling"""
        try:
            if not task:
                _append_log("_start_next_task: received None task, skipping")
                return
                
            if not hasattr(task, 'file_name'):
                _append_log("_start_next_task: task missing file_name attribute, skipping")
                return
                
            _append_log(f"_start_next_task: attempting to start '{task.file_name}'")
            
            # Check if task is still valid
            if not hasattr(task, 'url') or not hasattr(task, 'save_path'):
                _append_log(f"_start_next_task: task '{task.file_name}' missing required attributes")
                return
                
            # Ensure task hasn't been deleted/destroyed
            try:
                task_filename = task.file_name  # Test access to ensure object is valid
            except RuntimeError as re:
                _append_log(f"_start_next_task: task object destroyed, cannot start: {re}")
                return
            except Exception as e:
                _append_log(f"_start_next_task: task object invalid: {e}")
                return
            
            # Set AutoDelete to False to prevent Qt from deleting the object
            try:
                task.setAutoDelete(False)
            except RuntimeError as re:
                _append_log(f"_start_next_task: setAutoDelete failed (object destroyed?): {re}")
                return
            except Exception as e:
                _append_log(f"_start_next_task: setAutoDelete failed: {e}")
                # Continue anyway, this might not be critical
                
            # Add task to tracking before starting
            try:
                self.download_tasks[task.file_name] = task
                self.download_status[task.file_name] = 'downloading'
                _append_log(f"_start_next_task: added '{task.file_name}' to tracking")
            except Exception as e:
                _append_log(f"_start_next_task: failed to add task to tracking: {e}")
                return
                
            # Connect signals if not already connected
            try:
                # Disconnect any existing connections to avoid duplicates
                try:
                    task.signals.completed.disconnect()
                    task.signals.error.disconnect()
                except:
                    pass  # Ignore if no connections exist
                    
                # Connect fresh signals
                task.signals.completed.connect(lambda fn, fp, fs, t=task: self._on_task_completed(t, fn, fp, fs))
                task.signals.error.connect(lambda fn, err, t=task: self._on_task_error(t, fn, err))
                _append_log(f"_start_next_task: connected signals for '{task.file_name}'")
            except Exception as e:
                _append_log(f"_start_next_task: failed to connect signals for '{task.file_name}': {e}")
                # Continue anyway, signals might already be connected
                
            # Start the task in thread pool
            try:
                self.thread_pool.start(task)
                _append_log(f"_start_next_task: successfully started '{task.file_name}' in thread pool")
            except RuntimeError as re:
                _append_log(f"_start_next_task: RuntimeError starting '{task.file_name}': {re}")
                # Clean up tracking
                self._cleanup_failed_task(task)
                return
            except Exception as e:
                _append_log(f"_start_next_task: failed to start '{task.file_name}' in thread pool: {e}")
                # Clean up tracking
                self._cleanup_failed_task(task)
                return
                
            # Emit download started signal
            try:
                self.download_started.emit(task.file_name)
                _append_log(f"_start_next_task: emitted download_started for '{task.file_name}'")
            except Exception as e:
                _append_log(f"_start_next_task: failed to emit download_started for '{task.file_name}': {e}")
                # Don't return here, download might still work
                
        except Exception as e:
            # Catch-all for any unexpected errors
            task_name = getattr(task, 'file_name', '<unknown>') if task else '<None>'
            _append_log(f"_start_next_task: unexpected error starting '{task_name}': {e}")
            if task:
                self._cleanup_failed_task(task)

        # Always emit downloads_changed to update UI
        try:
            self.downloads_changed.emit()
        except Exception as e:
            _append_log(f"_start_next_task: failed to emit downloads_changed: {e}")
            
    def _cleanup_failed_task(self, task):
        """Clean up tracking for a task that failed to start"""
        try:
            if task and hasattr(task, 'file_name'):
                file_name = task.file_name
                
                # Remove from active downloads if present
                if task in self.active_downloads:
                    self.active_downloads.remove(task)
                    _append_log(f"_cleanup_failed_task: removed '{file_name}' from active_downloads")
                    
                # Remove from tracking
                if file_name in self.download_tasks:
                    del self.download_tasks[file_name]
                    _append_log(f"_cleanup_failed_task: removed '{file_name}' from download_tasks")
                    
                if file_name in self.download_status:
                    del self.download_status[file_name]
                    _append_log(f"_cleanup_failed_task: removed '{file_name}' from download_status")
                    
        except Exception as e:
            _append_log(f"_cleanup_failed_task: error during cleanup: {e}")

    def _on_task_error(self, task, file_name, error_message):
        # Treat error similar to completion for lifecycle management
        # Optionally record error in DB
        try:
            if hasattr(self, 'db_manager') and task.model_data and task.version:
                # Use normalized Failed status instead of arbitrary message
                self.db_manager.record_download(
                    task.model_data,
                    task.version,
                    task.save_path or '',
                    0,
                    status="Failed",
                    original_file_name=getattr(task, 'original_file_name', None),
                    file_sha256=getattr(task, 'file_sha256', None),
                    primary_tag=getattr(task, 'primary_tag', None)
                )
        except Exception:
            pass

        self._on_task_completed(task, file_name, None, 0)