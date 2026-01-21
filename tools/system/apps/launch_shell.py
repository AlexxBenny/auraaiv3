"""Tool: system.apps.launch.shell

OS-native shell launch for GUI applications.
Uses os.startfile() which delegates resolution to Windows Shell.

Category: system
Risk Level: medium
Side Effects: changes_focus, changes_ui_state, launches_process

WHEN TO USE:
- Launching GUI applications by name (chrome, notepad, spotify)
- When no command-line arguments are needed
- Default choice for user-facing application launches

WHEN NOT TO USE:
- CLI tools that need arguments (use system.apps.launch.path instead)
- When explicit executable path is provided
"""

import time
from typing import Dict, Any
from tools.base import Tool
from tools.system.apps.utils import find_windows
from tools.system.apps.app_handle import AppHandle, HandleRegistry
from tools.system.apps.resolver import execute_shell_launch


class LaunchAppShell(Tool):
    """Launch GUI application via OS shell (os.startfile)"""
    
    @property
    def name(self) -> str:
        return "system.apps.launch.shell"
    
    @property
    def description(self) -> str:
        return (
            "Launches a GUI application using OS-native shell resolution. "
            "Works with apps registered in Windows (Chrome, Spotify, etc.). "
            "Do NOT use for CLI tools with arguments."
        )
    
    @property
    def risk_level(self) -> str:
        return "medium"
        
    @property
    def side_effects(self) -> list[str]:
        return ["changes_focus", "changes_ui_state", "resource_usage"]
        
    @property
    def stabilization_time_ms(self) -> int:
        return 2000
        
    @property
    def reversible(self) -> bool:
        return True

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
                    "description": "Name of application to launch (e.g., 'chrome', 'notepad', 'spotify')"
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
        """Execute shell launch using os.startfile()"""
        if not self.validate_args(args):
            return {"status": "error", "error": "Invalid arguments"}
            
        app_name = args["app_name"]
        wait = args.get("wait_for_window", True)
        timeout_sec = args.get("timeout_ms", 10000) / 1000.0
        
        # Execute via os.startfile
        success, error = execute_shell_launch(app_name)
        if not success:
            return {
                "status": "error",
                "error": error,
                "error_type": "environment",
                "launch_method": "shell"
            }
        
        # Wait for window if requested
        if wait:
            return self._wait_for_window(app_name, timeout_sec)
        else:
            handle = AppHandle.create(app_name, f"shell:{app_name}")
            HandleRegistry.register(handle)
            return {
                "status": "success",
                "launch_method": "shell",
                "app_handle": handle.to_dict(),
                "note": "Launched via OS shell, did not wait for window"
            }
    
    def _wait_for_window(self, app_name: str, timeout_sec: float) -> Dict[str, Any]:
        """Wait for window after shell launch"""
        start_time = time.time()
        found_window = None
        
        while time.time() - start_time < timeout_sec:
            matches = find_windows(app_name=app_name)
            if matches:
                found_window = matches[0]
                break
            time.sleep(0.5)
        
        if found_window:
            handle = AppHandle.create(app_name, f"shell:{app_name}")
            handle.bind_window(
                hwnd=found_window["hwnd"],
                pid=found_window["pid"],
                title=found_window["title"]
            )
            HandleRegistry.register(handle)
            
            return {
                "status": "success",
                "launch_method": "shell",
                "window": {
                    "title": found_window["title"],
                    "hwnd": found_window["hwnd"]
                },
                "app_handle": handle.to_dict()
            }
        else:
            return {
                "status": "partial",
                "launch_method": "shell",
                "note": "Application launched but window not detected within timeout"
            }
