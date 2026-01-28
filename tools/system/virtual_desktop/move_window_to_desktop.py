"""Tool: system.virtual_desktop.move_window_to_desktop

Moves a window to a specified virtual desktop.

Category: action
Risk Level: low
Side Effects: window_moved

WINDOW MATCHING RULES (strict order):
1. Exact title match
2. Case-insensitive contains
3. Foreground fallback (only if exactly 1 window)
4. FAIL if >1 candidate (no guessing)

Uses VirtualDesktopAccessor.dll or pyvda with capability probe.
"""

import time
import logging
from typing import Dict, Any, List, Tuple

try:
    import win32gui
    import win32process
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

from ...base import Tool
from .accessor import move_window_to_desktop, get_desktop_count, is_capability_available


class MoveWindowToDesktop(Tool):
    """Move a window to a virtual desktop
    
    Uses strict window matching rules to prevent wrong-window bugs.
    """
    
    @property
    def name(self) -> str:
        return "system.virtual_desktop.move_window_to_desktop"
    
    @property
    def description(self) -> str:
        return "Moves a window (by title) to a specified virtual desktop"
    
    @property
    def risk_level(self) -> str:
        return "low"
    
    @property
    def side_effects(self) -> list[str]:
        return ["window_moved", "virtual_desktop_changed"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 300  # Electron apps may need repeated tries
    
    @property
    def reversible(self) -> bool:
        return True
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return False  # Window may move off current desktop
    
    @property
    def requires_focus(self) -> bool:
        return False
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return True
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "window_title": {
                    "type": "string",
                    "description": "Window title to match"
                },
                "desktop_number": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Target desktop number (1-indexed)"
                }
            },
            "required": ["window_title", "desktop_number"]
        }
    
    def _find_windows_by_title(self, title_pattern: str) -> List[Tuple[int, str]]:
        """Find windows matching title pattern.
        
        Returns:
            List of (hwnd, title) tuples
        """
        if not WIN32_AVAILABLE:
            return []
        
        matches = []
        
        def enum_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    matches.append((hwnd, title))
            return True
        
        try:
            win32gui.EnumWindows(enum_callback, None)
        except Exception as e:
            logging.error(f"EnumWindows failed: {e}")
        
        return matches
    
    def _match_window(self, title_pattern: str) -> Tuple[int, str, str]:
        """Match window using strict rules.
        
        Returns:
            (hwnd, title, match_method) or (0, "", "no_match")
        """
        windows = self._find_windows_by_title(title_pattern)
        
        if not windows:
            return 0, "", "no_windows"
        
        # Rule 1: Exact title match
        for hwnd, title in windows:
            if title == title_pattern:
                return hwnd, title, "exact"
        
        # Rule 2: Case-insensitive contains
        pattern_lower = title_pattern.lower()
        contains_matches = [
            (hwnd, title) for hwnd, title in windows
            if pattern_lower in title.lower()
        ]
        
        if len(contains_matches) == 1:
            hwnd, title = contains_matches[0]
            return hwnd, title, "contains"
        elif len(contains_matches) > 1:
            # FAIL: Multiple matches, no guessing
            return 0, "", "multiple_matches"
        
        # Rule 3: Foreground fallback (only if exactly 1 visible window)
        if len(windows) == 1:
            hwnd, title = windows[0]
            return hwnd, title, "foreground_fallback"
        
        return 0, "", "no_match"
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute move window to desktop"""
        # Dependency check
        if not WIN32_AVAILABLE:
            return {
                "status": "error",
                "error": "Dependency not installed: pywin32"
            }
        
        # Capability probe
        if not is_capability_available():
            return {
                "status": "unsupported",
                "error": "Virtual desktop control not available on this system"
            }
        
        window_title = args.get("window_title")
        desktop_number = args.get("desktop_number")
        
        if window_title is None:
            return {
                "status": "error",
                "error": "Required argument 'window_title' not provided"
            }
        
        if desktop_number is None:
            return {
                "status": "error",
                "error": "Required argument 'desktop_number' not provided"
            }
        
        try:
            # Validate desktop exists
            total = get_desktop_count()
            if total and desktop_number > total:
                return {
                    "status": "error",
                    "error": f"Desktop {desktop_number} does not exist. Only {total} desktops available."
                }
            
            # Match window with strict rules
            hwnd, matched_title, match_method = self._match_window(window_title)
            
            if match_method == "no_windows":
                return {
                    "status": "error",
                    "error": "No visible windows found"
                }
            
            if match_method == "multiple_matches":
                return {
                    "status": "error",
                    "error": f"Multiple windows match '{window_title}'. Be more specific."
                }
            
            if match_method == "no_match":
                return {
                    "status": "error",
                    "error": f"No window found matching '{window_title}'"
                }
            
            # Move window (may need retries for Electron apps)
            success = False
            for attempt in range(3):
                if move_window_to_desktop(hwnd, desktop_number):
                    success = True
                    break
                time.sleep(0.15)
            
            if success:
                time.sleep(self.stabilization_time_ms / 1000.0)
                logging.info(f"Moved '{matched_title}' to desktop {desktop_number} (method: {match_method})")
                return {
                    "status": "success",
                    "action": "move_window_to_desktop",
                    "window_title": matched_title,
                    "desktop_number": desktop_number,
                    "match_method": match_method
                }
            else:
                return {
                    "status": "error",
                    "error": f"Failed to move '{matched_title}' to desktop {desktop_number}"
                }
            
        except Exception as e:
            logging.error(f"Failed to move window: {e}")
            return {
                "status": "error",
                "error": f"Failed to move window: {str(e)}"
            }
