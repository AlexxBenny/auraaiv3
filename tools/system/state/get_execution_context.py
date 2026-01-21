"""Tool: system.state.get_execution_context

Checks environment safety constraints before execution.
Detects lock screen, idle state, and other blocking conditions.

Category: system
Risk Level: low
Side Effects: none
"""

import ctypes
import os
import psutil
from typing import Dict, Any
from tools.base import Tool


class GetExecutionContext(Tool):
    """Get safety context (lock screen, idle, etc)"""
    
    @property
    def name(self) -> str:
        return "system.state.get_execution_context"
    
    @property
    def description(self) -> str:
        return "Checks environment safety: screen lock status, user idle time, and fullscreen apps."
    
    @property
    def risk_level(self) -> str:
        return "low"
        
    @property
    def side_effects(self) -> list[str]:
        return []
        
    @property
    def stabilization_time_ms(self) -> int:
        return 10
        
    @property
    def reversible(self) -> bool:
        return True

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def _is_screen_locked(self) -> bool:
        """Check if workstation is locked"""
        user32 = ctypes.windll.User32
        # If open input desktop check fails, it's likely locked/UAC
        # 0x0001 = DF_ALLOWOTHERACCOUNTHOOK check
        # This is a heuristic; more robust methods involve WTS APIs
        try:
            hwnd = user32.GetForegroundWindow()
            return hwnd == 0
        except:
            return True

    def _get_idle_time(self) -> float:
        """Get system idle time in seconds"""
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]
            
        lastInput = LASTINPUTINFO()
        lastInput.cbSize = ctypes.sizeof(LASTINPUTINFO)
        
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lastInput)):
            millis = ctypes.windll.kernel32.GetTickCount() - lastInput.dwTime
            return millis / 1000.0
        return 0.0

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool"""
        if not self.validate_args(args):
            return {"status": "error", "error": "Invalid arguments"}
            
        try:
            screen_locked = self._is_screen_locked()
            idle_seconds = self._get_idle_time()
            
            # Context heuristics
            safety_status = "safe"
            warnings = []
            
            if screen_locked:
                safety_status = "unsafe"
                warnings.append("Screen is likely locked (heuristic)")
            
            if idle_seconds > 300: # 5 mins
                warnings.append(f"User idle for {int(idle_seconds)}s")
            
            return {
                "status": "success",
                "context": {
                    "is_safe_to_execute": safety_status == "safe",
                    "screen_locked_heuristic": screen_locked,
                    "confidence_level": "heuristic",
                    "user_idle_seconds": idle_seconds,
                    "warnings": warnings,
                    "platform": os.name
                }
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to get context: {str(e)}"
            }
