"""Tool: system.display.find_text

Locates text on screen using OCR.
Returns bounds, confidence, and frame hash.

Category: system
Risk Level: low
Side Effects: none
"""

import pyautogui
import hashlib
from typing import Dict, Any, List
from tools.base import Tool
from core.vision.manager import get_ocr_engine

class FindText(Tool):
    """Find text on screen"""
    
    @property
    def name(self) -> str:
        return "system.display.find_text"
    
    @property
    def description(self) -> str:
        return "Locates text on the screen using OCR. Returns coordinates and confidence."
    
    @property
    def risk_level(self) -> str:
        return "low"
        
    @property
    def side_effects(self) -> list[str]:
        return []
        
    @property
    def stabilization_time_ms(self) -> int:
        return 500  # OCR is slow
        
    @property
    def reversible(self) -> bool:
        return True

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string", 
                    "description": "text to find (case-insensitive partial match)"
                },
                "min_confidence": {
                    "type": "integer",
                    "default": 60,
                    "description": "Minimum confidence threshold (0-100)"
                },
                "region": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "[x, y, w, h] to search within"
                }
            },
            "required": ["text"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute text search"""
        if not self.validate_args(args):
            return {"status": "error", "error": "Invalid arguments"}
            
        target_text = args["text"].lower()
        min_conf = args.get("min_confidence", 60)
        region = args.get("region")
        
        try:
            # Capture screenshot using pyautogui
            # Future: Use ViewBackend for screenshots too?
            if region:
                screenshot = pyautogui.screenshot(region=tuple(region))
            else:
                screenshot = pyautogui.screenshot()
                
            # Compute frame hash for state tracking
            img_bytes = screenshot.tobytes()
            frame_hash = hashlib.md5(img_bytes).hexdigest()[:8]
            
            # Run OCR using abstract engine
            engine = get_ocr_engine()
            regions = engine.detect_text(screenshot, min_confidence=min_conf)
            
            matches = []
            
            # Since regions are now absolute relative to the IMAGE PASSED,
            # if we cropped screenshot (by passing region to pyautogui.screenshot), 
            # we need to adjust output coords relative to SCREEN.
            # BUT: In TesseractBackend we handle cropping if region is passed TO THE BACKEND.
            # Here I passed the CROPPED IMAGE to detect_text but with NO region arg?
            # Or pass full image + region?
            
            # Current implementation of tool:
            # 1. Capture screenshot (cropped or full)
            # 2. Pass to engine.detect_text(image) 
            # If cropped, image coords are 0,0 based. Need to add offset.
            
            screen_offset_x = region[0] if region else 0
            screen_offset_y = region[1] if region else 0
            
            for r in regions:
                text_found = r.text.lower()
                
                if target_text in text_found:
                    matches.append({
                        "text": r.text,
                        "confidence": r.confidence,
                        "bounds": {
                            "x": r.x + screen_offset_x,
                            "y": r.y + screen_offset_y,
                            "w": r.w, 
                            "h": r.h
                        }
                    })
            
            return {
                "status": "success",
                "found": len(matches) > 0,
                "matches": matches,
                "frame_hash": frame_hash,
                "best_match": matches[0] if matches else None
            }
            
        except Exception as e:
             return {
                "status": "error",
                "error": f"OCR failed: {str(e)}"
            }
