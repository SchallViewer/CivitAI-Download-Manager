# layout_mixin.py
from PyQt5.QtWidgets import QMainWindow


class LayoutMixin:
    def compute_columns(self):
        try:
            viewport = self.scroll_area.viewport()
            available_width = (
                viewport.width()
                - self.model_grid_layout.contentsMargins().left()
                - self.model_grid_layout.contentsMargins().right()
            )
            card_total = 240 + self.model_grid_layout.horizontalSpacing()
            if card_total <= 0:
                return 3
            cols = max(3, max(1, available_width // card_total))
            return int(cols)
        except Exception:
            return 3

    def relayout_model_cards(self):
        try:
            self.search_manager.relayout_model_cards()
        except Exception as e:
            print(f"Error relaying model cards: {e}")

    def resizeEvent(self, event):
        try:
            if getattr(self, '_enforcing_splitter', False):
                QMainWindow.resizeEvent(self, event)
                return
            if hasattr(self, 'splitter') and hasattr(self, 'right_panel'):
                fixed_width = self.right_panel.maximumWidth()
                if fixed_width > 0:
                    total = self.splitter.size().width()
                    left_width = max(self.model_list_container.minimumWidth(), total - fixed_width)
                    self._enforcing_splitter = True
                    self.splitter.setSizes([left_width, fixed_width])
                    self._enforcing_splitter = False
        except Exception:
            self._enforcing_splitter = False
        QMainWindow.resizeEvent(self, event)
