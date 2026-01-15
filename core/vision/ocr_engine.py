"""OCR Engine Interface

Defines the abstract base class for OCR engines.
Enables swapping between Tesseract, PaddleOCR, EasyOCR, etc.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class TextRegion:
    text: str
    confidence: int
    x: int
    y: int
    w: int
    h: int

class OCREngine(ABC):
    """Abstract interface for OCR operations"""
    
    @abstractmethod
    def detect_text(self, image: Any, min_confidence: int = 60, region: Optional[List[int]] = None) -> List[TextRegion]:
        """Detect text in an image.
        
        Args:
            image: PIL Image or numpy array
            min_confidence: Minimum confidence threshold (0-100)
            region: Optional [x, y, w, h] to search within
            
        Returns:
            List of TextRegion objects
        """
        pass
