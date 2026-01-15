"""Vision Manager

Factory/Singleton for getting the active OCR engine.
"""

from typing import Optional
from .ocr_engine import OCREngine
from .backends.paddleocr_backend import PaddleOCRBackend

class VisionManager:
    _instance: Optional['VisionManager'] = None
    _engine: Optional[OCREngine] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VisionManager, cls).__new__(cls)
            # PaddleOCR is now the default (pure Python, no external deps)
            cls._engine = PaddleOCRBackend()
        return cls._instance
    
    @classmethod
    def get_engine(cls) -> OCREngine:
        """Get the active OCR engine"""
        if cls._instance is None:
            cls()
        return cls._engine

def get_ocr_engine() -> OCREngine:
    """Convenience accessor"""
    return VisionManager.get_engine()
