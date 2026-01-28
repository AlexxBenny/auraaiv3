"""Tool: system.power.sleep

Puts the system to sleep.

Category: action
Risk Level: medium (interrupts work)
Side Effects: system_sleep

Same pattern as lock - single power action.
"""

import logging
import subprocess
from typing import Dict, Any

from ...base import Tool


class Sleep(Tool):
    """Put the system to sleep"""
    
    @property
    def name(self) -> str:
        return "system.power.sleep"
    
    @property
    def description(self) -> str:
        return "Puts the system to sleep"
    
    @property
    def risk_level(self) -> str:
        return "medium"  # Interrupts current work
    
    @property
    def side_effects(self) -> list[str]:
        return ["system_sleep"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 0  # System sleeps immediately
    
    @property
    def reversible(self) -> bool:
        return True  # Wake up reverses
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return True  # Screen goes black
    
    @property
    def requires_focus(self) -> bool:
        return False
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return True  # Should only sleep from unlocked state
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute system sleep"""
        try:
            # Windows sleep command
            # SetSuspendState(Hibernate, ForceCritical, DisableWakeEvent)
            # 0,1,0 = Sleep (not hibernate), Force, Allow wake events
            result = subprocess.run(
                ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                capture_output=True, timeout=5
            )
            
            # If we get here, command executed (system may be waking up)
            logging.info("System sleep initiated")
            return {
                "status": "success",
                "action": "sleep"
            }
            
        except subprocess.TimeoutExpired:
            # This likely means sleep worked and we're waking up
            return {
                "status": "success",
                "action": "sleep",
                "note": "System was put to sleep"
            }
            
        except Exception as e:
            logging.error(f"Failed to sleep: {e}")
            return {
                "status": "error",
                "error": f"Failed to sleep: {str(e)}"
            }
