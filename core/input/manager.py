"""Input Manager

Factory/Singleton for getting the active input backend.
"""

from typing import Optional
from .backend import InputBackend
from .backends.pyautogui_backend import PyAutoGUIBackend

class InputManager:
    _instance: Optional['InputManager'] = None
    _backend: Optional[InputBackend] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(InputManager, cls).__new__(cls)
            # In future: Load from config
            cls._backend = PyAutoGUIBackend()
        return cls._instance
    
    @classmethod
    def get_backend(cls) -> InputBackend:
        """Get the active input backend"""
        if cls._instance is None:
            cls()
        return cls._backend

def get_input_backend() -> InputBackend:
    """Convenience accessor"""
    return InputManager.get_backend()
