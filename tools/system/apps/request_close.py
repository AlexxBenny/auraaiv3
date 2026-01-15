"""Tool: system.apps.request_close

Requests an application to close safely (WM_CLOSE).
Does NOT force kill.

Category: system
Risk Level: medium
Side Effects: changes_ui_state, stops_process
"""

import win32gui
import win32con
import time
import psutil
from typing import Dict, Any
from tools.base import Tool
from tools.system.apps.utils import find_windows, get_window_info
from tools.system.apps.app_handle import HandleRegistry

class RequestCloseApp(Tool):
    """Safely close an application"""
    
    @property
    def name(self) -> str:
        return "system.apps.request_close"
    
    @property
    def description(self) -> str:
        return "Requests an application to close (polite request). Fails if ambiguous."
    
    @property
    def risk_level(self) -> str:
        return "medium" # Can lose unsaved data if app doesn't handle prompt
        
    @property
    def side_effects(self) -> list[str]:
        return ["stops_process", "changes_ui_state"]
        
    @property
    def stabilization_time_ms(self) -> int:
        return 1000
        
    @property
    def reversible(self) -> bool:
        return False # Can relaunch but state lost

    @property
    def requires_visual_confirmation(self) -> bool:
        return True # Did it actually close?

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "handle_id": {
                    "type": "string",
                    "description": "AppHandle ID from launch (preferred - most precise)"
                },
                "window_title": {"type": "string"},
                "pid": {"type": "integer"},
                "timeout_ms": {
                    "type": "integer", 
                    "default": 3000,
                    "description": "Max wait time for close"
                }
            },
            "required": []  # Require one of handle_id/title/pid
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute close request"""
        if not self.validate_args(args):
            return {"status": "error", "error": "Invalid arguments"}
        
        handle_id = args.get("handle_id")
        window_title = args.get("window_title")
        pid = args.get("pid")
        timeout_sec = args.get("timeout_ms", 3000) / 1000.0
        
        if not (handle_id or window_title or pid):
            return {"status": "error", "error": "Must provide handle_id, window_title, or pid"}
        
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
                allow_rebinding=False
            )
            
            if len(matches) == 0:
                # Handle resolved to nothing - app may already be closed
                handle.invalidate()
                return {
                    "status": "success",
                    "closed": True,
                    "reason": "window_already_gone",
                    "handle_id": handle_id
                }
            
            if len(matches) > 1:
                return {
                    "status": "error",
                    "error": "Ambiguous close request: Handle resolved to multiple windows",
                    "handle_id": handle_id,
                    "matches": [{"pid": m["pid"], "title": m["title"]} for m in matches[:5]]
                }
            
            target = matches[0]
        else:
            # === PATH 2: Legacy criteria-based lookup ===
            matches = find_windows(pid=pid, title_substring=window_title)
            
            if len(matches) == 0:
                return {"status": "error", "error": "No matching windows found"}
            
            if len(matches) > 1:
                return {
                    "status": "error",
                    "error": "Ambiguous close request",
                    "matches": [
                         {"pid": m["pid"], "title": m["title"]} for m in matches[:5]
                    ]
                }
            
            target = matches[0]
        hwnd = target["hwnd"]
        target_pid = target["pid"]
        
        # 2. Request Close
        try:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            
            # Wait and Verify
            start_time = time.time()
            closed = False
            
            while time.time() - start_time < timeout_sec:
                if not win32gui.IsWindow(hwnd):
                    closed = True
                    break
                time.sleep(0.5)
            
            # Invalidate handle if closed and we have one
            if closed and handle_id:
                handle = HandleRegistry.get(handle_id)
                if handle:
                    handle.invalidate()
            
            return {
                "status": "success",
                "closed": closed,
                "reason": "success" if closed else "timeout_or_user_prompt",
                "target": {
                    "pid": target_pid,
                    "title": target["title"]
                }
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Close request failed: {str(e)}"
            }
