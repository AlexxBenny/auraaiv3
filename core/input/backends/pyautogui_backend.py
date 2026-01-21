"""PyAutoGUI Input Backend

Implementation of InputBackend using pyautogui.
"""

import pyautogui
from typing import List, Optional, Tuple
from ..backend import InputBackend

class PyAutoGUIBackend(InputBackend):
    """PyAutoGUI utilization for input"""
    
    def __init__(self):
        # Fail-safe to prevent mouse from going out of control
        # Moving mouse to corner throws exception
        pyautogui.FAILSAFE = True
        
    def get_screen_size(self) -> Tuple[int, int]:
        return pyautogui.size()
        
    def get_mouse_position(self) -> Tuple[int, int]:
        return pyautogui.position()

    def move_to(self, x: int, y: int) -> Tuple[int, int]:
        """Move mouse to absolute coordinates"""
        # Validate logic should be in tool or manager, but backend can also guard
        screen_w, screen_h = self.get_screen_size()
        if not (0 <= x <= screen_w and 0 <= y <= screen_h):
            raise ValueError(f"Coordinates ({x},{y}) out of bounds ({screen_w},{screen_h})")
            
        pyautogui.moveTo(x, y)
        return self.get_mouse_position()

    def click(self, x: Optional[int], y: Optional[int], button: str, double: bool) -> Tuple[int, int]:
        """Click mouse button"""
        if x is not None and y is not None:
            self.move_to(x, y)
            
        clicks = 2 if double else 1
        pyautogui.click(button=button, clicks=clicks, interval=0.1)
        return self.get_mouse_position()

    def type_text(self, text: str, interval: float = 0.0) -> None:
        """Type a string of text"""
        pyautogui.write(text, interval=interval)

    def press_keys(self, keys: List[str], modifiers: List[str] = []) -> None:
        """Press key(s) with modifiers"""
        # Hold modifiers
        for mod in modifiers:
            pyautogui.keyDown(mod)
        
        # Press keys
        # If 'keys' is a list of single keys like ['a', 'b'], should we press them sequentially?
        # The tool currently passes a single key string or list? 
        # Interface says List[str], but tool passes single key usually.
        # Let's support sequential press if multiple keys provided (rare for shortcuts, usually 1 key)
        for key in keys:
            pyautogui.press(key)
        
        # Release modifiers
        for mod in reversed(modifiers):
            pyautogui.keyUp(mod)
