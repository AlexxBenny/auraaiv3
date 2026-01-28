"""Virtual Desktop Accessor - DLL wrapper with capability probe

Provides Python access to Windows Virtual Desktop APIs through
VirtualDesktopAccessor.dll or pyvda library as fallback.

CAPABILITY PROBE PATTERN:
- Try loading DLL
- If fail, try pyvda
- If both fail, mark capability as unsupported (no exceptions)
"""

import os
import ctypes
import logging
from typing import Optional, Tuple

# Path to DLL in same directory
DLL_PATH = os.path.join(os.path.dirname(__file__), "VirtualDesktopAccessor.dll")

# Global capability state
_dll_handle: Optional[ctypes.CDLL] = None
_pyvda_available: bool = False
_capability_checked: bool = False
_capability_available: bool = False


def _probe_capability() -> Tuple[bool, str]:
    """Probe virtual desktop capability.
    
    Returns:
        (available: bool, method: str)
        method is "dll", "pyvda", or "none"
    """
    global _dll_handle, _pyvda_available, _capability_checked, _capability_available
    
    if _capability_checked:
        if _dll_handle:
            return True, "dll"
        elif _pyvda_available:
            return True, "pyvda"
        else:
            return False, "none"
    
    _capability_checked = True
    
    # Try 1: Load DLL
    if os.path.exists(DLL_PATH):
        try:
            _dll_handle = ctypes.WinDLL(DLL_PATH)
            logging.info(f"VirtualDesktopAccessor.dll loaded from {DLL_PATH}")
            _capability_available = True
            return True, "dll"
        except OSError as e:
            logging.warning(f"Failed to load VirtualDesktopAccessor.dll: {e}")
    
    # Try 2: pyvda library
    try:
        import pyvda
        _pyvda_available = True
        logging.info("pyvda library available for virtual desktop control")
        _capability_available = True
        return True, "pyvda"
    except ImportError:
        logging.warning("pyvda library not available")
    
    # Both failed
    logging.warning("Virtual desktop control not available on this system")
    _capability_available = False
    return False, "none"


def get_current_desktop_number() -> Optional[int]:
    """Get current virtual desktop number (1-indexed).
    
    Returns:
        Desktop number or None if unsupported
    """
    available, method = _probe_capability()
    
    if not available:
        return None
    
    if method == "dll":
        try:
            result = _dll_handle.GetCurrentDesktopNumber()
            return result + 1  # Convert to 1-indexed
        except Exception as e:
            logging.error(f"DLL GetCurrentDesktopNumber failed: {e}")
            return None
    
    elif method == "pyvda":
        try:
            import pyvda
            return pyvda.get_current_desktop_number() + 1
        except Exception as e:
            logging.error(f"pyvda get_current_desktop failed: {e}")
            return None
    
    return None


def get_desktop_count() -> Optional[int]:
    """Get total number of virtual desktops.
    
    Returns:
        Count or None if unsupported
    """
    available, method = _probe_capability()
    
    if not available:
        return None
    
    if method == "dll":
        try:
            return _dll_handle.GetDesktopCount()
        except Exception as e:
            logging.error(f"DLL GetDesktopCount failed: {e}")
            return None
    
    elif method == "pyvda":
        try:
            import pyvda
            return len(pyvda.get_virtual_desktops())
        except Exception as e:
            logging.error(f"pyvda get_desktop_count failed: {e}")
            return None
    
    return None


def switch_to_desktop(desktop_number: int) -> bool:
    """Switch to specified virtual desktop.
    
    Args:
        desktop_number: 1-indexed desktop number
        
    Returns:
        True if successful, False otherwise
    """
    available, method = _probe_capability()
    
    if not available:
        return False
    
    zero_indexed = desktop_number - 1
    
    if method == "dll":
        try:
            result = _dll_handle.GoToDesktopNumber(zero_indexed)
            return result == 0
        except Exception as e:
            logging.error(f"DLL GoToDesktopNumber failed: {e}")
            return False
    
    elif method == "pyvda":
        try:
            import pyvda
            desktops = pyvda.get_virtual_desktops()
            if 0 <= zero_indexed < len(desktops):
                desktops[zero_indexed].go()
                return True
            return False
        except Exception as e:
            logging.error(f"pyvda switch_desktop failed: {e}")
            return False
    
    return False


def move_window_to_desktop(hwnd: int, desktop_number: int) -> bool:
    """Move window to specified virtual desktop.
    
    Args:
        hwnd: Window handle
        desktop_number: 1-indexed desktop number
        
    Returns:
        True if successful, False otherwise
    """
    available, method = _probe_capability()
    
    if not available:
        return False
    
    zero_indexed = desktop_number - 1
    
    if method == "dll":
        try:
            result = _dll_handle.MoveWindowToDesktopNumber(hwnd, zero_indexed)
            return result == 0
        except Exception as e:
            logging.error(f"DLL MoveWindowToDesktopNumber failed: {e}")
            return False
    
    elif method == "pyvda":
        try:
            import pyvda
            from pyvda import AppView
            desktops = pyvda.get_virtual_desktops()
            if 0 <= zero_indexed < len(desktops):
                app = AppView.from_hwnd(hwnd)
                app.move(desktops[zero_indexed])
                return True
            return False
        except Exception as e:
            logging.error(f"pyvda move_window failed: {e}")
            return False
    
    return False


def is_capability_available() -> bool:
    """Check if virtual desktop control is available."""
    available, _ = _probe_capability()
    return available


def get_capability_method() -> str:
    """Get the method being used for virtual desktop control."""
    _, method = _probe_capability()
    return method
