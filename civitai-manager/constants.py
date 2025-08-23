from enum import Enum
from PyQt5.QtGui import QColor

class ModelType(Enum):
    CHECKPOINT = "Checkpoint"
    LORA = "LoRA"
    TEXTURE = "Texture"
    EMBEDDING = "Embedding"
    HYPERNET = "Hypernetwork"
    AESTHETIC = "Aesthetic Gradient"

class MainTag(Enum):
    CHARACTER = "Character"
    STYLE = "Style"
    CONCEPT = "Concept"
    REALISM = "Realism"
    ANIME = "Anime"
    FANTASY = "Fantasy"

# Civitai color palette
PRIMARY_COLOR = QColor("#7e57c2")  # Deep purple
SECONDARY_COLOR = QColor("#03dac5")  # Teal
BACKGROUND_COLOR = QColor("#121212")  # Dark background
CARD_BACKGROUND = QColor("#1e1e1e")  # Card background
TEXT_COLOR = QColor("#e0e0e0")  # Primary text
SECONDARY_TEXT = QColor("#9e9e9e")  # Secondary text
ACCENT_COLOR = QColor("#ff4081")  # Pink accent

API_BASE_URL = "https://civitai.com/api/v1"
MAX_CONCURRENT_DOWNLOADS = 3
