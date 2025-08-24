#!/usr/bin/env python3
"""
Complete Data Wipe Script for CivitAI Download Manager

This script performs a complete reset of the application by:
1. Clearing all database tables and data
2. Removing Windows registry entries
3. Deleting configuration files
4. Removing all downloaded images
5. Clearing log files and history

IMPORTANT: This will NOT delete downloaded model files (.safetensors, .ckpt, etc.)
Only metadata, configurations, and preview images will be removed.

Usage: python complete_wipe.py
"""

import os
import sys
import sqlite3
import shutil
import winreg
import json
from pathlib import Path

class CompleteWiper:
    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.civitai_dir = self.script_dir / "civitai-manager"
        self.images_dir = self.script_dir / "images"
        self.config_file = self.script_dir / "config.json"
        self.history_file = self.script_dir / "history-bk.json"
        self.log_file = self.script_dir / "refresh_logs.log"
        
        # Database files
        self.db_files = [
            self.script_dir / "civitai_manager.db",
            self.script_dir / "civitai_manager.db-shm", 
            self.script_dir / "civitai_manager.db-wal",
            self.civitai_dir / "civitai_manager.db",
            self.civitai_dir / "civitai_manager.db-shm",
            self.civitai_dir / "civitai_manager.db-wal"
        ]
        
        # Registry path for QSettings
        self.registry_path = r"HKEY_CURRENT_USER\Software\CivitaiManager\DownloadManager"
        
    def confirm_wipe(self):
        """Ask user for confirmation before proceeding."""
        print("=" * 60)
        print("CivitAI Download Manager - COMPLETE DATA WIPE")
        print("=" * 60)
        print("\nThis will permanently delete:")
        print("✗ All database records and metadata")
        print("✗ All configuration settings")
        print("✗ All Windows registry entries")
        print("✗ All downloaded preview images")
        print("✗ All download history and logs")
        print("\nThis will NOT delete:")
        print("✓ Downloaded model files (.safetensors, .ckpt, .pt, etc.)")
        print("✓ Model directories (only preview images inside them)")
        
        print("\n" + "!" * 60)
        print("WARNING: This action cannot be undone!")
        print("!" * 60)
        
        response = input("\nType 'WIPE' (in capitals) to confirm: ").strip()
        return response == "WIPE"
    
    def clear_databases(self):
        """Remove all database files."""
        print("\n[1/6] Clearing databases...")
        
        for db_file in self.db_files:
            try:
                if db_file.exists():
                    # Try to close any open connections first
                    try:
                        conn = sqlite3.connect(str(db_file))
                        conn.close()
                    except:
                        pass
                    
                    db_file.unlink()
                    print(f"  ✓ Deleted: {db_file.name}")
                else:
                    print(f"  - Not found: {db_file.name}")
            except Exception as e:
                print(f"  ✗ Error deleting {db_file.name}: {e}")
    
    def clear_registry(self):
        """Remove Windows registry entries for the application."""
        print("\n[2/6] Clearing Windows registry...")
        
        try:
            # Try to delete the entire CivitaiManager key
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software") as software_key:
                try:
                    winreg.DeleteKeyEx(software_key, r"CivitaiManager\DownloadManager")
                    print("  ✓ Deleted: DownloadManager registry key")
                except FileNotFoundError:
                    print("  - Registry key not found (already clean)")
                except Exception as e:
                    print(f"  ✗ Error deleting DownloadManager key: {e}")
                
                try:
                    winreg.DeleteKey(software_key, "CivitaiManager")
                    print("  ✓ Deleted: CivitaiManager parent key")
                except FileNotFoundError:
                    print("  - Parent registry key not found")
                except Exception as e:
                    print(f"  - Parent key may have subkeys: {e}")
                    
        except Exception as e:
            print(f"  ✗ Error accessing registry: {e}")
    
    def clear_config_files(self):
        """Remove configuration and history files."""
        print("\n[3/6] Clearing configuration files...")
        
        config_files = [self.config_file, self.history_file, self.log_file]
        
        for config_file in config_files:
            try:
                if config_file.exists():
                    config_file.unlink()
                    print(f"  ✓ Deleted: {config_file.name}")
                else:
                    print(f"  - Not found: {config_file.name}")
            except Exception as e:
                print(f"  ✗ Error deleting {config_file.name}: {e}")
    
    def clear_images(self):
        """Remove all downloaded preview images while preserving model files."""
        print("\n[4/6] Clearing preview images...")
        
        if not self.images_dir.exists():
            print("  - Images directory not found")
            return
        
        total_deleted = 0
        models_processed = 0
        
        # Image extensions to delete
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
        
        try:
            for model_dir in self.images_dir.iterdir():
                if model_dir.is_dir():
                    models_processed += 1
                    deleted_count = 0
                    
                    # Delete only image files, keep model files
                    for file_path in model_dir.iterdir():
                        if file_path.is_file():
                            if file_path.suffix.lower() in image_extensions:
                                try:
                                    file_path.unlink()
                                    deleted_count += 1
                                    total_deleted += 1
                                except Exception as e:
                                    print(f"    ✗ Error deleting {file_path.name}: {e}")
                    
                    if deleted_count > 0:
                        print(f"  ✓ {model_dir.name}: {deleted_count} images deleted")
                    
                    # Remove directory if it's now empty (no model files)
                    try:
                        remaining_files = list(model_dir.iterdir())
                        if not remaining_files:
                            model_dir.rmdir()
                            print(f"  ✓ Removed empty directory: {model_dir.name}")
                    except:
                        pass  # Directory not empty (has model files)
                        
        except Exception as e:
            print(f"  ✗ Error processing images directory: {e}")
        
        print(f"  ✓ Total: {total_deleted} images deleted from {models_processed} model directories")
    
    def clear_cache_files(self):
        """Remove Python cache files."""
        print("\n[5/6] Clearing cache files...")
        
        cache_dirs = [
            self.script_dir / "__pycache__",
            self.civitai_dir / "__pycache__",
            self.civitai_dir / "window_parts" / "__pycache__"
        ]
        
        total_deleted = 0
        
        for cache_dir in cache_dirs:
            if cache_dir.exists():
                try:
                    file_count = len(list(cache_dir.glob("*.pyc")))
                    shutil.rmtree(cache_dir)
                    total_deleted += file_count
                    print(f"  ✓ Deleted: {cache_dir.relative_to(self.script_dir)} ({file_count} files)")
                except Exception as e:
                    print(f"  ✗ Error deleting {cache_dir.name}: {e}")
            else:
                print(f"  - Not found: {cache_dir.relative_to(self.script_dir)}")
        
        print(f"  ✓ Total: {total_deleted} cache files deleted")
    
    def reset_complete(self):
        """Display completion message."""
        print("\n[6/6] Reset complete!")
        print("\n" + "=" * 60)
        print("✓ COMPLETE DATA WIPE FINISHED")
        print("=" * 60)
        print("\nAll application data has been cleared.")
        print("The application will start fresh on next launch.")
        print("\nNote: Downloaded model files have been preserved.")
        print("\nYou can now:")
        print("- Run the application to start with clean settings")
        print("- Reconfigure your API key and preferences")
        print("- Re-download metadata for existing models if needed")
    
    def wipe_all(self):
        """Perform the complete wipe operation."""
        if not self.confirm_wipe():
            print("\nOperation cancelled.")
            return False
        
        print("\nStarting complete data wipe...")
        
        try:
            self.clear_databases()
            self.clear_registry()
            self.clear_config_files()
            self.clear_images()
            self.clear_cache_files()
            self.reset_complete()
            return True
            
        except KeyboardInterrupt:
            print("\n\nOperation interrupted by user.")
            return False
        except Exception as e:
            print(f"\n\nUnexpected error during wipe: {e}")
            return False

def main():
    """Main entry point."""
    try:
        wiper = CompleteWiper()
        success = wiper.wipe_all()
        
        if success:
            input("\nPress Enter to exit...")
            sys.exit(0)
        else:
            input("\nPress Enter to exit...")
            sys.exit(1)
            
    except Exception as e:
        print(f"Fatal error: {e}")
        input("\nPress Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()
