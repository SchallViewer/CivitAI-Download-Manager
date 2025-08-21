import sys
from PyQt5.QtWidgets import QApplication
from main_window import MainWindow

def main():
    # Create application
    app = QApplication(sys.argv)
    
    # Apply dark theme
    app.setStyle("Fusion")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Run application
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()