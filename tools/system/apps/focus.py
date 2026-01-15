"""Tool: system.apps.focus

Brings a specific window to the foreground.
Strictly handles ambiguity.

Category: system
Risk Level: low
Side Effects: changes_focus, changes_ui_state
"""

import win32gui
import win32con
from typing import Dict, Any, Optional
from tools.base import Tool
from tools.system.apps.utils import find_windows, get_window_info
from tools.system.apps.app_handle import HandleRegistry

class FocusApp(Tool):
    """Focus a specific application window"""
    
    @property
    def name(self) -> str:
        return "system.apps.focus"
    
    @property
    def description(self) -> str:
        return "Brings an application window to the foreground. Fails if ambiguous."
    
    @property
    def risk_level(self) -> str:
        return "low"
        
    @property
    def side_effects(self) -> list[str]:
        return ["changes_focus", "changes_ui_state"]
        
    @property
    def stabilization_time_ms(self) -> int:
        return 500 # Windows animations
        
    @property
    def reversible(self) -> bool:
        return True # Can focus something else

    @property
    def requires_visual_confirmation(self) -> bool:
        return False

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "handle_id": {
                    "type": "string",
                    "description": "AppHandle ID from launch (preferred - most precise)"
                },
                "app_name": {
                    "type": "string",
                    "description": "Name of app executable or partial title (e.g. 'notepad')"
                },
                "window_title": {
                    "type": "string",
                    "description": "Partial title to match (more specific)"
                },
                "pid": {
                    "type": "integer",
                    "description": "Specific Process ID"
                }
            },
            "required": []  # At least one should be provided, validated in logic
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute focus"""
        if not self.validate_args(args):
            return {"status": "error", "error": "Invalid arguments"}
        
        handle_id = args.get("handle_id")
        app_name = args.get("app_name")
        window_title = args.get("window_title")
        pid = args.get("pid")
        
        if not (handle_id or app_name or window_title or pid):
            return {"status": "error", "error": "Must provide handle_id, app_name, window_title, or pid"}
        
        # === PATH 1: Handle-based resolution (most precise) ===
        if handle_id:
            handle = HandleRegistry.get(handle_id)
            if not handle:
                return {
                    "status": "error",
                    "error": f"Handle not found: {handle_id[:8]}...",
                    "identity_basis": "unknown"
                }
            
            # Resolve handle to current windows
            matches = handle.resolve(
                find_windows_fn=find_windows,
                is_window_fn=win32gui.IsWindow,
                get_window_info_fn=get_window_info,
                allow_rebinding=False  # Strict - don't poison handle
            )
            
            if len(matches) == 0:
                return {
                    "status": "error",
                    "error": "Handle resolved to no windows (app may have closed)",
                    "handle_id": handle_id,
                    "resolution_confidence": handle.resolution_confidence.value,
                    "identity_basis": handle.identity_basis.value
                }
            
            if len(matches) > 1:
                return {
                    "status": "error",
                    "error": "start_ambiguous: Handle resolved to multiple windows",
                    "handle_id": handle_id,
                    "matches": [{"pid": m["pid"], "title": m["title"]} for m in matches[:5]]
                }
            
            # Single match from handle - go directly to focus
            target = matches[0]
        else:
            # === PATH 2: Legacy criteria-based lookup ===
            matches = find_windows(app_name=app_name, pid=pid, title_substring=window_title)
            
            # Handle Ambiguity (only for legacy path)
            if len(matches) == 0:
                return {
                    "status": "error",
                    "error": "No matching windows found",
                    "criteria": args
                }
                
            if len(matches) > 1:
                return {
                    "status": "error",
                    "error": "start_ambiguous: Multiple windows matched criteria",
                    "matches": [
                        {
                            "pid": m["pid"],
                            "title": m["title"],
                            "process": m["process_name"]
                        }
                        for m in matches[:5]  # Limit output
                    ]
                }
                
            target = matches[0]
        
        # === FOCUS (common path for both handle and legacy) ===
        try:
            hwnd = target["hwnd"]
            
            # Windows focus restrictions... usually SetForegroundWindow works if we are active
            # If minimized, Restore.
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            
            win32gui.SetForegroundWindow(hwnd)
            
            return {
                "status": "success",
                "focused_window": {
                    "title": target["title"],
                    "pid": target["pid"],
                    "process": target["process_name"]
                }
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Focus failed: {str(e)}"
            }
