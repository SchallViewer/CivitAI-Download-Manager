# search_manager.py - Search and navigation functionality
import json
from typing import Dict, List, Any, Optional
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QObject
from ui_components import ModelCard
from window_parts.model_utils import ModelDataUtils


class SearchWorker(QThread):
    """Background thread worker for API calls."""
    
    # Signals
    search_completed = pyqtSignal(list, dict)  # models, metadata
    search_error = pyqtSignal(str)  # error message
    
    def __init__(self, api, params):
        super().__init__()
        self.api = api
        self.params = params
        
    def run(self):
        """Execute the API call in background thread."""
        try:
            print(f"SearchWorker: Making API call with params: {self.params}")
            response = self.api.search_models(**self.params)
            
            print(f"SearchWorker: API response type: {type(response)}")
            if response:
                print(f"SearchWorker: Response keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
                if 'items' in response:
                    items_count = len(response['items'])
                    print(f"SearchWorker: Found {items_count} items")
                    models = response['items']
                    metadata = response.get('metadata', {})
                    self.search_completed.emit(models, metadata)
                else:
                    print("SearchWorker: No 'items' key in response")
                    self.search_error.emit("No 'items' key in API response")
            else:
                print("SearchWorker: Empty or None response")
                self.search_error.emit("No results found")
                
        except Exception as e:
            print(f"SearchWorker: Exception occurred: {e}")
            self.search_error.emit(str(e))


class ProgressiveRenderer(QObject):
    """Renders model cards progressively to prevent UI freezing."""
    
    # Signals
    rendering_progress = pyqtSignal(int, int)  # current, total
    rendering_complete = pyqtSignal()
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.render_timer = QTimer()
        self.render_timer.timeout.connect(self._render_next_batch)
        self.pending_models = []
        self.render_index = 0
        self.batch_size = 3  # Render 3 cards at a time
        
    def start_rendering(self, models: List[Dict[str, Any]]):
        """Start progressive rendering of model cards."""
        print(f"ProgressiveRenderer: Starting to render {len(models)} models")
        self.pending_models = models.copy()
        self.render_index = 0
        
        if not self.pending_models:
            print("ProgressiveRenderer: No models to render, emitting complete")
            self.rendering_complete.emit()
            return
            
        # Start rendering with 50ms intervals
        print(f"ProgressiveRenderer: Starting timer with {len(self.pending_models)} models")
        self.render_timer.start(50)
        
    def _render_next_batch(self):
        """Render the next batch of model cards."""
        main = self.main_window
        utils = main.search_manager.utils
        
        # Calculate batch end
        batch_end = min(self.render_index + self.batch_size, len(self.pending_models))
        
        # Render batch
        for i in range(self.render_index, batch_end):
            model = self.pending_models[i]
            try:
                card = ModelCard(model)
                card.clicked.connect(main.show_model_details)
                
                # Set card image
                img_url = utils.extract_image_url(model)
                print(f"ProgressiveRenderer: Model {i}: img_url = {img_url}")
                
                if img_url:
                    try:
                        from ui_helpers import ImageLoaderThread
                        headers = main.api.headers if hasattr(main, 'api') else None
                        print(f"ProgressiveRenderer: Creating ImageLoaderThread for {img_url}")
                        
                        # Set expected URL on card for stale response handling
                        try:
                            setattr(card, '_expected_image_url', img_url)
                        except Exception:
                            pass
                            
                        thread = ImageLoaderThread(img_url, card, headers=headers)
                        thread.image_loaded.connect(main.set_card_image)  # Use main window's handler
                        thread.start()
                        main.image_loader_threads.append(thread)
                        print(f"ProgressiveRenderer: ImageLoaderThread started successfully")
                    except Exception as e:
                        print(f"ProgressiveRenderer: Error creating ImageLoaderThread: {e}")
                else:
                    print(f"ProgressiveRenderer: No image URL found for model {i}")
                
                main.model_cards.append(card)
                
            except Exception as e:
                print(f"Error creating model card: {e}")
        
        # Update layout for this batch
        self._update_layout_for_new_cards(batch_end - self.render_index)
        
        # Update progress
        self.render_index = batch_end
        self.rendering_progress.emit(self.render_index, len(self.pending_models))
        
        # Check if finished
        if self.render_index >= len(self.pending_models):
            self.render_timer.stop()
            self.rendering_complete.emit()
    
    def _update_layout_for_new_cards(self, new_card_count):
        """Update grid layout only for newly added cards."""
        main = self.main_window
        try:
            columns = 4  # Fixed number of columns
            total_cards = len(main.model_cards)
            
            # Only layout the new cards
            start_index = total_cards - new_card_count
            for i in range(start_index, total_cards):
                card = main.model_cards[i]
                row = i // columns
                col = i % columns
                main.model_grid_layout.addWidget(card, row, col)
                
        except Exception as e:
            print(f"Error updating layout: {e}")
    
    def stop_rendering(self):
        """Stop the progressive rendering."""
        self.render_timer.stop()
        self.pending_models.clear()
        self.render_index = 0


class SearchManager:
    """Manages search functionality and model loading."""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.utils = ModelDataUtils()
        
        # Background worker and progressive renderer
        self.search_worker = None
        self.progressive_renderer = ProgressiveRenderer(main_window)
        
        # Connect progressive renderer signals
        self.progressive_renderer.rendering_progress.connect(self._on_rendering_progress)
        self.progressive_renderer.rendering_complete.connect(self._on_rendering_complete)
        
        # Debounce timer for scroll events
        self.scroll_debounce_timer = QTimer()
        self.scroll_debounce_timer.setSingleShot(True)
        self.scroll_debounce_timer.timeout.connect(self._handle_scroll_load)
        
    def _on_rendering_progress(self, current, total):
        """Handle rendering progress updates."""
        self.main_window.status_bar.showMessage(f"Rendering models... {current}/{total}")
        
    def _on_rendering_complete(self):
        """Handle rendering completion."""
        main = self.main_window
        current_count = len(main.model_cards)
        main.status_bar.showMessage(f"Loaded {current_count} models")
        
        # Reset scroll position if this was a new search
        if hasattr(main, '_reset_scroll_on_complete') and main._reset_scroll_on_complete:
            main._reset_scroll_on_complete = False
            try:
                main.scroll_area.verticalScrollBar().setValue(0)
            except Exception:
                pass
    
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
        
        # Stop any ongoing rendering
        self.progressive_renderer.stop_rendering()
        
        # Stop any ongoing search worker
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.terminate()
            self.search_worker.wait(1000)  # Wait up to 1 second
        
        # Reset pagination when search parameters change
        main.model_page = 0
        main.model_has_more = True
        main.search_cursor = None
        main._reset_scroll_on_complete = True  # Flag to reset scroll when rendering completes
        
        # Clear existing cards
        main.clear_model_grid()
        
        # Show loading message
        main.status_bar.showMessage("Searching...")
        
        # Start search
        self.load_models()
    
    def load_models(self):
        """Load models from API with current search parameters."""
        main = self.main_window
        if not main.api_key or not main.model_has_more:
            return
        
        # Prevent multiple simultaneous requests
        if hasattr(main, '_loading_models') and main._loading_models:
            return
        main._loading_models = True
        
        # Stop any ongoing search worker
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.terminate()
            self.search_worker.wait(1000)
        
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
                'sort': sort_mapping.get(sort, "Most Downloaded"),
                'period': period_mapping.get(period, "AllTime"),
                'nsfw': nsfw
            }
            
            # Add pagination - use cursor if available, otherwise page number
            if main.search_cursor:
                params['cursor'] = main.search_cursor
                print(f"load_models: Using cursor pagination: {main.search_cursor}")
            else:
                params['page'] = main.model_page + 1
                print(f"load_models: Using page pagination: {main.model_page + 1}")
            
            if query:
                params['query'] = query
            if type_mapping.get(model_type):
                params['types'] = [type_mapping[model_type]]
            if base_model_mapping.get(base_model):
                params['baseModels'] = [base_model_mapping[base_model]]
            
            # Create and start background worker
            self.search_worker = SearchWorker(main.api, params)
            self.search_worker.search_completed.connect(self._on_search_completed)
            self.search_worker.search_error.connect(self._on_search_error)
            self.search_worker.finished.connect(lambda: setattr(main, '_loading_models', False))
            
            # Show loading status
            main.status_bar.showMessage("Loading models...")
            
            # Start the worker
            self.search_worker.start()
                
        except Exception as e:
            print(f"Error starting model search: {e}")
            main.status_bar.showMessage(f"Error starting search: {e}")
            main.model_has_more = False
            main._loading_models = False
    
    def _on_search_completed(self, models: List[Dict[str, Any]], metadata: Dict[str, Any]):
        """Handle successful search completion."""
        main = self.main_window
        
        print(f"_on_search_completed: Received {len(models)} models")
        print(f"_on_search_completed: Metadata: {metadata}")
        
        try:
            # Filter by base model if needed (client-side fallback)
            base_model = main.base_model_combo.currentText()
            print(f"_on_search_completed: Base model filter: {base_model}")
            
            # Check if filtering should be skipped
            if base_model not in ["All", "Any Base", ""]:
                before_filter = len(models)
                models = [m for m in models if self.utils.matches_base_model(m, base_model)]
                print(f"_on_search_completed: Filtered {before_filter} -> {len(models)} models")
            else:
                print(f"_on_search_completed: Skipping base model filter (showing all {len(models)} models)")
            
            # Update pagination
            main.model_page += 1
            
            # Determine if there are more pages using metadata
            total_items = metadata.get('totalItems', 0)
            total_pages = metadata.get('totalPages', 0)
            next_cursor = metadata.get('nextCursor')
            next_page_url = metadata.get('nextPage')
            
            # Check multiple indicators for more data
            has_more_by_cursor = bool(next_cursor)
            has_more_by_url = bool(next_page_url)
            has_more_by_pages = main.model_page < total_pages if total_pages > 0 else False
            has_more_by_count = len(models) >= 20  # Fallback if metadata is incomplete
            
            # Use the most reliable indicator
            if next_cursor or next_page_url:
                main.model_has_more = True
                main.search_cursor = next_cursor
            elif total_pages > 0:
                main.model_has_more = main.model_page < total_pages
            else:
                # Fallback: assume more if we got a full batch
                main.model_has_more = len(models) >= 20
            
            print(f"_on_search_completed: Page {main.model_page}, has_more: {main.model_has_more}")
            print(f"_on_search_completed: Indicators - cursor: {has_more_by_cursor}, url: {has_more_by_url}, pages: {has_more_by_pages}, count: {has_more_by_count}")
            print(f"_on_search_completed: Total items: {total_items}, total pages: {total_pages}, cursor: {next_cursor}")
            
            # Update metadata info
            try:
                total = metadata.get('totalItems', 0)
                current_count = len(main.model_cards)
                print(f"_on_search_completed: Total available: {total}, current cards: {current_count}")
                if total > 0:
                    main.status_bar.showMessage(f"Starting render... (Total available: {total})")
                else:
                    main.status_bar.showMessage(f"Starting render... ({len(models)} new models)")
            except Exception:
                main.status_bar.showMessage("Starting render...")
            
            # Start progressive rendering
            if models:
                print(f"_on_search_completed: Starting progressive rendering for {len(models)} models")
                self.progressive_renderer.start_rendering(models)
            else:
                print("_on_search_completed: No models to render")
                main.status_bar.showMessage("No more models found")
                
        except Exception as e:
            print(f"Error processing search results: {e}")
            main.status_bar.showMessage(f"Error processing results: {e}")
    
    def _on_search_error(self, error_message: str):
        """Handle search error."""
        main = self.main_window
        print(f"Search error: {error_message}")
        main.status_bar.showMessage(f"Search error: {error_message}")
        main.model_has_more = False
    
    def load_more_models_if_needed(self):
        """Load more models if scrolled near bottom (with debouncing)."""
        main = self.main_window
        try:
            # Only trigger for search view
            if getattr(main, 'current_left_view', 'search') != 'search':
                return
                
            # Don't load if already loading or no more models
            if (hasattr(main, '_loading_models') and main._loading_models) or not main.model_has_more:
                return
                
            # Don't load if currently rendering
            if self.progressive_renderer.render_timer.isActive():
                return
            
            scroll_area = main.scroll_area
            scrollbar = scroll_area.verticalScrollBar()
            
            # Check if near bottom (within 100px) and has scrollable content
            near_bottom = (scrollbar.value() >= scrollbar.maximum() - 100)
            has_content = scrollbar.maximum() > 0
            
            if near_bottom and has_content:
                # Use debounced loading to prevent rapid-fire requests
                self.scroll_debounce_timer.start(300)  # 300ms delay
                
        except Exception as e:
            print(f"Error in load_more_models_if_needed: {e}")
    
    def _handle_scroll_load(self):
        """Handle debounced scroll loading."""
        try:
            self.load_models()
        except Exception as e:
            print(f"Error in scroll load: {e}")
    
    def clear_model_grid(self):
        """Clear all model cards from grid."""
        main = self.main_window
        try:
            # Stop any ongoing rendering
            self.progressive_renderer.stop_rendering()
            
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
