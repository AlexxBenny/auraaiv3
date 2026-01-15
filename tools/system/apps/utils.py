"""Shared utilities for application tools.

Provides window enumeration and matching logic using win32gui and psutil.
"""

import win32gui
import win32process
import psutil
from typing import List, Dict, Any, Optional

def get_window_info(hwnd: int) -> Dict[str, Any]:
    """Get detailed info for a window handle"""
    if not win32gui.IsWindow(hwnd):
        return {}
    
    title = win32gui.GetWindowText(hwnd)
    if not title:
        return {}
        
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    try:
        proc = psutil.Process(pid)
        process_name = proc.name().lower()
        exe_path = proc.exe()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        process_name = "unknown"
        exe_path = "unknown"
        
    rect = win32gui.GetWindowRect(hwnd)
    
    return {
        "hwnd": hwnd,
        "title": title,
        "pid": pid,
        "process_name": process_name,
        "exe_path": exe_path,
        "rect": rect
    }

def find_windows(
    app_name: Optional[str] = None, 
    pid: Optional[int] = None, 
    title_substring: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Find all windows matching criteria. 
    Returns list of window info dicts.
    """
    matches = []
    
    def enum_callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
            
        # Optimization: Filter by title early if cheap?
        # But we need process info for app_name check usually.
        
        info = get_window_info(hwnd)
        if not info:
            return
            
        # Match PID
        if pid is not None and info["pid"] != pid:
            return
            
        # Match Title
        if title_substring:
            if title_substring.lower() not in info["title"].lower():
                return
                
        # Match App Name (fuzzy)
        if app_name:
            target = app_name.lower()
            # Check process name (e.g. notepad.exe) or title
            if target not in info["process_name"] and target not in info["title"].lower():
                return
                
        matches.append(info)

    win32gui.EnumWindows(enum_callback, None)
    return matches
