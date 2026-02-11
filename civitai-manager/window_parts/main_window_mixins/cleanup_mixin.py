# cleanup_mixin.py


class CleanupMixin:
    def closeEvent(self, event):
        print("DEBUG: closeEvent called - starting cleanup")
        try:
            if hasattr(self, 'download_filter_timer'):
                print("DEBUG: Stopping download_filter_timer")
                self.download_filter_timer.stop()
            if hasattr(self, 'progressive_render_timer'):
                print("DEBUG: Stopping progressive_render_timer")
                self.progressive_render_timer.stop()
            if hasattr(self, 'search_timer'):
                print("DEBUG: Stopping search_timer")
                self.search_timer.stop()

            if hasattr(self, 'download_manager'):
                print("DEBUG: Canceling active downloads")
                try:
                    for download in self.download_manager.get_active_downloads():
                        if hasattr(download, 'file_name'):
                            self.download_manager.cancel_download(download.file_name)

                    if hasattr(self.download_manager, 'thread_pool'):
                        self.download_manager.thread_pool.clear()
                except Exception as e:
                    print(f"DEBUG: Error canceling downloads: {e}")

            if hasattr(self, 'db_manager') and hasattr(self.db_manager, 'conn'):
                print("DEBUG: Closing database connection")
                self.db_manager.conn.close()

            if hasattr(self, 'tray_icon'):
                print("DEBUG: Hiding system tray icon")
                self.tray_icon.hide()
            elif hasattr(self, 'tray'):
                print("DEBUG: Hiding system tray icon")
                self.tray.hide()

        except Exception as e:
            print(f"Error during cleanup: {e}")
        finally:
            print("DEBUG: closeEvent completed - accepting event")
            event.accept()
