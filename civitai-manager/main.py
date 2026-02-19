import sys
from PyQt5.QtWidgets import QApplication, QMessageBox
from main_window import MainWindow
from settings import SettingsManager, ConfigValidationError
from compatibility_manager import CompatibilityManager

def main():
    # Create application
    app = QApplication(sys.argv)
    
    # Apply dark theme
    app.setStyle("Fusion")
    
    # Validate configuration before initializing main window
    try:
        settings_manager = SettingsManager(validate_on_init=True)
        compatibility_manager = CompatibilityManager(settings_manager)
        compatibility_manager.run_all()
        settings_manager.validate_config_integrity(raise_on_error=True)
    except ConfigValidationError as e:
        QMessageBox.critical(
            None,
            "Configuration Error",
            "Error loading config file.\n\n"
            f"{str(e)}\n\n"
            "Fix config.json and restart the application."
        )
        sys.exit(1)

    # Create and show main window
    window = MainWindow(settings_manager=settings_manager)
    window.show()
    
    # Run application
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()