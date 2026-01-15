"""Tool: system.apps.launch

Launches an application.
Supports waiting for window appearance.

Category: system
Risk Level: medium
Side Effects: changes_focus, changes_ui_state, launches_process
"""

import subprocess
import time
import psutil
from typing import Dict, Any
from tools.base import Tool
from tools.system.apps.utils import find_windows
from tools.system.apps.app_handle import AppHandle, HandleRegistry

class LaunchApp(Tool):
    """Launch an application"""
    
    @property
    def name(self) -> str:
        return "system.apps.launch"
    
    @property
    def description(self) -> str:
        return "Launches an application. Can wait for window to appear."
    
    @property
    def risk_level(self) -> str:
        return "medium"
        
    @property
    def side_effects(self) -> list[str]:
        return ["changes_focus", "changes_ui_state", "resource_usage"]
        
    @property
    def stabilization_time_ms(self) -> int:
        return 2000 # App startup is slow
        
    @property
    def reversible(self) -> bool:
        return True # Can close app

    @property
    def requires_visual_confirmation(self) -> bool:
        return True

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Name of executable (e.g. 'notepad')"
                },
                "path": {
                    "type": "string",
                    "description": "Full path to executable (optional if in PATH)"
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Command line arguments"
                },
                "wait_for_window": {
                    "type": "boolean",
                    "default": True,
                    "description": "Wait for a visible window to appear?"
                },
                "timeout_ms": {
                    "type": "integer",
                    "default": 10000,
                    "description": "Timeout for wait_for_window"
                }
            },
            "required": ["app_name"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute launch"""
        if not self.validate_args(args):
            return {"status": "error", "error": "Invalid arguments"}
            
        app_name = args["app_name"]
        path = args.get("path")
        cmd_args = args.get("args", [])
        wait = args.get("wait_for_window", True)
        timeout_sec = args.get("timeout_ms", 10000) / 1000.0
        
        # 1. Construct command
        # If path provided, use it. Else assume app_name is in PATH or simple name.
        if path:
            executable = path
        else:
            # Simple heuristic: if it doesn't have extension, add .exe? 
            # Subprocess usually handles PATH lookup.
            executable = app_name
            
        full_cmd = [executable] + cmd_args
        
        try:
            # 2. Launch
            proc = subprocess.Popen(full_cmd, shell=False)
            pid = proc.pid
            
            if not wait:
                # Create minimal handle even without waiting
                handle = AppHandle.create(app_name, " ".join(full_cmd))
                HandleRegistry.register(handle)
                return {
                    "status": "success",
                    "pid": pid,
                    "app_handle": handle.to_dict(),
                    "note": "Did not wait for window - handle unbound"
                }
            
            # 3. Wait for Window (app_name based, not PID-only)
            # Windows 11 UWP apps (like Notepad) spawn separate processes,
            # so we cannot rely on the launched PID. We poll by app_name.
            start_time = time.time()
            found_window = None
            
            while time.time() - start_time < timeout_sec:
                # Try to find window by app_name first (most reliable for UWP)
                matches = find_windows(app_name=app_name)
                if matches:
                    found_window = matches[0]
                    break
                
                # Also check by PID and children (for traditional apps)
                matches = find_windows(pid=pid)
                if matches:
                    found_window = matches[0]
                    break
                    
                try:
                    p = psutil.Process(pid)
                    children = p.children(recursive=True)
                    for child in children:
                        matches = find_windows(pid=child.pid)
                        if matches:
                            found_window = matches[0]
                            break
                except psutil.NoSuchProcess:
                    pass # Process exited - that's okay for UWP stubs
                    
                if found_window:
                    break
                    
                time.sleep(0.5)
            
            if found_window:
                # Create and bind AppHandle with ACTUAL window PID (not stub PID)
                # This is critical: found_window["pid"] is the REAL process owning the window
                handle = AppHandle.create(app_name, " ".join(full_cmd))
                handle.bind_window(
                    hwnd=found_window["hwnd"],
                    pid=found_window["pid"],  # REAL PID, not stub!
                    title=found_window["title"]
                )
                HandleRegistry.register(handle)
                
                return {
                    "status": "success",
                    "pid": pid,  # Legacy: stub PID (for backward compat)
                    "window": {
                        "title": found_window["title"],
                        "hwnd": found_window["hwnd"]
                    },
                    "app_handle": handle.to_dict()  # NEW: Full handle
                }
            else:
                return {
                    "status": "error",
                    "error": "Timeout waiting for window",
                    "pid": pid
                }
            
        except FileNotFoundError:
             return {
                "status": "error",
                "error": f"Executable not found: {executable}"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": f"Launch failed: {str(e)}"
            }
