"""Tool: system.power.shutdown

Shuts down the system.

Category: action
Risk Level: HIGH
Side Effects: system_shutdown, data_loss_possible

**CONFIRMATION GATE REQUIRED**
- Must pass confirm=true to execute
- Hard fails without confirmation
- Same pattern as empty_recycle_bin

This is the most destructive power action.
"""

import logging
import subprocess
from typing import Dict, Any

from ...base import Tool


class Shutdown(Tool):
    """Shut down the system
    
    REQUIRES CONFIRMATION GATE - will refuse without confirm=true
    """
    
    @property
    def name(self) -> str:
        return "system.power.shutdown"
    
    @property
    def description(self) -> str:
        return "Shuts down the system (REQUIRES confirm=true)"
    
    @property
    def risk_level(self) -> str:
        return "high"
    
    @property
    def side_effects(self) -> list[str]:
        return ["system_shutdown", "data_loss_possible"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 0
    
    @property
    def reversible(self) -> bool:
        return False  # Cannot undo shutdown
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return True
    
    @property
    def requires_focus(self) -> bool:
        return False
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return True
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "confirm": {
                    "type": "boolean",
                    "description": "Must be true to confirm shutdown. This is a safety gate."
                },
                "delay_seconds": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 300,
                    "default": 0,
                    "description": "Optional delay before shutdown (0-300 seconds)"
                }
            },
            "required": ["confirm"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute shutdown with confirmation gate"""
        confirm = args.get("confirm")
        delay = args.get("delay_seconds", 0)
        
        # ===== CONFIRMATION GATE =====
        if confirm is not True:
            logging.warning("Shutdown BLOCKED - confirm not provided or not true")
            return {
                "status": "refused",
                "error": "Shutdown requires explicit confirmation. Pass confirm=true to proceed.",
                "required": {"confirm": True}
            }
        
        # Validate delay
        if delay < 0 or delay > 300:
            return {
                "status": "error",
                "error": f"Delay must be 0-300 seconds, got {delay}"
            }
        
        try:
            # Windows shutdown command
            cmd = ["shutdown", "/s", "/t", str(delay)]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                return {
                    "status": "error",
                    "error": f"Shutdown command failed: {result.stderr}"
                }
            
            logging.warning(f"System shutdown initiated (delay={delay}s)")
            return {
                "status": "success",
                "action": "shutdown",
                "delay_seconds": delay,
                "warning": "System will shut down" + (f" in {delay} seconds" if delay > 0 else " immediately")
            }
            
        except Exception as e:
            logging.error(f"Failed to shutdown: {e}")
            return {
                "status": "error",
                "error": f"Failed to shutdown: {str(e)}"
            }
