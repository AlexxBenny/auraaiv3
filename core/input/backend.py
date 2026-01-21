"""Input Backend Interface

Defines the abstract base class for all input backends.
Enables swapping between PyAutoGUI, ctypes, win32api, etc.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

class InputBackend(ABC):
    """Abstract interface for input operations"""
    
    @abstractmethod
    def move_to(self, x: int, y: int) -> Tuple[int, int]:
        """Move mouse to absolute coordinates.
        Returns final (x, y).
        """
        pass

    @abstractmethod
    def click(self, x: Optional[int], y: Optional[int], button: str, double: bool) -> Tuple[int, int]:
        """Click mouse button. 
        If x,y provided, move there first.
        Returns final (x, y).
        """
        pass

    @abstractmethod
    def type_text(self, text: str, interval: float = 0.0) -> None:
        """Type a string of text"""
        pass

    @abstractmethod
    def press_keys(self, keys: List[str], modifiers: List[str] = []) -> None:
        """Press a key or combination of keys"""
        pass

    @abstractmethod
    def get_mouse_position(self) -> Tuple[int, int]:
        """Get current mouse position"""
        pass
    
    @abstractmethod
    def get_screen_size(self) -> Tuple[int, int]:
        """Get screen resolution (width, height)
        Used for bounds checking.
        """
        pass
