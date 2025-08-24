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
        main = self.main_window
        
        # Record previous view for caching
        prev_view = getattr(main, 'current_left_view', 'search')
        
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
        try:
            main.current_left_view = 'downloaded'
        except Exception:
            main.current_left_view = 'downloaded'
        
        # Update UI appearance
        try:
            main.title_label.setText("Downloaded Models")
            from constants import CARD_BACKGROUND
            main.title_container.setStyleSheet(f"background-color: {CARD_BACKGROUND.name()}; border-radius: 6px; padding: 10px;")
        except Exception:
            pass
        
        # Load downloaded models
        try:
            # Disable search pagination
            try:
                main.model_has_more = False
                main.search_cursor = None
                main.model_page = 0
            except Exception:
                pass
            
            self.load_downloaded_models_left()
            main.status_bar.showMessage("Showing downloaded models")
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
                main._left_agg_downloaded[key] = md
            else:
                if item.get('version_id'):
                    main._left_agg_downloaded[key]['_downloaded_versions'].append(item.get('version_id'))
                for im in (item.get('images') or []):
                    if im not in main._left_agg_downloaded[key]['_images']:
                        main._left_agg_downloaded[key]['_images'].append(im)
        
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
