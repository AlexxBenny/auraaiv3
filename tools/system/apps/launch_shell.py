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
from pathlib import Path
from typing import Dict, Any, Optional, List
from tools.base import Tool
from tools.system.apps.utils import find_windows
from tools.system.apps.app_handle import AppHandle, HandleRegistry
from tools.system.apps.app_resolver import get_app_resolver, LaunchTarget, ResolutionMethod


# ===== App-specific launch configuration =====
# Loaded from config/apps.yaml - determines default args for browsers, etc.
# This logic lives HERE (not in app_resolver) per separation of concerns:
#   - AppResolver: finds WHAT to launch
#   - LaunchShell: decides HOW to launch it (args, flags, profiles)

def _load_app_config() -> Dict[str, Any]:
    """Load app-specific configuration from config/apps.yaml"""
    config_path = Path(__file__).parent.parent.parent.parent / "config" / "apps.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
                logging.debug(f"Loaded app config from {config_path}")
                return config
        except Exception as e:
            logging.warning(f"Failed to load app config: {e}")
    return {}


# Load config at module level (cached)
_APP_CONFIG: Optional[Dict[str, Any]] = None

def _get_app_config() -> Dict[str, Any]:
    """Get cached app config (loads lazily)"""
    global _APP_CONFIG
    if _APP_CONFIG is None:
        _APP_CONFIG = _load_app_config()
    return _APP_CONFIG


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
        
        # Apply app-specific args (e.g., browser profile flags)
        # NOTE: Args are only applied to executable targets, not protocols
        target = self._apply_app_args(app_name, target)
        
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
    
    def _apply_app_args(self, app_name: str, target: LaunchTarget) -> LaunchTarget:
        """Apply app-specific launch arguments from config.
        
        SAFETY RULE: Args are ONLY applied to executable targets.
        Protocol targets (spotify:, ms-settings:, shell:AppsFolder) do NOT accept CLI args.
        
        Args:
            app_name: Original app name requested
            target: Resolved launch target
            
        Returns:
            LaunchTarget with args populated (for executables only)
        """
        # Only executable targets can have args
        if target.target_type != "executable":
            return target
        
        config = _get_app_config()
        browsers = config.get("browsers", {})
        
        # Check each browser config for a match
        for browser_name, browser_config in browsers.items():
            patterns = browser_config.get("executable_patterns", [])
            default_args = browser_config.get("default_args", [])
            
            if not default_args:
                continue
            
            # Match by app name or executable patterns
            target_value_lower = target.value.lower() if target.value else ""
            app_name_lower = app_name.lower()
            
            is_match = (
                app_name_lower == browser_name or
                any(p.lower() in target_value_lower for p in patterns)
            )
            
            if is_match:
                logging.info(f"Applying {browser_name} args: {default_args}")
                return LaunchTarget(
                    target_type=target.target_type,
                    value=target.value,
                    resolution_method=target.resolution_method,
                    details=target.details,
                    args=default_args
                )
        
        return target
    
    def _execute_target(self, target: LaunchTarget) -> tuple[bool, str | None]:
        """Execute the resolved launch target.
        
        SAFETY RULE: Args are ONLY passed to executable targets.
        Protocol and shell targets ignore args.
        
        Returns:
            (success, error_message)
        """
        try:
            if target.target_type == "protocol":
                # Protocol URIs do NOT accept CLI arguments
                if target.args:
                    logging.debug(f"Ignoring args for protocol target: {target.value}")
                os.startfile(target.value)
                logging.info(f"Launched protocol: {target.value}")
                return True, None
                
            elif target.target_type == "executable":
                # Build command with optional args
                cmd = [target.value]
                if target.args:
                    cmd.extend(target.args)
                    logging.info(f"Launching {target.value} with args: {target.args}")
                
                subprocess.Popen(
                    cmd,
                    shell=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                logging.info(f"Launched executable: {target.value}")
                return True, None
                
            elif target.target_type == "shell":
                # Shell targets (including AppsFolder) do NOT accept CLI arguments
                if target.args:
                    logging.debug(f"Ignoring args for shell target: {target.value}")
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
