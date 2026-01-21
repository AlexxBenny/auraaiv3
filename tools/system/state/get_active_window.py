"""Tool: system.state.get_active_window

Retrieves information about the currently active (focused) window.

Category: system
Risk Level: low
Side Effects: none
"""

import win32gui
import win32process
import psutil
from typing import Dict, Any
from tools.base import Tool


class GetActiveWindow(Tool):
    """Get information about the active window"""
    
    @property
    def name(self) -> str:
        return "system.state.get_active_window"
    
    @property
    def description(self) -> str:
        return "Gets details about the currently focused window (title, process, bounds)"
    
    @property
    def risk_level(self) -> str:
        return "low"
        
    @property
    def side_effects(self) -> list[str]:
        return []
        
    @property
    def stabilization_time_ms(self) -> int:
        return 10  # Very fast read
        
    @property
    def reversible(self) -> bool:
        return True  # Read-only

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool"""
        if not self.validate_args(args):
            return {"status": "error", "error": "Invalid arguments"}
            
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return {
                    "status": "success",
                    "window": None
                }
            
            # Get window text (title)
            title = win32gui.GetWindowText(hwnd)
            
            # Get window bounds
            rect = win32gui.GetWindowRect(hwnd)
            x, y, right, bottom = rect
            w = right - x
            h = bottom - y
            
            # Get process ID and name
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                process = psutil.Process(pid)
                process_name = process.name()
                exe_path = process.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                process_name = "unknown"
                exe_path = "unknown"
                
            # Get class name
            class_name = win32gui.GetClassName(hwnd)
            
            return {
                "status": "success",
                "window": {
                    "title": title,
                    "process_name": process_name,
                    "exe_path": exe_path,
                    "pid": pid,
                    "class_name": class_name,
                    "bounds": {
                        "x": x,
                        "y": y,
                        "width": w,
                        "height": h
                    },
                    "hwnd": hwnd
                }
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to get active window: {str(e)}"
            }
