"""Tool: system.apps.launch.shell

OS-native shell launch for GUI applications.
Uses multi-strategy resolution via AppResolver, then launches appropriately.

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

import os
import time
import subprocess
import logging
from typing import Dict, Any
from tools.base import Tool
from tools.system.apps.utils import find_windows
from tools.system.apps.app_handle import AppHandle, HandleRegistry
from tools.system.apps.app_resolver import get_app_resolver, LaunchTarget, ResolutionMethod


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
        """Execute app launch using multi-strategy resolution."""
        if not self.validate_args(args):
            return {"status": "error", "error": "Invalid arguments"}
            
        app_name = args["app_name"]
        wait = args.get("wait_for_window", True)
        timeout_sec = args.get("timeout_ms", 10000) / 1000.0
        
        # Resolve via multi-strategy pipeline
        resolver = get_app_resolver()
        target = resolver.resolve(app_name)
        
        logging.info(f"Resolved '{app_name}' via {target.resolution_method.value} -> {target.value}")
        
        # Execute based on target type
        success, error = self._execute_target(target)
        if not success:
            return {
                "status": "error",
                "error": error,
                "error_type": "environment",
                "launch_method": target.resolution_method.value,
                "resolution_details": target.details
            }
        
        # Wait for window if requested
        if wait:
            result = self._wait_for_window(app_name, timeout_sec)
            result["resolution_method"] = target.resolution_method.value
            return result
        else:
            handle = AppHandle.create(app_name, f"{target.resolution_method.value}:{target.value}")
            HandleRegistry.register(handle)
            return {
                "status": "success",
                "launch_method": target.resolution_method.value,
                "resolution_target": target.value,
                "app_handle": handle.to_dict(),
                "note": f"Launched via {target.resolution_method.value}, did not wait for window"
            }
    
    def _execute_target(self, target: LaunchTarget) -> tuple[bool, str | None]:
        """Execute the resolved launch target.
        
        Returns:
            (success, error_message)
        """
        try:
            if target.target_type == "protocol":
                # Launch via protocol URI (e.g., spotify:)
                os.startfile(target.value)
                logging.info(f"Launched protocol: {target.value}")
                return True, None
                
            elif target.target_type == "executable":
                # Launch executable directly
                subprocess.Popen(
                    [target.value],
                    shell=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                logging.info(f"Launched executable: {target.value}")
                return True, None
                
            elif target.target_type == "shell":
                # Fallback to os.startfile with app name
                os.startfile(target.value)
                logging.info(f"Launched via shell: {target.value}")
                return True, None
                
            else:
                return False, f"Unknown target type: {target.target_type}"
                
        except FileNotFoundError:
            error = (
                f"No valid launch method found for '{target.value}'.\n"
                f"Tried: protocol, App Paths registry, Start Menu, common install paths.\n"
                f"Resolution method: {target.resolution_method.value}"
            )
            logging.warning(error)
            return False, error
            
        except OSError as e:
            if "Access is denied" in str(e):
                error = f"Permission denied launching '{target.value}'"
            else:
                error = f"OS error launching '{target.value}': {e}"
            logging.warning(error)
            return False, error
            
        except Exception as e:
            error = f"Launch failed for '{target.value}': {e}"
            logging.error(error)
            return False, error
    
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
