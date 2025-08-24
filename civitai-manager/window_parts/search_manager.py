# search_manager.py - Search and navigation functionality
import json
from typing import Dict, List, Any, Optional
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QTimer
from ui_components import ModelCard
from window_parts.model_utils import ModelDataUtils


class SearchManager:
    """Manages search functionality and model loading."""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.utils = ModelDataUtils()
    
    def search_models(self):
        """Trigger model search with current filters."""
        main = self.main_window
        if not main.api_key:
            QMessageBox.warning(
                main,
                "API Key Required",
                "Please set your Civitai API key in settings before searching.",
                QMessageBox.Ok
            )
            return
        
        # Reset pagination when search parameters change
        main.model_page = 0
        main.model_has_more = True
        main.search_cursor = None
        
        # Clear existing cards
        main.clear_model_grid()
        
        # Start search
        main.load_models()
    
    def load_models(self):
        """Load models from API with current search parameters."""
        main = self.main_window
        if not main.api_key or not main.model_has_more:
            return
        
        # Prevent multiple simultaneous requests
        if hasattr(main, '_loading_models') and main._loading_models:
            return
        main._loading_models = True
        
        try:
            # Get search parameters
            query = main.search_input.text().strip()
            model_type = main.model_type_combo.currentText()
            base_model = main.base_model_combo.currentText()
            sort = main.sort_combo.currentText()
            period = main.period_combo.currentText()
            
            # Get NSFW setting
            nsfw = False
            try:
                nsfw = main.nsfw_checkbox.isChecked()
            except Exception:
                pass
            
            # Map UI values to API parameters
            type_mapping = {
                "All": None,
                "Checkpoint": "Checkpoint",
                "LORA": "LORA", 
                "TextualInversion": "TextualInversion",
                "Hypernetwork": "Hypernetwork",
                "AestheticGradient": "AestheticGradient",
                "Controlnet": "Controlnet",
                "Poses": "Poses"
            }
            
            sort_mapping = {
                "Most Downloaded": "Most Downloaded",
                "Most Liked": "Most Liked", 
                "Newest": "Newest",
                "Most Discussed": "Most Discussed"
            }
            
            period_mapping = {
                "AllTime": "AllTime",
                "Year": "Year",
                "Month": "Month", 
                "Week": "Week",
                "Day": "Day"
            }
            
            base_model_mapping = {
                "All": None,
                "SD 1.4": "SD 1.4",
                "SD 1.5": "SD 1.5",
                "SD 2.0": "SD 2.0", 
                "SD 2.1": "SD 2.1",
                "SDXL 1.0": "SDXL 1.0",
                "SDXL Turbo": "SDXL Turbo"
            }
            
            # Build API parameters
            params = {
                'limit': 20,
                'page': main.model_page + 1,
                'sort': sort_mapping.get(sort, "Most Downloaded"),
                'period': period_mapping.get(period, "AllTime"),
                'nsfw': nsfw
            }
            
            if query:
                params['query'] = query
            if type_mapping.get(model_type):
                params['types'] = [type_mapping[model_type]]
            if base_model_mapping.get(base_model):
                params['baseModels'] = [base_model_mapping[base_model]]
            
            # Make API request
            response = main.api.search_models(**params)
            
            if response and 'items' in response:
                models = response['items']
                
                # Filter by base model if needed (client-side fallback)
                if base_model != "All":
                    models = [m for m in models if self.utils.matches_base_model(m, base_model)]
                
                # Add model cards
                self._add_model_cards(models)
                
                # Update pagination
                main.model_page += 1
                main.model_has_more = len(models) >= 20
                
                # Update metadata info
                try:
                    metadata = response.get('metadata', {})
                    total = metadata.get('totalItems', 0)
                    current_count = len(main.model_cards)
                    main.status_bar.showMessage(f"Loaded {current_count} models (Total: {total})")
                except Exception:
                    main.status_bar.showMessage(f"Loaded {len(main.model_cards)} models")
            else:
                main.model_has_more = False
                main.status_bar.showMessage("No more models found")
                
        except Exception as e:
            print(f"Error loading models: {e}")
            main.status_bar.showMessage(f"Error loading models: {e}")
            main.model_has_more = False
        finally:
            main._loading_models = False
    
    def _add_model_cards(self, models: List[Dict[str, Any]]):
        """Add model cards to the grid."""
        main = self.main_window
        
        for model in models:
            try:
                card = ModelCard(model)
                card.clicked.connect(main.show_model_details)
                
                # Set card image
                img_url = self.utils.extract_image_url(model)
                if img_url:
                    try:
                        from ui_helpers import ImageLoaderThread
                        headers = main.api.headers if hasattr(main, 'api') else None
                        thread = ImageLoaderThread(img_url, card, headers=headers)
                        thread.image_loaded.connect(card.set_image)
                        thread.start()
                        main.image_loader_threads.append(thread)
                    except Exception:
                        pass
                
                main.model_cards.append(card)
            except Exception as e:
                print(f"Error creating model card: {e}")
        
        # Relayout grid
        main.relayout_model_cards()
    
    def load_more_models_if_needed(self):
        """Load more models if scrolled near bottom."""
        main = self.main_window
        try:
            scroll_area = main.left_scroll_area
            scrollbar = scroll_area.verticalScrollBar()
            
            # Check if near bottom (within 100px)
            if (scrollbar.value() >= scrollbar.maximum() - 100 and 
                main.model_has_more and 
                getattr(main, 'current_left_view', 'search') == 'search'):
                
                self.load_models()
        except Exception:
            pass
    
    def clear_model_grid(self):
        """Clear all model cards from grid."""
        main = self.main_window
        try:
            # Stop image loading threads
            for thread in getattr(main, 'image_loader_threads', []):
                try:
                    thread.terminate()
                except Exception:
                    pass
            main.image_loader_threads = []
            
            # Remove widgets from grid
            while main.model_grid_layout.count():
                child = main.model_grid_layout.takeAt(0)
                if child and child.widget():
                    child.widget().setParent(None)
            
            # Clear card list
            main.model_cards = []
        except Exception as e:
            print(f"Error clearing model grid: {e}")
    
    def relayout_model_cards(self):
        """Arrange model cards in grid layout."""
        main = self.main_window
        try:
            columns = 4  # Fixed number of columns
            for i, card in enumerate(main.model_cards):
                row = i // columns
                col = i % columns
                main.model_grid_layout.addWidget(card, row, col)
        except Exception as e:
            print(f"Error relaying model cards: {e}")
