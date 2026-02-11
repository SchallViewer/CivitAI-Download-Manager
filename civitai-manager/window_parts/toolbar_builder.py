# toolbar_builder.py
import os
from PyQt5.QtWidgets import QToolBar, QAction
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QSize
from constants import PRIMARY_COLOR, BACKGROUND_COLOR


class ToolbarBuilder:
    def __init__(self, host):
        self.host = host

    def build(self):
        host = self.host
        toolbar = QToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setStyleSheet(
            f"""
            QToolBar {{
                background-color: {BACKGROUND_COLOR.name()};
                border-bottom: 1px solid {PRIMARY_COLOR.name()};
                padding: 5px;
            }}
            """
        )
        host.addToolBar(toolbar)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        icons_dir = os.path.join(os.path.dirname(script_dir), "icons")

        host.search_action = QAction(QIcon(os.path.join(icons_dir, "search.png")), "Search", host)
        host.downloads_action = QAction(QIcon(os.path.join(icons_dir, "downloads.png")), "Downloads", host)
        host.history_action = QAction(QIcon(os.path.join(icons_dir, "history.png")), "History", host)
        host.settings_action = QAction(QIcon(os.path.join(icons_dir, "setting.png")), "Settings", host)
        host.downloaded_explorer_action = QAction(
            QIcon(os.path.join(icons_dir, "donwloads_explorer.png")),
            "Downloaded Explorer",
            host,
        )
        host.downloaded_explorer_action.setToolTip("Switch to Downloaded Model Explorer")

        toolbar.addAction(host.search_action)
        toolbar.addAction(host.downloads_action)
        toolbar.addAction(host.downloaded_explorer_action)
        toolbar.addAction(host.history_action)
        toolbar.addSeparator()
        toolbar.addAction(host.settings_action)

        return toolbar
