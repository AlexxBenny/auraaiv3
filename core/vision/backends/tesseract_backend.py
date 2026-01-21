"""Tesseract OCR Backend

Implementation of OCREngine using pytesseract.
"""

import pytesseract
from typing import List, Any, Optional
from ..ocr_engine import OCREngine, TextRegion

class TesseractBackend(OCREngine):
    """Tesseract OCR implementation"""
    
    def detect_text(self, image: Any, min_confidence: int = 60, region: Optional[List[int]] = None) -> List[TextRegion]:
        """Detect text using Tesseract"""
        # If region provided, crop image first
        offset_x, offset_y = 0, 0
        if region:
            x, y, w, h = region
            image = image.crop((x, y, x + w, y + h))
            offset_x, offset_y = x, y

        # Run OCR
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        
        results = []
        n_boxes = len(data['text'])
        
        for i in range(n_boxes):
            text = data['text'][i].strip()
            # Skip empty text
            if not text:
                continue
                
            conf = int(data['conf'][i])
            if conf < min_confidence:
                continue
                
            results.append(TextRegion(
                text=text,
                confidence=conf,
                x=data['left'][i] + offset_x,
                y=data['top'][i] + offset_y,
                w=data['width'][i],
                h=data['height'][i]
            ))
            
        return results
