"""Effect Verification - Deterministic verifiers for effect postconditions

This module provides SIDE-EFFECT FREE verification of postconditions.
Verifiers are SENSORS, not actuators.

CRITICAL CONSTRAINTS:
- Must only READ system state
- Must NEVER mutate state
- Must NEVER retry tools
- Must NEVER log success/failure implicitly
- Must return VerificationResult only

Two-tier evaluation:
- Tier 1: Deterministic verifiers (this module)
- Tier 2: LLM judgment (only for CUSTOM type, handled elsewhere)

Phase 1: Verification primitives (no runtime integration)
"""

import os
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, Callable

from .schema import PostconditionType


@dataclass
class VerificationResult:
    """
    Result of a postcondition verification.
    
    Attributes:
        satisfied: Whether the postcondition is met
        evidence: Why we believe satisfied is True/False
        verification_method: "deterministic" or "llm"
        error: Optional error message if verification itself failed
    """
    satisfied: bool
    evidence: str
    verification_method: str = "deterministic"
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "satisfied": self.satisfied,
            "evidence": self.evidence,
            "verification_method": self.verification_method
        }
        if self.error:
            result["error"] = self.error
        return result


# =============================================================================
# TIER 1: DETERMINISTIC VERIFIERS
# =============================================================================
# Each verifier:
# - Takes params dict
# - Returns VerificationResult
# - Has NO side effects
# - Does NOT mutate state
# - Does NOT retry anything
# =============================================================================


def verify_process_running(params: Dict[str, Any]) -> VerificationResult:
    """
    Verify that a process is running.
    
    Params:
        process: str - Process name to check (e.g., "chrome", "notepad")
        window_visible: bool - Optional, also check for visible window
    
    Returns:
        VerificationResult with process state evidence
    """
    process_name = params.get("process", "")
    if not process_name:
        return VerificationResult(
            satisfied=False,
            evidence="No process name provided",
            error="Missing 'process' parameter"
        )
    
    try:
        import psutil
        
        # Search for matching process
        found_processes = []
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                if process_name.lower() in proc.info['name'].lower():
                    found_processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if found_processes:
            pids = [p['pid'] for p in found_processes]
            evidence = f"Process '{process_name}' running (PIDs: {pids[:3]})"
            
            # Optional: Check window visibility
            if params.get("window_visible"):
                evidence += " (window visibility check skipped - requires win32gui)"
            
            return VerificationResult(satisfied=True, evidence=evidence)
        else:
            return VerificationResult(
                satisfied=False,
                evidence=f"Process '{process_name}' not found in running processes"
            )
            
    except ImportError:
        return VerificationResult(
            satisfied=False,
            evidence="Cannot verify: psutil not available",
            error="psutil module not installed"
        )
    except Exception as e:
        return VerificationResult(
            satisfied=False,
            evidence=f"Verification error: {str(e)}",
            error=str(e)
        )


def verify_window_visible(params: Dict[str, Any]) -> VerificationResult:
    """
    Verify that a window is visible.
    
    Params:
        title: str - Window title substring to match
        process: str - Optional process name to filter
    
    Returns:
        VerificationResult with window state evidence
    """
    title = params.get("title", "")
    process_name = params.get("process", "")
    
    if not title and not process_name:
        return VerificationResult(
            satisfied=False,
            evidence="No window identifier provided",
            error="Missing 'title' or 'process' parameter"
        )
    
    try:
        # Windows-specific implementation
        if os.name == 'nt':
            import win32gui
            
            matching_windows = []
            
            def enum_callback(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    window_title = win32gui.GetWindowText(hwnd)
                    if title and title.lower() in window_title.lower():
                        matching_windows.append(window_title)
                    elif process_name and process_name.lower() in window_title.lower():
                        matching_windows.append(window_title)
            
            win32gui.EnumWindows(enum_callback, None)
            
            if matching_windows:
                return VerificationResult(
                    satisfied=True,
                    evidence=f"Window found: '{matching_windows[0][:50]}...'"
                )
            else:
                return VerificationResult(
                    satisfied=False,
                    evidence=f"No visible window matching '{title or process_name}'"
                )
        else:
            return VerificationResult(
                satisfied=False,
                evidence="Window verification only supported on Windows",
                error="Non-Windows OS"
            )
            
    except ImportError:
        return VerificationResult(
            satisfied=False,
            evidence="Cannot verify: win32gui not available",
            error="win32gui module not installed"
        )
    except Exception as e:
        return VerificationResult(
            satisfied=False,
            evidence=f"Verification error: {str(e)}",
            error=str(e)
        )


def verify_file_exists(params: Dict[str, Any]) -> VerificationResult:
    """
    Verify that a file exists.
    
    Params:
        path: str - File path to check
    
    Returns:
        VerificationResult with file existence evidence
    """
    path = params.get("path", "")
    if not path:
        return VerificationResult(
            satisfied=False,
            evidence="No file path provided",
            error="Missing 'path' parameter"
        )
    
    try:
        exists = os.path.exists(path)
        is_file = os.path.isfile(path) if exists else False
        
        if exists and is_file:
            size = os.path.getsize(path)
            return VerificationResult(
                satisfied=True,
                evidence=f"File exists: '{path}' ({size} bytes)"
            )
        elif exists:
            return VerificationResult(
                satisfied=False,
                evidence=f"Path exists but is not a file: '{path}'"
            )
        else:
            return VerificationResult(
                satisfied=False,
                evidence=f"File does not exist: '{path}'"
            )
            
    except Exception as e:
        return VerificationResult(
            satisfied=False,
            evidence=f"Verification error: {str(e)}",
            error=str(e)
        )


def verify_file_modified(params: Dict[str, Any]) -> VerificationResult:
    """
    Verify that a file was recently modified.
    
    Params:
        path: str - File path to check
        since_timestamp: float - Optional Unix timestamp to compare against
        max_age_seconds: int - Optional max age in seconds (default 60)
    
    Returns:
        VerificationResult with modification time evidence
    """
    import time
    
    path = params.get("path", "")
    if not path:
        return VerificationResult(
            satisfied=False,
            evidence="No file path provided",
            error="Missing 'path' parameter"
        )
    
    try:
        if not os.path.exists(path):
            return VerificationResult(
                satisfied=False,
                evidence=f"File does not exist: '{path}'"
            )
        
        mtime = os.path.getmtime(path)
        since = params.get("since_timestamp", time.time() - params.get("max_age_seconds", 60))
        
        if mtime >= since:
            return VerificationResult(
                satisfied=True,
                evidence=f"File modified at {time.ctime(mtime)}"
            )
        else:
            return VerificationResult(
                satisfied=False,
                evidence=f"File last modified at {time.ctime(mtime)} (too old)"
            )
            
    except Exception as e:
        return VerificationResult(
            satisfied=False,
            evidence=f"Verification error: {str(e)}",
            error=str(e)
        )


def verify_content_captured(params: Dict[str, Any]) -> VerificationResult:
    """
    Verify that content was captured (screenshot, recording, etc.).
    
    Params:
        location: str - "clipboard" or file path
        format: str - Expected format (image, text, etc.)
    
    Returns:
        VerificationResult with capture evidence
    """
    location = params.get("location", "")
    content_format = params.get("format", "")
    
    if location == "clipboard":
        # Clipboard verification (Windows)
        try:
            if os.name == 'nt':
                import win32clipboard
                win32clipboard.OpenClipboard()
                try:
                    # Check for image format
                    if content_format == "image":
                        has_image = win32clipboard.IsClipboardFormatAvailable(
                            win32clipboard.CF_DIB
                        )
                        if has_image:
                            return VerificationResult(
                                satisfied=True,
                                evidence="Image content present in clipboard"
                            )
                        else:
                            return VerificationResult(
                                satisfied=False,
                                evidence="No image content in clipboard"
                            )
                    else:
                        # Check for text
                        has_text = win32clipboard.IsClipboardFormatAvailable(
                            win32clipboard.CF_UNICODETEXT
                        )
                        if has_text:
                            return VerificationResult(
                                satisfied=True,
                                evidence="Text content present in clipboard"
                            )
                        else:
                            return VerificationResult(
                                satisfied=False,
                                evidence="No text content in clipboard"
                            )
                finally:
                    win32clipboard.CloseClipboard()
            else:
                return VerificationResult(
                    satisfied=False,
                    evidence="Clipboard verification only supported on Windows",
                    error="Non-Windows OS"
                )
        except ImportError:
            return VerificationResult(
                satisfied=False,
                evidence="Cannot verify clipboard: win32clipboard not available",
                error="win32clipboard module not installed"
            )
        except Exception as e:
            return VerificationResult(
                satisfied=False,
                evidence=f"Clipboard verification error: {str(e)}",
                error=str(e)
            )
    else:
        # File-based capture
        return verify_file_exists({"path": location})


def verify_state_changed(params: Dict[str, Any]) -> VerificationResult:
    """
    Verify that a system state changed.
    
    This is a generic verifier for state changes that don't fit other categories.
    Often requires LLM judgment, so returns inconclusive by default.
    
    Params:
        state_type: str - Type of state (volume, brightness, etc.)
        expected_value: Any - Expected value after change
    
    Returns:
        VerificationResult (usually inconclusive for deterministic tier)
    """
    state_type = params.get("state_type", "")
    
    # Most state changes require system-specific APIs
    # Return inconclusive to trigger Tier 2 (LLM judgment)
    return VerificationResult(
        satisfied=False,
        evidence=f"State change '{state_type}' requires LLM judgment",
        verification_method="requires_llm",
        error="Deterministic verification not available for this state type"
    )


# =============================================================================
# VERIFIER REGISTRY
# =============================================================================
# Maps PostconditionType to verifier function.
# Explicit mapping - no fallback magic.
# =============================================================================

DETERMINISTIC_VERIFIERS: Dict[str, Callable[[Dict[str, Any]], VerificationResult]] = {
    "process_running": verify_process_running,
    "window_visible": verify_window_visible,
    "file_exists": verify_file_exists,
    "file_modified": verify_file_modified,
    "content_captured": verify_content_captured,
    "state_changed": verify_state_changed,
    # NOTE: "custom" type is NOT in this registry
    # It explicitly requires LLM judgment (Tier 2)
}


def get_verifier(postcondition_type: str) -> Optional[Callable[[Dict[str, Any]], VerificationResult]]:
    """
    Get deterministic verifier for postcondition type.
    
    Returns None if type requires LLM judgment (Tier 2).
    This is EXPLICIT - no silent promotion to LLM tier.
    
    Args:
        postcondition_type: The postcondition type string
        
    Returns:
        Verifier function or None if LLM-only
    """
    return DETERMINISTIC_VERIFIERS.get(postcondition_type)


def is_deterministically_verifiable(postcondition_type: str) -> bool:
    """
    Check if a postcondition type can be verified deterministically.
    
    Args:
        postcondition_type: The postcondition type string
        
    Returns:
        True if Tier 1 verifier exists, False if requires Tier 2 (LLM)
    """
    return postcondition_type in DETERMINISTIC_VERIFIERS and postcondition_type != "custom"
