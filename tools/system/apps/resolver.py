"""Application Resolution - Two-Tier Execution Model

PRINCIPLE: AURA must NOT attempt to discover executable paths for GUI apps.
           AURA must delegate GUI application resolution to the OS shell.

Tier 1: OS-Native GUI Launch (os.startfile)
    - Used for GUI applications without command-line arguments
    - Delegates resolution entirely to Windows Shell
    - Works with App Paths, Start Menu, file associations
    - NO path discovery, NO registry scraping

Tier 2: PATH-Based CLI Launch (shutil.which + subprocess)
    - Used for CLI tools WITH arguments (python, git, npm)
    - Uses standard PATH resolution
    - Fails cleanly if not found

This is the industry-correct approach for Windows application launching.
"""

import os
import sys
import shutil
import logging
from typing import Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum


class LaunchMethod(Enum):
    """How the application was/should be launched"""
    SHELL = "shell"        # os.startfile (Tier 1)
    PATH = "path"          # shutil.which + subprocess (Tier 2)
    EXPLICIT = "explicit"  # User provided full path
    FAILED = "failed"      # Could not resolve


class ErrorType(Enum):
    """Classification of launch errors"""
    NONE = "none"
    ENVIRONMENT = "environment"  # App not installed, not in PATH
    PERMISSION = "permission"    # Access denied
    TOOL = "tool"                # Launch mechanism failed


@dataclass
class LaunchStrategy:
    """Result of determining how to launch an application"""
    method: LaunchMethod
    executable: Optional[str]  # Path for PATH/EXPLICIT, app_name for SHELL
    use_shell_execute: bool    # True = os.startfile, False = subprocess
    error: Optional[str] = None
    error_type: ErrorType = ErrorType.NONE


def determine_launch_strategy(
    app_name: str,
    path: Optional[str] = None,
    args: Optional[List[str]] = None
) -> LaunchStrategy:
    """
    Determine the correct launch strategy for an application.
    
    Decision Logic:
    1. If explicit path provided → use it directly (subprocess)
    2. If no args → Tier 1: OS-native shell (os.startfile)
    3. If args present → Tier 2: PATH resolution (shutil.which + subprocess)
    
    Args:
        app_name: Application name (e.g., "chrome", "python")
        path: Optional explicit path to executable
        args: Optional command-line arguments
        
    Returns:
        LaunchStrategy with method and executable
    """
    args = args or []
    
    # Case 1: Explicit path provided
    if path:
        if os.path.exists(path):
            return LaunchStrategy(
                method=LaunchMethod.EXPLICIT,
                executable=path,
                use_shell_execute=False
            )
        else:
            return LaunchStrategy(
                method=LaunchMethod.FAILED,
                executable=None,
                use_shell_execute=False,
                error=f"Explicit path does not exist: {path}",
                error_type=ErrorType.ENVIRONMENT
            )
    
    # Case 2: No arguments → Tier 1 (OS-native shell launch)
    # This is the CORRECT approach for GUI applications
    if not args:
        logging.debug(f"Tier 1: Using os.startfile for '{app_name}' (no args)")
        return LaunchStrategy(
            method=LaunchMethod.SHELL,
            executable=app_name,  # Let OS resolve
            use_shell_execute=True
        )
    
    # Case 3: Arguments present → Tier 2 (PATH-based CLI launch)
    logging.debug(f"Tier 2: Using PATH resolution for '{app_name}' (has args)")
    
    # Try to find in PATH
    resolved = _resolve_via_path(app_name)
    if resolved:
        return LaunchStrategy(
            method=LaunchMethod.PATH,
            executable=resolved,
            use_shell_execute=False
        )
    
    # PATH resolution failed
    return LaunchStrategy(
        method=LaunchMethod.FAILED,
        executable=None,
        use_shell_execute=False,
        error=f"'{app_name}' not found in PATH. For GUI apps, remove arguments to use OS-native launch.",
        error_type=ErrorType.ENVIRONMENT
    )


def _resolve_via_path(app_name: str) -> Optional[str]:
    """
    Resolve application via system PATH.
    
    Only used for Tier 2 (CLI tools with arguments).
    
    Args:
        app_name: Application name
        
    Returns:
        Full path if found, None otherwise
    """
    # Try exact name first
    path = shutil.which(app_name)
    if path:
        return path
    
    # On Windows, try with .exe extension
    if sys.platform == "win32" and not app_name.lower().endswith('.exe'):
        path = shutil.which(f"{app_name}.exe")
        if path:
            return path
    
    return None


def execute_shell_launch(app_name: str) -> Tuple[bool, Optional[str]]:
    """
    Execute Tier 1: OS-native shell launch.
    
    Uses os.startfile() which internally calls ShellExecuteEx.
    This is the CORRECT way to launch GUI applications on Windows.
    
    Args:
        app_name: Application name to launch
        
    Returns:
        (success, error_message)
    """
    try:
        os.startfile(app_name)
        logging.info(f"Shell launch successful: {app_name}")
        return True, None
    except FileNotFoundError:
        error = f"Application not found: '{app_name}'. Ensure it is installed."
        logging.warning(error)
        return False, error
    except OSError as e:
        # OSError can mean permission denied or other issues
        if "Access is denied" in str(e):
            error = f"Permission denied launching '{app_name}'"
            logging.warning(error)
            return False, error
        else:
            error = f"OS error launching '{app_name}': {e}"
            logging.warning(error)
            return False, error
