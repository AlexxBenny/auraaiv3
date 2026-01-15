"""PaddleOCR Backend

Implementation of OCREngine using PaddleOCR v3.x API.
Uses predict() method and dict-like access to OCRResult.
"""

from paddleocr import PaddleOCR
from typing import List, Any, Optional
from ..ocr_engine import OCREngine, TextRegion

class PaddleOCRBackend(OCREngine):
    """PaddleOCR v3 implementation"""
    
    def __init__(self):
        # Initialize once (model loading is slow)
        self._ocr = PaddleOCR(lang='en')
    
    def detect_text(self, image: Any, min_confidence: int = 60, region: Optional[List[int]] = None) -> List[TextRegion]:
        """Detect text using PaddleOCR v3"""
        import numpy as np
        
        # Convert PIL image to numpy array (RGB)
        img_array = np.array(image)
        
        # If region provided, crop
        offset_x, offset_y = 0, 0
        if region:
            x, y, w, h = region
            img_array = img_array[y:y+h, x:x+w]
            offset_x, offset_y = x, y
        
        # Run OCR using predict() (v3 API)
        result_list = self._ocr.predict(img_array)
        
        results = []
        
        # Handle empty result
        if not result_list:
            return results
            
        try:
            # result_list is a list of OCRResult dict-like objects
            for ocr_result in result_list:
                # OCRResult is dict-like: use bracket access
                texts = ocr_result.get('rec_texts', [])
                scores = ocr_result.get('rec_scores', [])
                polys = ocr_result.get('rec_polys', [])
                
                for i, (text, score) in enumerate(zip(texts, scores)):
                    # Convert confidence to 0-100 scale
                    conf_pct = int(score * 100) if score <= 1 else int(score)
                    
                    if conf_pct < min_confidence:
                        continue
                    
                    # Get bounding box from polygon
                    if i < len(polys):
                        poly = polys[i]
                        # poly is numpy array [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                        try:
                            x_coords = [p[0] for p in poly]
                            y_coords = [p[1] for p in poly]
                            x_min = int(min(x_coords)) + offset_x
                            y_min = int(min(y_coords)) + offset_y
                            w = int(max(x_coords) - min(x_coords))
                            h = int(max(y_coords) - min(y_coords))
                        except:
                            # Fallback if poly format is unexpected
                            x_min, y_min, w, h = 0, 0, 100, 20
                    else:
                        x_min, y_min, w, h = 0, 0, 100, 20
                    
                    results.append(TextRegion(
                        text=text,
                        confidence=conf_pct,
                        x=x_min,
                        y=y_min,
                        w=w,
                        h=h
                    ))
                    
        except Exception as e:
            # If parsing fails, return empty results rather than crash
            import logging
            logging.warning(f"PaddleOCR parse error: {e}")
            return []
                
        return results
