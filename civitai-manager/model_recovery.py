"""
Model Recovery Manager - Recovers metadata for unknown models in download folder
"""
import os
import hashlib
import json
import requests
import time
import math
import webbrowser
import tempfile
from datetime import datetime
from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QProgressBar, QTextEdit, QTableWidget, QTableWidgetItem,
    QComboBox, QMessageBox, QHeaderView, QFrame
)
from PyQt5.QtGui import QFont, QColor, QImage

try:
    from PIL import Image as PILImage, ImageOps as PILImageOps
except Exception:
    PILImage = None

from constants import PRIMARY_COLOR, TEXT_COLOR, BACKGROUND_COLOR

# Use the same image processing constants as download_manager
MAX_IMAGE_AREA = 700_000  # ~700K pixels cap

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


class RecoveryWorker(QThread):
    """Worker thread for model recovery process"""
    
    # Signals
    status_update = pyqtSignal(str)  # status message
    progress_update = pyqtSignal(int, int)  # current, total
    model_processed = pyqtSignal(str, str, str)  # filename, status, details
    recovery_finished = pyqtSignal(dict)  # final statistics
    
    def __init__(self, download_folder, db_manager, api_key, settings_manager=None):
        super().__init__()
        self.download_folder = download_folder
        self.db_manager = db_manager
        self.api_key = api_key
        self.settings_manager = settings_manager
        self.is_cancelled = False
        
        # Results tracking
        self.results = []
        self.duplicates = []
        self.successful_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        
    def get_primary_tag_from_hierarchy(self, model_data):
        """Determine primary tag using the tag hierarchy from settings"""
        try:
            tags = model_data.get('tags') or []
            if not tags:
                return None
                
            # Build normalized list of tag names
            names = []
            for t in tags:
                if isinstance(t, dict):
                    n = t.get('name') or ''
                else:
                    n = str(t or '')
                if n:
                    names.append(n)
            
            if not names:
                return None
                
            # Get user-configured priority tags from settings
            try:
                if self.settings_manager:
                    pri_raw = self.settings_manager.get('priority_tags', '') or ''
                    priority = [p.strip().lower() for p in pri_raw.split(',') if p.strip()]
                    if not priority:
                        priority = ['meme','concept','character','style','clothing','pose']
                else:
                    priority = ['meme','concept','character','style','clothing','pose']
            except Exception:
                priority = ['meme','concept','character','style','clothing','pose']
                
            # Create case-insensitive mapping while preserving original casing
            lower_map = {n.lower(): n for n in names}
            
            # Find the first priority tag that exists in the model
            chosen = None
            for p in priority:
                if p in lower_map:
                    chosen = lower_map[p]
                    break
                    
            # Fallback to first tag if no priority tag matches
            if not chosen and names:
                chosen = names[0]
                
            print(f"[DEBUG] Tag selection - Available tags: {names}, Priority order: {priority}, Chosen: {chosen}")
            return chosen
            
        except Exception as e:
            print(f"[DEBUG] Error determining primary tag: {e}")
            return None
        
    def rollback_recovery(self):
        """Rollback database changes"""
        try:
            success = self.db_manager.rollback_transaction()
            if success:
                print("Successfully rolled back database transaction")
            else:
                print("Failed to rollback database transaction")
            return success
        except Exception as e:
            print(f"Error rolling back transaction: {e}")
            return False
    
    def commit_recovery(self):
        """Commit the database transaction"""
        try:
            success = self.db_manager.commit_transaction()
            if success:
                print("Database transaction committed successfully")
            else:
                print("Failed to commit database transaction")
            return success
        except Exception as e:
            print(f"Error committing transaction: {e}")
            return False
    
    def cancel_recovery(self):
        """Cancel the recovery process"""
        self.is_cancelled = True
    
    def export_html_visualizer(self, results_data):
        """Export recovery results as an interactive HTML visualizer"""
        try:
            # Get the directory where this script is located
            script_dir = os.path.dirname(os.path.abspath(__file__))
            managers_dir = os.path.join(script_dir, 'managers')
            
            # Paths to template files
            html_template_path = os.path.join(managers_dir, 'recovery_visualizer.html')
            css_path = os.path.join(managers_dir, 'styles', 'recovery_visualizer.css')
            js_path = os.path.join(managers_dir, 'scripts', 'recovery_visualizer.js')
            
            # Check if template files exist
            if not all(os.path.exists(p) for p in [html_template_path, css_path, js_path]):
                print("Warning: HTML template files not found, skipping HTML export")
                return None
            
            # Read template files
            with open(html_template_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            with open(css_path, 'r', encoding='utf-8') as f:
                css_content = f.read()
            
            with open(js_path, 'r', encoding='utf-8') as f:
                js_content = f.read()
            
            # Process results data for HTML export
            processed_results = []
            total_size = 0
            
            for result in results_data.get('results', []):
                # Extract file size from filename if available
                file_path = result.get('filename', '')
                file_size = 0
                
                try:
                    if os.path.exists(file_path):
                        file_size = os.path.getsize(file_path)
                        total_size += file_size
                except Exception:
                    pass
                
                processed_result = {
                    'filename': os.path.basename(result.get('filename', 'Unknown')),
                    'filepath': result.get('filename', 'Unknown'),
                    'status': result.get('status', 'Unknown'),
                    'size': file_size,
                    'details': result.get('details', 'No details available'),
                    'modelId': result.get('model_id'),
                    'versionId': result.get('version_id'),
                    'modelName': result.get('model_name'),
                    'duplicate_files': result.get('duplicate_files', [])  # Include duplicate files info
                }
                processed_results.append(processed_result)
            
            # Add duplicate files to results (enhance duplicate detection)
            duplicate_hash_map = {}
            
            # First, build a map of hash to all files with that hash
            for dup_file in results_data.get('duplicate_files', []):
                try:
                    file_hash = self.calculate_sha256(dup_file)
                    if file_hash:
                        if file_hash not in duplicate_hash_map:
                            duplicate_hash_map[file_hash] = []
                        duplicate_hash_map[file_hash].append(dup_file)
                except Exception:
                    pass
            
            # Now process each duplicate file with enhanced details
            for dup_file in results_data.get('duplicate_files', []):
                try:
                    file_size = os.path.getsize(dup_file) if os.path.exists(dup_file) else 0
                    total_size += file_size
                    
                    # Find other files with the same hash
                    try:
                        file_hash = self.calculate_sha256(dup_file)
                        other_files = []
                        if file_hash and file_hash in duplicate_hash_map:
                            other_files = [f for f in duplicate_hash_map[file_hash] if f != dup_file]
                    except Exception:
                        other_files = []
                    
                    other_filenames = [os.path.basename(f) for f in other_files]
                    
                    if other_filenames:
                        details = f'Duplicate file found. Same hash as: {", ".join(other_filenames)}'
                    else:
                        details = 'Duplicate file found in download directory'
                    
                except Exception:
                    file_size = 0
                    other_files = []
                    details = 'Duplicate file found in download directory'

                processed_results.append({
                    'filename': os.path.basename(dup_file),
                    'filepath': dup_file,
                    'status': 'Duplicate',
                    'size': file_size,
                    'details': details,
                    'modelId': None,
                    'versionId': None,
                    'modelName': None,
                    'duplicate_files': other_files  # Include list of files with same hash
                })            # Prepare statistics
            statistics = {
                'successful': results_data.get('successful', 0),
                'failed': results_data.get('failed', 0),
                'skipped': results_data.get('skipped', 0),
                'duplicates': results_data.get('duplicates', 0),
                'total': len(processed_results),
                'totalSize': total_size,
                'timestamp': datetime.now().isoformat()
            }
            
            # Create data payload for JavaScript
            recovery_data = {
                'results': processed_results,
                'statistics': statistics
            }
            
            # Create self-contained HTML file
            standalone_html = html_content.replace(
                '<link rel="stylesheet" href="styles/recovery_visualizer.css">',
                f'<style>{css_content}</style>'
            ).replace(
                '<script src="scripts/recovery_visualizer.js"></script>',
                f'<script>{js_content}</script>'
            )
            
            # Inject data into HTML
            data_script = f"""
            <script>
                window.recoveryData = {json.dumps(recovery_data, indent=2)};
            </script>
            """
            
            # Insert data script before closing body tag
            standalone_html = standalone_html.replace('</body>', f'{data_script}</body>')
            
            # Create output file in temp directory
            output_dir = tempfile.gettempdir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(output_dir, f'civitai_recovery_results_{timestamp}.html')
            
            # Write the HTML file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(standalone_html)
            
            print(f"HTML visualizer exported to: {output_file}")
            return output_file
            
        except Exception as e:
            print(f"Failed to export HTML visualizer: {e}")
            return None
        
    def calculate_sha256(self, file_path):
        """Calculate SHA256 hash of a file"""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    if self.is_cancelled:
                        return None
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest().upper()
        except Exception as e:
            return None
            
    def check_api_status(self):
        """Check if CivitAI API is accessible"""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            response = requests.get("https://civitai.com/api/v1/models?limit=1", 
                                  headers=headers, timeout=10)
            return response.status_code == 200
        except Exception:
            return False
            
    def query_model_by_hash(self, file_hash):
        """Query CivitAI API for model by hash"""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            url = f"https://civitai.com/api/v1/model-versions/by-hash/{file_hash}"
            print(f"[DEBUG] API Request: {url}")
            response = requests.get(url, headers=headers, timeout=15)
            print(f"[DEBUG] API Response Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"[DEBUG] API Response: Found model '{data.get('model', {}).get('name', 'Unknown')}'")
                return data
            elif response.status_code == 404:
                print(f"[DEBUG] API Response: Hash not found in CivitAI database")
                return None  # Hash not found
            else:
                print(f"[DEBUG] API Response: Error {response.status_code}")
                response.raise_for_status()
        except Exception as e:
            print(f"[DEBUG] API Query Exception: {e}")
            raise Exception(f"API query failed: {str(e)}")
            
    def download_images(self, model_data, version_data, model_id, version_id):
        """Download and save model images"""
        try:
            images = []
            
            # Get images from model data
            model_images = model_data.get('images', [])[:5]  # Limit to 5 images
            
            # Get images from version data  
            version_images = version_data.get('images', [])[:5]
            
            # Combine and deduplicate
            all_images = model_images + version_images
            seen_urls = set()
            unique_images = []
            for img in all_images:
                url = img.get('url')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_images.append(img)
                    if len(unique_images) >= 5:
                        break
            
            # Use the workspace images folder (not download folder)
            # Get the script directory and use the images folder relative to it
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            images_dir = os.path.join(script_dir, 'images')
            
            # Sanitize model name for folder name (remove invalid characters)
            model_name = model_data.get('name', 'Unknown')
            safe_model_name = "".join(c for c in model_name if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_model_name = safe_model_name.replace(' ', '_')
            if not safe_model_name:
                safe_model_name = 'Unknown'
            
            model_images_dir = os.path.join(images_dir, f"{safe_model_name}_{model_id}")
            
            print(f"[DEBUG] Found {len(unique_images)} unique images to download")
            print(f"[DEBUG] Images will be saved to: {model_images_dir}")
            
            if unique_images:
                os.makedirs(model_images_dir, exist_ok=True)
                print(f"[DEBUG] Created image directory: {model_images_dir}")
                
            for i, img in enumerate(unique_images):
                if self.is_cancelled:
                    break
                    
                try:
                    url = img.get('url')
                    if not url:
                        print(f"[DEBUG] Skipping image {i} - no URL")
                        continue
                        
                    print(f"[DEBUG] Downloading image {i+1}/{len(unique_images)}: {url}")
                    response = requests.get(url, timeout=15)
                    response.raise_for_status()
                    
                    # Determine file extension
                    content_type = response.headers.get('content-type', '')
                    if 'jpeg' in content_type or 'jpg' in content_type:
                        ext = '.jpg'
                    elif 'png' in content_type:
                        ext = '.png'
                    elif 'webp' in content_type:
                        ext = '.webp'
                    elif 'gif' in content_type:
                        ext = '.gif'
                    else:
                        ext = '.jpg'  # Default
                    
                    image_filename = f"image_{i}{ext}"
                    image_path = os.path.join(model_images_dir, image_filename)
                    
                    # Process and save image with size limits and metadata stripping
                    print(f"[DEBUG] Processing and saving image: {image_filename}")
                    _process_and_write_image_bytes(response.content, image_path, ext)
                    
                    # Store image in database (only essential fields)
                    self.db_manager.store_image(
                        model_id=model_id,
                        version_id=version_id, 
                        url=url,
                        local_path=image_path,
                        position=i,
                        is_gif=ext == '.gif',
                        auto_commit=False
                    )
                    
                    images.append(image_path)
                    
                except Exception as e:
                    print(f"Failed to download image {url}: {e}")
                    continue
                    
            return images
            
        except Exception as e:
            print(f"Failed to download images: {e}")
            return []
    
    def run(self):
        """Main recovery process"""
        try:
            # Begin transaction for rollback capability
            self.status_update.emit("Starting database transaction...")
            try:
                success = self.db_manager.begin_transaction()
                if success:
                    print("Database transaction started successfully")
                else:
                    print("Warning: Could not start transaction")
            except Exception as e:
                print(f"Warning: Could not start transaction: {e}")
                # Continue anyway, just without rollback capability
            
            # Check API status first
            self.status_update.emit("Checking CivitAI API status...")
            if not self.check_api_status():
                self.recovery_finished.emit({
                    'success': False,
                    'error': 'CivitAI API is not accessible. Please check your internet connection.'
                })
                return
            
            # Find all model files in download folder
            self.status_update.emit("Scanning download folder for models...")
            model_files = []
            supported_extensions = {'.safetensors', '.ckpt', '.pt', '.pth', '.bin'}
            
            for root, dirs, files in os.walk(self.download_folder):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in supported_extensions):
                        file_path = os.path.join(root, file)
                        model_files.append(file_path)
            
            if not model_files:
                self.recovery_finished.emit({
                    'success': True,
                    'successful': 0,
                    'failed': 0,
                    'skipped': 0,
                    'duplicates': 0,
                    'results': [],
                    'duplicate_files': []
                })
                return
            
            total_files = len(model_files)
            self.status_update.emit(f"Found {total_files} model files. Starting recovery...")
            print(f"[DEBUG] Found {total_files} model files to process:")
            for i, file_path in enumerate(model_files[:5]):  # Show first 5 files
                print(f"[DEBUG]   {i+1}. {os.path.basename(file_path)}")
            if total_files > 5:
                print(f"[DEBUG]   ... and {total_files - 5} more files")
            
            # Track hashes to detect duplicates
            hash_to_files = {}
            processed_hashes = set()
            
            # Get existing hashes from database to skip already registered models
            existing_hashes = set()
            try:
                history = self.db_manager.get_download_history()
                for record in history:
                    if record.get('file_sha256'):
                        existing_hashes.add(record['file_sha256'].upper())
                print(f"[DEBUG] Found {len(existing_hashes)} existing hashes in database")
            except Exception as e:
                print(f"[DEBUG] Error getting existing hashes: {e}")
                pass
            
            for i, file_path in enumerate(model_files):
                if self.is_cancelled:
                    break
                    
                filename = os.path.basename(file_path)
                self.progress_update.emit(i + 1, total_files)
                self.status_update.emit(f"Processing: {filename}")
                print(f"[DEBUG] Processing file {i+1}/{total_files}: {filename}")
                
                # Calculate hash
                file_hash = self.calculate_sha256(file_path)
                if not file_hash:
                    if self.is_cancelled:
                        break
                    print(f"[DEBUG] Failed to calculate hash for {filename}")
                    self.results.append({
                        'filename': filename,
                        'status': 'Failed',
                        'details': 'Could not calculate file hash'
                    })
                    self.failed_count += 1
                    self.model_processed.emit(filename, 'Failed', 'Could not calculate file hash')
                    continue
                
                print(f"[DEBUG] Calculated hash for {filename}: {file_hash}")
                
                # Check for duplicates
                if file_hash in hash_to_files:
                    hash_to_files[file_hash].append(file_path)
                else:
                    hash_to_files[file_hash] = [file_path]
                
                # Skip if already processed this hash
                if file_hash in processed_hashes:
                    print(f"[DEBUG] Skipping duplicate hash: {file_hash}")
                    # Find other files with the same hash
                    other_files = [f for f in hash_to_files[file_hash] if f != file_path]
                    other_filenames = [os.path.basename(f) for f in other_files]
                    
                    details = f'Duplicate hash already processed. Same hash as: {", ".join(other_filenames)}'
                    self.results.append({
                        'filename': filename,
                        'status': 'Duplicate',
                        'details': details,
                        'duplicate_files': other_files  # Include list of files with same hash
                    })
                    self.skipped_count += 1
                    self.model_processed.emit(filename, 'Duplicate', details)
                    continue
                
                # Skip if already in database
                if file_hash in existing_hashes:
                    print(f"[DEBUG] Skipping {filename} - already in database with hash: {file_hash}")
                    self.results.append({
                        'filename': filename,
                        'status': 'Skipped',
                        'details': 'Already registered in database'
                    })
                    self.skipped_count += 1
                    self.model_processed.emit(filename, 'Skipped', 'Already registered in database')
                    processed_hashes.add(file_hash)
                    continue
                
                try:
                    # Query API for model data
                    print(f"[DEBUG] Querying CivitAI API for hash: {file_hash}")
                    version_data = self.query_model_by_hash(file_hash)
                    if not version_data:
                        print(f"[DEBUG] No model found for hash: {file_hash}")
                        self.results.append({
                            'filename': filename,
                            'status': 'Failed',
                            'details': 'Model not found in CivitAI database'
                        })
                        self.failed_count += 1
                        self.model_processed.emit(filename, 'Failed', 'Model not found in CivitAI database')
                        processed_hashes.add(file_hash)
                        continue
                    
                    print(f"[DEBUG] Found version data for {filename}")
                    
                    # Get model ID from version data
                    model_id = version_data.get('modelId')
                    if not model_id:
                        print(f"[DEBUG] No modelId found in version data for {filename}")
                        self.results.append({
                            'filename': filename,
                            'status': 'Failed',
                            'details': 'Invalid API response: missing modelId'
                        })
                        self.failed_count += 1
                        self.model_processed.emit(filename, 'Failed', 'Invalid API response: missing modelId')
                        processed_hashes.add(file_hash)
                        continue
                    
                    # Always fetch full model data using the modelId for complete information
                    print(f"[DEBUG] Found modelId: {model_id}, fetching full model data...")
                    try:
                        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                        model_response = requests.get(f"https://civitai.com/api/v1/models/{model_id}", 
                                                    headers=headers, timeout=15)
                        if model_response.status_code == 200:
                            model_data = model_response.json()
                            print(f"[DEBUG] Successfully fetched model data: {model_data.get('name', 'Unknown')}")
                        else:
                            print(f"[DEBUG] Failed to fetch model data: {model_response.status_code}")
                            # Fall back to basic model data from version response
                            model_data = version_data.get('model', {})
                            if not model_data.get('name'):
                                raise Exception(f"Failed to fetch model data: {model_response.status_code}")
                            print(f"[DEBUG] Using basic model data from version response: {model_data.get('name', 'Unknown')}")
                            # Add the model ID to the basic model data
                            model_data['id'] = model_id
                    except Exception as e:
                        print(f"[DEBUG] Error fetching model data: {e}")
                        # Try to use basic model data from version response as fallback
                        model_data = version_data.get('model', {})
                        if model_data.get('name'):
                            print(f"[DEBUG] Using fallback model data: {model_data.get('name', 'Unknown')}")
                            model_data['id'] = model_id  # Ensure ID is set
                        else:
                            self.results.append({
                                'filename': filename,
                                'status': 'Failed',
                                'details': f'Failed to fetch model data: {str(e)}'
                            })
                            self.failed_count += 1
                            self.model_processed.emit(filename, 'Failed', f'Failed to fetch model data: {str(e)}')
                            processed_hashes.add(file_hash)
                            continue
                    
                    if not model_data or not model_data.get('id'):
                        print(f"[DEBUG] No valid model data available for {filename}")
                        self.results.append({
                            'filename': filename,
                            'status': 'Failed',
                            'details': 'Invalid API response: missing model data'
                        })
                        self.failed_count += 1
                        self.model_processed.emit(filename, 'Failed', 'Invalid API response: missing model data')
                        processed_hashes.add(file_hash)
                        continue
                    
                    version_id = version_data.get('id')
                    model_id = model_data.get('id')  # Get the actual model ID from model data
                    
                    if not model_id or not version_id:
                        print(f"[DEBUG] Missing IDs for {filename} - model_id: {model_id}, version_id: {version_id}")
                        self.results.append({
                            'filename': filename,
                            'status': 'Failed',
                            'details': 'Invalid API response: missing IDs'
                        })
                        self.failed_count += 1
                        self.model_processed.emit(filename, 'Failed', 'Invalid API response: missing IDs')
                        processed_hashes.add(file_hash)
                        continue
                    print(f"[DEBUG] Model ID: {model_id}, Version ID: {version_id}")
                    
                    # Check if this model/version is already in database
                    if self.db_manager.has_download_record(model_id, version_id):
                        print(f"[DEBUG] Model {model_id}/{version_id} already in database")
                        self.results.append({
                            'filename': filename,
                            'status': 'Skipped',
                            'details': 'Model already registered in database'
                        })
                        self.skipped_count += 1
                        self.model_processed.emit(filename, 'Skipped', 'Model already registered in database')
                        processed_hashes.add(file_hash)
                        continue
                    
                    recovery_complete = True
                    recovery_details = []
                    
                    print(f"[DEBUG] Starting data storage for {filename}")
                    
                    # Store model metadata
                    try:
                        print(f"[DEBUG] Storing model metadata: {model_data.get('name', 'Unknown')}")
                        self.db_manager.store_model(model_data, auto_commit=False)
                        recovery_details.append("Model metadata stored")
                        print(f"[DEBUG] Model metadata stored successfully")
                    except Exception as e:
                        print(f"[DEBUG] Failed to store model metadata: {e}")
                        recovery_complete = False
                        recovery_details.append(f"Failed to store model metadata: {str(e)}")
                    
                    # Store version metadata
                    try:
                        trained_words = version_data.get('trainedWords', [])
                        print(f"[DEBUG] Storing version metadata: {version_data.get('name', 'Unknown')}")
                        print(f"[DEBUG] Trained words: {trained_words}")
                        self.db_manager.store_version(version_data, auto_commit=False)
                        recovery_details.append("Version metadata stored")
                        print(f"[DEBUG] Version metadata stored successfully")
                    except Exception as e:
                        print(f"[DEBUG] Failed to store version metadata: {e}")
                        recovery_complete = False
                        recovery_details.append(f"Failed to store version metadata: {str(e)}")
                    
                    # Download and store images
                    try:
                        print(f"[DEBUG] Starting image download for {filename}")
                        images = self.download_images(model_data, version_data, model_id, version_id)
                        recovery_details.append(f"Downloaded {len(images)} images")
                        print(f"[DEBUG] Downloaded {len(images)} images successfully")
                    except Exception as e:
                        print(f"[DEBUG] Failed to download images: {e}")
                        recovery_complete = False
                        recovery_details.append(f"Failed to download images: {str(e)}")
                    
                    # Only record download if recovery is complete
                    if recovery_complete:
                        try:
                            # Get file size
                            file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
                            
                            # Determine primary tag using tag hierarchy
                            primary_tag = self.get_primary_tag_from_hierarchy(model_data)
                            print(f"[DEBUG] Using primary tag from hierarchy: {primary_tag}")
                            
                            # Record as completed download
                            print(f"[DEBUG] Recording download for {filename} in database")
                            success = self.db_manager.record_download(
                                model_data=model_data,
                                version=version_data,
                                file_path=file_path,
                                file_size=file_size,
                                status="Completed",
                                original_file_name=filename,
                                file_sha256=file_hash,
                                primary_tag=primary_tag
                            )
                            print(f"[DEBUG] Download record success: {success}")
                            
                            if success:
                                print(f"[DEBUG] Recovery completed successfully for {filename}")
                                self.results.append({
                                    'filename': filename,
                                    'status': 'Success',
                                    'details': 'Model successfully recovered'
                                })
                                self.successful_count += 1
                                self.model_processed.emit(filename, 'Success', 'Model successfully recovered')
                            else:
                                print(f"[DEBUG] Failed to record download for {filename}")
                                self.results.append({
                                    'filename': filename,
                                    'status': 'Failed',
                                    'details': 'Failed to record download in database'
                                })
                                self.failed_count += 1
                                self.model_processed.emit(filename, 'Failed', 'Failed to record download in database')
                        except Exception as e:
                            self.results.append({
                                'filename': filename,
                                'status': 'Failed',
                                'details': f'Failed to record download: {str(e)}'
                            })
                            self.failed_count += 1
                            self.model_processed.emit(filename, 'Failed', f'Failed to record download: {str(e)}')
                    else:
                        self.results.append({
                            'filename': filename,
                            'status': 'Failed',
                            'details': 'Incomplete recovery: ' + '; '.join(recovery_details)
                        })
                        self.failed_count += 1
                        self.model_processed.emit(filename, 'Failed', 'Incomplete recovery')
                    
                    processed_hashes.add(file_hash)
                    
                except Exception as e:
                    print(f"[DEBUG] Exception during recovery of {filename}: {e}")
                    self.results.append({
                        'filename': filename,
                        'status': 'Failed',
                        'details': f'Recovery error: {str(e)}'
                    })
                    self.failed_count += 1
                    self.model_processed.emit(filename, 'Failed', f'Recovery error: {str(e)}')
                    processed_hashes.add(file_hash)
            
            # Identify duplicates
            duplicate_files = []
            for file_hash, files in hash_to_files.items():
                if len(files) > 1:
                    duplicate_files.extend(files)
            
            # Finish recovery
            if self.is_cancelled:
                # Rollback on cancellation
                self.rollback_recovery()
                self.recovery_finished.emit({
                    'success': False,
                    'error': 'Recovery was cancelled by user'
                })
            else:
                # Commit the transaction on successful completion
                self.commit_recovery()
                
                # Prepare results data for emission
                results_data = {
                    'success': True,
                    'successful': self.successful_count,
                    'failed': self.failed_count,
                    'skipped': self.skipped_count,
                    'duplicates': len(duplicate_files),
                    'results': self.results,
                    'duplicate_files': duplicate_files
                }
                
                # Export HTML visualizer
                self.status_update.emit("Generating HTML visualizer...")
                html_file = self.export_html_visualizer(results_data)
                if html_file:
                    results_data['html_file'] = html_file
                
                self.recovery_finished.emit(results_data)
                
        except Exception as e:
            # Rollback on any error
            try:
                self.rollback_recovery()
            except Exception:
                pass
            self.recovery_finished.emit({
                'success': False,
                'error': f'Recovery failed: {str(e)}'
            })


class RecoveryProgressDialog(QDialog):
    """Progress dialog for model recovery"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recovering Models Data")
        self.setModal(True)
        self.setFixedSize(500, 200)
        self.worker = None
        self.final_results = None  # Store the final results from worker
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BACKGROUND_COLOR.name()};
                color: {TEXT_COLOR.name()};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Status label
        self.status_label = QLabel("Initializing recovery...")
        self.status_label.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Progress info
        self.progress_info = QLabel("0 / 0 files processed")
        layout.addWidget(self.progress_info)
        
        # Cancel button
        self.cancel_button = QPushButton("Cancel Recovery")
        self.cancel_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #8b0000;
                color: white;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #a00000;
            }}
        """)
        self.cancel_button.clicked.connect(self.cancel_recovery)
        layout.addWidget(self.cancel_button)
        
    def start_recovery(self, download_folder, db_manager, api_key, settings_manager=None):
        """Start the recovery process"""
        self.worker = RecoveryWorker(download_folder, db_manager, api_key, settings_manager)
        self.worker.status_update.connect(self.update_status)
        self.worker.progress_update.connect(self.update_progress)
        self.worker.recovery_finished.connect(self.recovery_finished)
        self.worker.start()
        
    def update_status(self, status):
        """Update status label"""
        self.status_label.setText(status)
        
    def update_progress(self, current, total):
        """Update progress bar"""
        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar.setValue(percentage)
            self.progress_info.setText(f"{current} / {total} files processed")
        
    def cancel_recovery(self):
        """Cancel the recovery process"""
        if self.worker:
            self.worker.cancel_recovery()
        self.reject()
        
    def recovery_finished(self, results):
        """Handle recovery completion"""
        self.final_results = results  # Store the results from worker
        self.accept()


class RecoveryResultsDialog(QDialog):
    """Dialog to show recovery results"""
    
    def __init__(self, results, worker=None, parent=None):
        super().__init__(parent)
        self.results = results
        self.worker = worker  # Keep reference to worker for rollback
        self.setWindowTitle("Model Recovery Results")
        self.setModal(True)
        self.resize(700, 500)
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BACKGROUND_COLOR.name()};
                color: {TEXT_COLOR.name()};
            }}
        """)
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # Header with icon and title
        header_layout = QHBoxLayout()
        
        # Icon
        icon_label = QLabel("🎯")
        icon_label.setFont(QFont("Segoe UI", 24))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFixedSize(60, 60)
        icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {PRIMARY_COLOR.name()};
                border-radius: 30px;
                color: white;
            }}
        """)
        header_layout.addWidget(icon_label)
        
        # Title and subtitle
        title_layout = QVBoxLayout()
        title_label = QLabel("Model Recovery Complete!")
        title_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title_label.setStyleSheet(f"color: {PRIMARY_COLOR.name()};")
        
        subtitle_label = QLabel("Recovery process has finished successfully")
        subtitle_label.setFont(QFont("Segoe UI", 11))
        subtitle_label.setStyleSheet("color: #888888;")
        
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)
        title_layout.addStretch()
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Statistics Cards Grid
        stats_frame = QFrame()
        stats_frame.setFrameStyle(QFrame.Box)
        stats_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 16px;
            }}
        """)
        
        stats_layout = QVBoxLayout(stats_frame)
        stats_title = QLabel("📊 Recovery Statistics")
        stats_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        stats_title.setStyleSheet(f"color: {PRIMARY_COLOR.name()}; margin-bottom: 10px;")
        stats_layout.addWidget(stats_title)
        
        # Statistics grid
        stats_grid_layout = QHBoxLayout()
        
        # Create stat cards
        stat_cards = [
            ("✅", "Successfully Recovered", self.results.get('successful', 0), "#4caf50"),
            ("❌", "Failed Recovery", self.results.get('failed', 0), "#f44336"),
            ("⚠️", "Already Registered", self.results.get('skipped', 0), "#ff9800"),
            ("📁", "Duplicates Found", self.results.get('duplicates', 0), "#9c27b0")
        ]
        
        for icon, label, count, color in stat_cards:
            card = self.create_stat_card(icon, label, count, color)
            stats_grid_layout.addWidget(card)
        
        stats_layout.addLayout(stats_grid_layout)
        layout.addWidget(stats_frame)
        
        # Key Actions Section
        actions_frame = QFrame()
        actions_frame.setFrameStyle(QFrame.Box)
        actions_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 16px;
            }}
        """)
        
        actions_layout = QVBoxLayout(actions_frame)
        actions_title = QLabel("🚀 Next Steps")
        actions_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        actions_title.setStyleSheet(f"color: {PRIMARY_COLOR.name()}; margin-bottom: 10px;")
        actions_layout.addWidget(actions_title)
        
        # Action buttons grid
        actions_grid = QVBoxLayout()
        
        # HTML Visualizer action (most prominent)
        if self.results.get('html_file'):
            html_action = self.create_action_item(
                "📊", 
                "Interactive Results Visualizer", 
                "View detailed recovery results in an interactive table with filtering and export options",
                "Open HTML Visualizer",
                self.open_html_visualizer,
                "#4caf50"
            )
            actions_grid.addWidget(html_action)
        
        # Downloaded Explorer action
        if self.results.get('successful', 0) > 0:
            explorer_action = self.create_action_item(
                "📚",
                "View in Downloaded Explorer",
                "Browse your recovered models with full metadata and preview images",
                "Open Downloaded Explorer",
                self.open_downloaded_explorer,
                "#2196f3"
            )
            actions_grid.addWidget(explorer_action)
        
        actions_layout.addLayout(actions_grid)
        layout.addWidget(actions_frame)
        
        # Footer with buttons
        footer_layout = QHBoxLayout()
        
        # Rollback button (only show if recovery was successful and worker available)
        if self.results.get('success') and self.worker and self.results.get('successful', 0) > 0:
            rollback_button = QPushButton("🔄 Rollback Changes (Test)")
            rollback_button.setStyleSheet("""
                QPushButton {
                    background-color: #8b0000;
                    color: white;
                    padding: 12px 20px;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #a00000;
                }
            """)
            rollback_button.clicked.connect(self.rollback_changes)
            footer_layout.addWidget(rollback_button)
        
        footer_layout.addStretch()
        
        # Close button
        close_button = QPushButton("✖️ Close")
        close_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {PRIMARY_COLOR.name()};
                color: white;
                padding: 12px 24px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: #9575cd;
            }}
        """)
        close_button.clicked.connect(self.accept)
        footer_layout.addWidget(close_button)
        
        layout.addLayout(footer_layout)
    
    def create_stat_card(self, icon, label, count, color):
        """Create a statistics card widget"""
        card = QFrame()
        card.setFrameStyle(QFrame.Box)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #333333;
                border: 1px solid {color};
                border-radius: 6px;
                padding: 12px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignCenter)
        
        # Icon
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Segoe UI", 20))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(f"color: {color};")
        layout.addWidget(icon_label)
        
        # Count
        count_label = QLabel(str(count))
        count_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        count_label.setAlignment(Qt.AlignCenter)
        count_label.setStyleSheet("color: white;")
        layout.addWidget(count_label)
        
        # Label
        text_label = QLabel(label)
        text_label.setFont(QFont("Segoe UI", 9))
        text_label.setAlignment(Qt.AlignCenter)
        text_label.setWordWrap(True)
        text_label.setStyleSheet("color: #cccccc;")
        layout.addWidget(text_label)
        
        return card
    
    def create_action_item(self, icon, title, description, button_text, callback, color):
        """Create an action item widget"""
        item = QFrame()
        item.setFrameStyle(QFrame.Box)
        item.setStyleSheet("""
            QFrame {
                background-color: #333333;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 16px;
            }
            QFrame:hover {
                border-color: #777777;
                background-color: #363636;
            }
        """)
        
        layout = QHBoxLayout(item)
        
        # Icon
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Segoe UI", 24))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFixedSize(48, 48)
        icon_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                background-color: rgba(128, 128, 128, 0.1);
                border-radius: 24px;
            }}
        """)
        layout.addWidget(icon_label)
        
        # Content
        content_layout = QVBoxLayout()
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title_label.setStyleSheet("color: white;")
        content_layout.addWidget(title_label)
        
        desc_label = QLabel(description)
        desc_label.setFont(QFont("Segoe UI", 10))
        desc_label.setStyleSheet("color: #aaaaaa;")
        desc_label.setWordWrap(True)
        content_layout.addWidget(desc_label)
        
        layout.addLayout(content_layout)
        
        # Button
        action_button = QPushButton(button_text)
        action_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
                min-width: 120px;
            }}
            QPushButton:hover {{
                background-color: #66bb6a;
            }}
        """)
        action_button.clicked.connect(callback)
        layout.addWidget(action_button)
        
        return item
    
    def open_downloaded_explorer(self):
        """Open the Downloaded Explorer to view recovered models"""
        try:
            # Get reference to main window
            main_window = self.parent()
            if main_window and hasattr(main_window, 'show_downloaded_explorer'):
                self.accept()  # Close the dialog first
                main_window.show_downloaded_explorer()
            else:
                QMessageBox.information(
                    self,
                    "Downloaded Explorer",
                    "Please navigate to the Downloaded Explorer manually to view your recovered models."
                )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Could not open Downloaded Explorer",
                f"Failed to open Downloaded Explorer: {str(e)}"
            )
        
    def rollback_changes(self):
        """Rollback the recovery changes"""
        if not self.worker:
            return
            
        reply = QMessageBox.question(
            self,
            "Rollback Recovery",
            f"Are you sure you want to rollback all {self.results.get('successful', 0)} recovered models?\n\n"
            "This will remove all metadata and images that were added during this recovery session.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.worker.rollback_recovery():
                QMessageBox.information(
                    self,
                    "Rollback Complete",
                    "All recovery changes have been successfully rolled back.\n\n"
                    "The database has been restored to its state before the recovery."
                )
                # Update the dialog title to indicate rollback
                self.setWindowTitle("Model Recovery Results (ROLLED BACK)")
                
                # Disable rollback button
                for button in self.findChildren(QPushButton):
                    if button.text() == "Rollback Changes (Test)":
                        button.setEnabled(False)
                        button.setText("Changes Rolled Back")
                        break
                        
            else:
                QMessageBox.critical(
                    self,
                    "Rollback Failed",
                    "Failed to rollback recovery changes.\n\n"
                    "The database may be in an inconsistent state."
                )
    
    def open_html_visualizer(self):
        """Open the HTML visualizer in the default web browser"""
        html_file = self.results.get('html_file')
        if html_file and os.path.exists(html_file):
            try:
                webbrowser.open(f'file:///{html_file.replace(os.sep, "/")}')
                QMessageBox.information(
                    self,
                    "HTML Visualizer Opened",
                    f"The interactive recovery results visualizer has been opened in your default web browser.\n\n"
                    f"File location: {html_file}\n\n"
                    f"💡 Tip: You can bookmark this page or save the file for future reference."
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Failed to Open Visualizer",
                    f"Could not open the HTML visualizer:\n{str(e)}\n\n"
                    f"You can manually open the file:\n{html_file}"
                )
        else:
            QMessageBox.warning(
                self,
                "Visualizer Not Available",
                "The HTML visualizer file is not available or was not generated successfully."
            )


class ModelRecoveryManager:
    """Manager for model recovery functionality"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        
    def start_recovery(self):
        """Start the model recovery process"""
        main = self.main_window
        
        # Get download folder from settings
        download_folder = main.settings_manager.get('download_dir')
        if not download_folder or not os.path.exists(download_folder):
            QMessageBox.warning(
                main,
                "Invalid Download Folder",
                "Please configure a valid download folder in settings before attempting recovery."
            )
            return
            
        # Get API key
        api_key = main.settings_manager.get('api_key')
        if not api_key:
            reply = QMessageBox.question(
                main,
                "No API Key",
                "No CivitAI API key found. Recovery may have limited functionality.\n\nDo you want to continue anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        
        # Show progress dialog and start recovery
        progress_dialog = RecoveryProgressDialog(main)
        progress_dialog.start_recovery(download_folder, main.db_manager, api_key, main.settings_manager)
        
        if progress_dialog.exec_() == QDialog.Accepted:
            # Recovery completed, get results from worker
            if progress_dialog.final_results:
                # Use the actual results from the worker (includes html_file)
                final_results = progress_dialog.final_results
                
                # Show results dialog with worker reference for rollback
                results_dialog = RecoveryResultsDialog(final_results, progress_dialog.worker, main)
                results_dialog.exec_()
                
                # Refresh downloaded models view if any were recovered
                if final_results.get('successful', 0) > 0:
                    try:
                        # Clear cached downloaded models to force refresh
                        if hasattr(main, '_left_agg_downloaded'):
                            delattr(main, '_left_agg_downloaded')
                            
                        # Refresh if currently viewing downloaded models
                        if getattr(main, 'current_left_view', None) == 'downloaded':
                            main.downloaded_manager.load_downloaded_models_left()
                            
                        main.status_bar.showMessage(
                            f"Recovery complete: {final_results.get('successful', 0)} models recovered", 
                            5000
                        )
                    except Exception as e:
                        print(f"Error refreshing downloaded models: {e}")
        else:
            # Recovery was cancelled
            main.status_bar.showMessage("Model recovery cancelled", 3000)
