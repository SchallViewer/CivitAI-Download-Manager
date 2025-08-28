# downloaded_manager.py - Downloaded models functionality
from typing import Dict, List, Any
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QPixmap
from ui_components import ModelCard
from window_parts.model_utils import ModelDataUtils


class DownloadedManager:
    """Manages downloaded models functionality."""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.utils = ModelDataUtils()
    
    def show_downloaded_explorer(self):
        """Show downloaded models in the left grid panel."""
        print("DEBUG: show_downloaded_explorer called - switching to downloaded explorer")
        main = self.main_window
        
        # Record previous view for caching and selection preservation
        prev_view = getattr(main, 'current_left_view', 'search')
        print(f"DEBUG: Previous view was: {prev_view}")
        
        # Save current model selection for restoration later
        current_model_id = None
        current_version_id = None
        try:
            if hasattr(main, 'current_model') and main.current_model:
                current_model_id = main.current_model.get('id')
            if hasattr(main, 'current_version') and main.current_version:
                current_version_id = main.current_version.get('id')
            main._saved_selection = {
                'model_id': current_model_id,
                'version_id': current_version_id,
                'view': prev_view
            }
        except Exception:
            pass
        
        # Cache search results when switching away
        try:
            if prev_view == 'search' and getattr(main, 'model_cards', None):
                cached = []
                for c in main.model_cards[:21]:
                    try:
                        md = getattr(c, 'model_data', None) or {}
                        cached.append(md)
                    except Exception:
                        continue
                main._search_cache = cached
        except Exception:
            pass
        
        # Update current view
        print("DEBUG: Setting current_left_view to 'downloaded'")
        try:
            main.current_left_view = 'downloaded'
        except Exception:
            main.current_left_view = 'downloaded'
        
        # Update UI appearance
        print("DEBUG: Updating UI appearance for downloaded mode")
        try:
            main.title_label.setText("Downloaded Models")
            from constants import CARD_BACKGROUND
            main.title_container.setStyleSheet(f"background-color: {CARD_BACKGROUND.name()}; border-radius: 6px; padding: 10px;")
        except Exception:
            pass
        
        # Clear search input to avoid confusion (will be used for filtering now)
        print("DEBUG: Setting search input placeholder for downloaded mode")
        try:
            main.search_input.setPlaceholderText("Filter downloaded models...")
        except Exception:
            pass
        
        # Load downloaded models first
        print("DEBUG: Loading downloaded models")
        try:
            # Disable search pagination
            print("DEBUG: Disabling search pagination")
            try:
                main.model_has_more = False
                main.search_cursor = None
                main.model_page = 0
            except Exception:
                pass
            
            print("DEBUG: Calling load_downloaded_models_left()")
            self.load_downloaded_models_left()
            main.status_bar.showMessage("Showing downloaded models")
            
            # Update filter options for downloaded explorer (after models are loaded)
            print("DEBUG: Setting up downloaded filters")
            self.setup_downloaded_filters()
            
            # Try to restore previous model selection if switching from search
            print("DEBUG: Attempting to restore previous selection")
            try:
                saved_selection = getattr(main, '_saved_selection', {})
                if (saved_selection.get('view') == 'search' and 
                    saved_selection.get('model_id')):
                    # Try to find and select the same model in downloaded results
                    print(f"DEBUG: Restoring selection for model ID: {saved_selection.get('model_id')}")
                    self.restore_downloaded_selection(saved_selection.get('model_id'), saved_selection.get('version_id'))
                else:
                    print("DEBUG: No previous selection to restore")
            except Exception as e:
                print(f"DEBUG: Error restoring selection: {e}")
                pass
                
        except Exception as e:
            print("Error showing downloaded explorer:", e)
            # Fallback to right panel if left loading fails
            try:
                self.load_downloaded_models()
                idx = None
                for i in range(main.right_panel.count()):
                    if main.right_panel.widget(i) is main.downloaded_explorer_panel:
                        idx = i
                        break
                if idx is not None:
                    main.right_panel.setCurrentIndex(idx)
            except Exception:
                pass
    
    def setup_downloaded_filters(self):
        """Configure filter options for downloaded explorer mode."""
        print("DEBUG: setup_downloaded_filters called")
        main = self.main_window
        
        try:
            # Store original filter states if not already stored
            if not hasattr(main, '_original_filters_saved'):
                print("DEBUG: Saving original filter states")
                main._original_sort_items = []
                main._original_period_items = []
                
                # Save original sort combo items
                for i in range(main.sort_combo.count()):
                    text = main.sort_combo.itemText(i)
                    data = main.sort_combo.itemData(i)
                    main._original_sort_items.append((text, data))
                
                # Save original period combo items
                for i in range(main.period_combo.count()):
                    text = main.period_combo.itemText(i)
                    data = main.period_combo.itemData(i)
                    main._original_period_items.append((text, data))
                
                main._original_filters_saved = True
            
            # Temporarily disconnect signals to prevent triggering searches during setup
            print("DEBUG: Temporarily disconnecting filter signals for setup")
            try:
                main.sort_combo.currentIndexChanged.disconnect()
                main.period_combo.currentIndexChanged.disconnect()
            except:
                pass
            
            # Hide NSFW checkbox for downloaded explorer
            print("DEBUG: Hiding NSFW checkbox for downloaded explorer")
            if hasattr(main, 'nsfw_checkbox'):
                main.nsfw_checkbox.setVisible(False)
                print("DEBUG: NSFW checkbox hidden successfully")
            
            # Update sort combo for downloaded explorer
            print("DEBUG: Updating sort combo for downloaded explorer")
            main.sort_combo.clear()
            main.sort_combo.addItem("Newest", "newest")
            main.sort_combo.addItem("Title Name", "title")
            
            # Update period combo to show available tags
            print("DEBUG: Updating period combo with available tags")
            main.period_combo.clear()
            main.period_combo.addItem("All Tags", None)
            
            # Collect available tags from downloaded models
            print("DEBUG: Collecting available tags from downloaded models")
            available_tags = self.get_available_tags()
            print(f"DEBUG: Found {len(available_tags)} available tags")
            for tag in available_tags:
                main.period_combo.addItem(tag, tag.lower())
            
            # Reconnect signals after setup
            print("DEBUG: Reconnecting filter signals after setup")
            try:
                main.sort_combo.currentIndexChanged.connect(main.handle_filter_change)
                main.period_combo.currentIndexChanged.connect(main.handle_filter_change)
            except:
                pass
                
        except Exception as e:
            print(f"Error setting up downloaded filters: {e}")
    
    def get_available_tags(self):
        """Get available main tags from downloaded models in the database."""
        main = self.main_window
        
        try:
            # Get downloaded models to extract unique main tags
            models = main.db_manager.get_downloaded_models() or []
            
            # Collect unique main tags from downloaded models
            main_tags = set()
            for item in models:
                main_tag = item.get('main_tag')
                if main_tag and main_tag.strip():
                    main_tags.add(main_tag.strip())
            
            # Convert to sorted list
            available_tags = sorted(list(main_tags))
            return available_tags
            
        except Exception as e:
            print(f"Error getting main tags from downloaded models: {e}")
            # Fallback to all MainTag enum values if there's an error
            from constants import MainTag
            return [tag.value for tag in MainTag]
    
    def restore_search_filters(self):
        """Restore original filter options when returning to search explorer."""
        print("DEBUG: restore_search_filters called")
        main = self.main_window
        
        try:
            if hasattr(main, '_original_filters_saved'):
                print("DEBUG: Restoring original filters from saved state")
                
                # Temporarily disconnect signals to prevent triggering searches during restore
                print("DEBUG: Temporarily disconnecting filter signals")
                try:
                    main.sort_combo.currentIndexChanged.disconnect()
                    main.period_combo.currentIndexChanged.disconnect()
                except:
                    pass
                
                # Show NSFW checkbox for search explorer
                print("DEBUG: Showing NSFW checkbox for search explorer")
                if hasattr(main, 'nsfw_checkbox'):
                    main.nsfw_checkbox.setVisible(True)
                    print("DEBUG: NSFW checkbox shown successfully")
                
                # Restore sort combo
                print("DEBUG: Restoring sort combo")
                main.sort_combo.clear()
                for text, data in main._original_sort_items:
                    main.sort_combo.addItem(text, data)
                
                # Restore period combo
                print("DEBUG: Restoring period combo")
                main.period_combo.clear()
                for text, data in main._original_period_items:
                    main.period_combo.addItem(text, data)
                
                # Reconnect signals after restore
                print("DEBUG: Reconnecting filter signals")
                try:
                    main.sort_combo.currentIndexChanged.connect(main.handle_filter_change)
                    main.period_combo.currentIndexChanged.connect(main.handle_filter_change)
                except:
                    pass
                    
        except Exception as e:
            print(f"Error restoring search filters: {e}")
            print(f"DEBUG: Exception details: {e}")
    
    def load_downloaded_models_left(self):
        """Load downloaded models into the left-hand model grid."""
        main = self.main_window
        
        # Clear existing grid
        try:
            while main.model_grid_layout.count():
                child = main.model_grid_layout.takeAt(0)
                if child and child.widget():
                    child.widget().setParent(None)
            main.model_cards = []
            
            models = main.db_manager.get_downloaded_models() or []
        except Exception as e:
            print("Error fetching downloaded models:", e)
            models = []
        
        # Aggregate by model to avoid duplicate cards
        if not hasattr(main, '_left_agg_downloaded'):
            main._left_agg_downloaded = {}
        
        main._left_agg_downloaded.clear()
        
        for item in models:
            model_data = item.get('metadata') or {}
            try:
                if item.get('model_id') and (not model_data.get('id')):
                    model_data['id'] = item.get('model_id')
                if item.get('model_name') and (not model_data.get('name')):
                    model_data['name'] = item.get('model_name')
            except Exception:
                pass
            
            model_id = item.get('model_id') or model_data.get('id')
            key = f"m_{model_id}" if model_id is not None else f"db_{item.get('id')}"
            
            if key not in main._left_agg_downloaded:
                md = dict(model_data)
                # Attach versions list for offline entries
                try:
                    if model_id and 'modelVersions' not in md and hasattr(main, 'db_manager'):
                        md['modelVersions'] = main.db_manager.get_model_versions(model_id)
                except Exception:
                    pass
                
                md['_db_id'] = item.get('id')
                md['_downloaded_versions'] = [item.get('version_id')] if item.get('version_id') else []
                md['_images'] = item.get('images') or []
                md['main_tag'] = item.get('main_tag')  # Include main_tag from database
                main._left_agg_downloaded[key] = md
            else:
                if item.get('version_id'):
                    main._left_agg_downloaded[key]['_downloaded_versions'].append(item.get('version_id'))
                for im in (item.get('images') or []):
                    if im not in main._left_agg_downloaded[key]['_images']:
                        main._left_agg_downloaded[key]['_images'].append(im)
                # Update main_tag if not already set or if this item has a main_tag
                if item.get('main_tag') and not main._left_agg_downloaded[key].get('main_tag'):
                    main._left_agg_downloaded[key]['main_tag'] = item.get('main_tag')
        
        # Create cards from aggregated entries
        missing_map = {}
        try:
            if hasattr(main, 'db_manager'):
                missing_map = main.db_manager.get_missing_status_map() or {}
        except Exception:
            missing_map = {}
        
        for k, md in main._left_agg_downloaded.items():
            card = ModelCard(md)
            card.clicked.connect(main.show_downloaded_model_details)
            
            # Set local image if available
            imgs = md.get('_images') or []
            if imgs:
                try:
                    pix = QPixmap(imgs[0])
                    if not pix.isNull():
                        card.set_image(pix)
                except Exception:
                    pass
            
            # Highlight if Missing
            try:
                mid = md.get('id') or md.get('model_id') or md.get('_db_id')
                if mid in missing_map:
                    card.setStyleSheet(card.styleSheet() + '\nModelCard { background-color: #664; border: 2px solid #ffeb3b; }')
            except Exception:
                pass
            
            main.model_cards.append(card)
        
        # Layout cards in grid
        main.relayout_model_cards()
    
    def restore_downloaded_selection(self, target_model_id, target_version_id=None):
        """Try to restore model selection in downloaded explorer."""
        main = self.main_window
        try:
            if not hasattr(main, 'model_cards') or not main.model_cards:
                return
            
            for card in main.model_cards:
                card_model_data = getattr(card, 'model_data', {})
                if (card_model_data.get('id') == target_model_id or 
                    card_model_data.get('model_id') == target_model_id):
                    # Found the matching model card, simulate click
                    if hasattr(card, 'clicked'):
                        card.clicked.emit()
                    break
        except Exception:
            pass
    
    def load_downloaded_models(self):
        """Load downloaded models into the right panel grid (original functionality)."""
        main = self.main_window
        
        # Clear existing
        for i in reversed(range(main.downloaded_grid_layout.count())):
            w = main.downloaded_grid_layout.itemAt(i).widget() if main.downloaded_grid_layout.itemAt(i) else None
            if w:
                w.setParent(None)
        
        models = []
        try:
            models = main.db_manager.get_downloaded_models()
        except Exception:
            models = []
        
        # Aggregate by model_id
        agg = {}
        for item in models:
            model_data = item.get('metadata') or {}
            try:
                if item.get('model_id') and (not model_data.get('id')):
                    model_data['id'] = item.get('model_id')
                if item.get('model_name') and (not model_data.get('name')):
                    model_data['name'] = item.get('model_name')
            except Exception:
                pass
            
            model_id = item.get('model_id') or model_data.get('id')
            key = f"m_{model_id}" if model_id is not None else f"db_{item.get('id')}"
            
            if key not in agg:
                md = dict(model_data)
                try:
                    if model_id and 'modelVersions' not in md and hasattr(main, 'db_manager'):
                        md['modelVersions'] = main.db_manager.get_model_versions(model_id)
                except Exception:
                    pass
                
                md['_db_id'] = item.get('id')
                md['_downloaded_versions'] = [item.get('version_id')] if item.get('version_id') else []
                md['_images'] = item.get('images') or []
                agg[key] = md
            else:
                if item.get('version_id'):
                    agg[key]['_downloaded_versions'].append(item.get('version_id'))
                for im in (item.get('images') or []):
                    if im not in agg[key]['_images']:
                        agg[key]['_images'].append(im)
        
        # Render aggregated cards
        for i, (k, md) in enumerate(agg.items()):
            card = ModelCard(md)
            card.clicked.connect(main.show_downloaded_model_details)
            
            imgs = md.get('_images') or []
            if imgs:
                try:
                    pix = QPixmap(imgs[0])
                    if not pix.isNull():
                        card.set_image(pix)
                except Exception:
                    pass
            
            row = i // 4
            col = i % 4
            main.downloaded_grid_layout.addWidget(card, row, col)
    
    def show_downloaded_model_details(self, model_data):
        """Show downloaded model details in details panel."""
        main = self.main_window
        
        try:
            # Mark that we're routing through downloaded-explorer
            try:
                main._incoming_show_from_downloaded = True
            except Exception:
                pass
            
            # Suppress initial API image loading
            try:
                main._suppress_details_initial_load = True
            except Exception:
                pass
            
            main.show_model_details(model_data)
            
            try:
                main._suppress_details_initial_load = False
                main._incoming_show_from_downloaded = False
            except Exception:
                pass
            
            # Disable download button (already downloaded)
            main.download_btn.setEnabled(False)
            main.download_btn.setVisible(False)
            
            # Show downloaded badge
            main.model_name.setText(main.model_name.text() + "  (Downloaded)")
            
            # Prefer locally saved images
            imgs = []
            try:
                model_id = model_data.get('id') or model_data.get('model_id') or model_data.get('_db_id')
                version_id = None
                try:
                    if getattr(main, 'current_version', None):
                        version_id = main.current_version.get('id')
                except Exception:
                    version_id = None
                
                try:
                    if model_id and hasattr(main, 'db_manager'):
                        rec = main.db_manager.find_downloaded_model(model_id, version_id) if version_id else None
                        if rec and isinstance(rec, dict):
                            imgs = rec.get('images') or []
                except Exception:
                    pass
                
                if not imgs:
                    imgs = model_data.get('_images') or []
            except Exception:
                imgs = []
            
            if imgs:
                main.details_images_urls = imgs[:5]
                main.details_image_index = 0
                main._load_details_image_by_index(main.details_image_index)
                try:
                    main._showing_downloaded_details = True
                except Exception:
                    pass
        except Exception:
            pass
