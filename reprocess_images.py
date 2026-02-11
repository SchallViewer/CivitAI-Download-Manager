#!/usr/bin/env python3
"""
Image Reprocessing Script for CivitAI Download Manager
Reprocesses all downloaded images with the reduced pixel area cap to save disk space.
"""

import os
import math
import time
import shutil
from pathlib import Path
from typing import List, Tuple, Optional
from PyQt5.QtGui import QImage
from PyQt5.QtCore import Qt

try:
    from PIL import Image as PILImage, ImageOps as PILImageOps
    PILLOW_AVAILABLE = True
except ImportError:
    PILImage = None
    PILLOW_AVAILABLE = False

# Configuration
MAX_IMAGE_AREA = 120_000  # Match your reduced pixel area cap
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
BACKUP_ORIGINAL = True  # Set to False if you don't want to keep backups
DRY_RUN = False  # Set to True to see what would be processed without making changes

# Paths
IMAGES_DIR = r"c:\Users\User\Desktop\Python Scripts\Python ComfyUI Selector\images"
BACKUP_DIR = r"c:\Users\User\Desktop\Python Scripts\Python ComfyUI Selector\image_backups"

def format_bytes(bytes_size: int) -> str:
    """Format bytes into human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"

def get_image_dimensions(file_path: Path) -> Optional[Tuple[int, int]]:
    """Get image dimensions without loading full image."""
    try:
        if PILLOW_AVAILABLE:
            with PILImage.open(file_path) as img:
                return img.size
        else:
            # Fallback to QImage
            qimg = QImage(str(file_path))
            if not qimg.isNull():
                return qimg.width(), qimg.height()
    except Exception as e:
        print(f"Error getting dimensions for {file_path}: {e}")
    return None

def _process_and_write_image_bytes(content: bytes, dest_path: str, ext: str) -> None:
    """
    Resize if larger than MAX_IMAGE_AREA and strip metadata, saving back to dest_path.
    This is the same function from your download_manager.py
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

def process_image(file_path: Path) -> Tuple[bool, Optional[int], Optional[int]]:
    """
    Process a single image file.
    Returns: (was_processed, old_size, new_size)
    """
    try:
        # Get original dimensions and file size
        dimensions = get_image_dimensions(file_path)
        if not dimensions:
            return False, None, None
        
        width, height = dimensions
        pixel_area = width * height
        
        # Skip if already within the limit
        if pixel_area <= MAX_IMAGE_AREA:
            return False, None, None
            
        original_size = file_path.stat().st_size
        
        if DRY_RUN:
            print(f"[DRY RUN] Would resize: {file_path.name} ({width}x{height} = {pixel_area:,} pixels)")
            return True, original_size, None
        
        # Create backup if enabled
        if BACKUP_ORIGINAL:
            backup_path = Path(BACKUP_DIR) / file_path.parent.name / file_path.name
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            if not backup_path.exists():  # Don't overwrite existing backups
                shutil.copy2(file_path, backup_path)
        
        # Read the image file
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Process and rewrite the image
        _process_and_write_image_bytes(content, str(file_path), file_path.suffix)
        
        new_size = file_path.stat().st_size
        return True, original_size, new_size
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False, None, None

def find_image_files(root_dir: Path) -> List[Path]:
    """Find all image files in the directory tree."""
    image_files = []
    
    for item in root_dir.iterdir():
        if item.is_file():
            if item.suffix.lower() in SUPPORTED_EXTENSIONS:
                image_files.append(item)
        elif item.is_dir() and item.name != "images goes here":
            # Recursively search subdirectories
            image_files.extend(find_image_files(item))
    
    return image_files

def main():
    """Main execution function."""
    print("CivitAI Image Reprocessing Script")
    print("=" * 50)
    print(f"Target pixel area cap: {MAX_IMAGE_AREA:,} pixels")
    print(f"Images directory: {IMAGES_DIR}")
    print(f"Backup enabled: {BACKUP_ORIGINAL}")
    print(f"Dry run mode: {DRY_RUN}")
    print(f"Pillow available: {PILLOW_AVAILABLE}")
    print()
    
    # Check if images directory exists
    images_path = Path(IMAGES_DIR)
    if not images_path.exists():
        print(f"Error: Images directory not found: {IMAGES_DIR}")
        return
    
    # Find all image files
    print("Scanning for image files...")
    image_files = find_image_files(images_path)
    print(f"Found {len(image_files)} image files")
    
    if not image_files:
        print("No image files found to process.")
        return
    
    # Process statistics
    processed_count = 0
    skipped_count = 0
    error_count = 0
    total_space_saved = 0
    
    print("\nProcessing images...")
    print("-" * 50)
    
    start_time = time.time()
    
    for i, file_path in enumerate(image_files, 1):
        print(f"[{i}/{len(image_files)}] Processing: {file_path.parent.name}/{file_path.name}")
        
        was_processed, old_size, new_size = process_image(file_path)
        
        if was_processed:
            processed_count += 1
            if old_size and new_size:
                space_saved = old_size - new_size
                total_space_saved += space_saved
                print(f"  ✓ Resized: {format_bytes(old_size)} → {format_bytes(new_size)} "
                      f"(saved {format_bytes(space_saved)})")
            elif DRY_RUN:
                print(f"  ✓ Would be resized")
        else:
            skipped_count += 1
            if old_size is None:
                error_count += 1
                print(f"  ✗ Error reading image")
            else:
                print(f"  - Already within size limit")
    
    elapsed_time = time.time() - start_time
    
    # Print summary
    print("\n" + "=" * 50)
    print("PROCESSING SUMMARY")
    print("=" * 50)
    print(f"Total files scanned: {len(image_files)}")
    print(f"Files processed: {processed_count}")
    print(f"Files skipped (already optimal): {skipped_count - error_count}")
    print(f"Files with errors: {error_count}")
    print(f"Total space saved: {format_bytes(total_space_saved)}")
    print(f"Processing time: {elapsed_time:.1f} seconds")
    
    if BACKUP_ORIGINAL and processed_count > 0 and not DRY_RUN:
        print(f"Backups saved to: {BACKUP_DIR}")
    
    if DRY_RUN:
        print("\nThis was a dry run - no files were modified.")
        print("Set DRY_RUN = False to actually process the images.")

if __name__ == "__main__":
    # Confirm before running
    if not DRY_RUN:
        print("WARNING: This will modify your image files!")
        if BACKUP_ORIGINAL:
            print("Backups will be created, but please ensure you have additional backups if needed.")
        else:
            print("NO BACKUPS will be created - original files will be overwritten!")
        
        response = input("\nDo you want to continue? (y/N): ").strip().lower()
        if response != 'y':
            print("Operation cancelled.")
            exit()
    
    main()
