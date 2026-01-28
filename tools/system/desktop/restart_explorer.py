"""Tool: system.desktop.restart_explorer

Restarts Windows Explorer (kills and relaunches).

Category: action
Risk Level: medium
Side Effects: explorer_restarted, taskbar_reset

IMPORTANT: Returns cooldown_ms to block subsequent tools.
"""

import subprocess
import time
import logging
from typing import Dict, Any

from ...base import Tool


class RestartExplorer(Tool):
    """Restart Windows Explorer"""
    
    @property
    def name(self) -> str:
        return "system.desktop.restart_explorer"
    
    @property
    def description(self) -> str:
        return "Restarts Windows Explorer (taskbar, start menu, desktop shell)"
    
    @property
    def risk_level(self) -> str:
        return "medium"  # Disrupts desktop UI temporarily
    
    @property
    def side_effects(self) -> list[str]:
        return ["explorer_restarted", "taskbar_reset"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 2000  # Explorer restart is slow
    
    @property
    def reversible(self) -> bool:
        return True  # Explorer restarts automatically
    
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
            "properties": {},
            "required": []
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute restart explorer"""
        try:
            logging.info("Restarting Windows Explorer...")
            
            # Kill explorer.exe
            subprocess.run(
                ["taskkill", "/F", "/IM", "explorer.exe"],
                capture_output=True,
                timeout=5
            )
            
            # Brief pause
            time.sleep(0.5)
            
            # Restart explorer.exe
            subprocess.Popen(
                ["explorer.exe"],
                shell=False,
                creationflags=subprocess.DETACHED_PROCESS
            )
            
            # Wait for stabilization
            time.sleep(self.stabilization_time_ms / 1000.0)
            
            logging.info("Explorer restarted successfully")
            return {
                "status": "success",
                "action": "restart_explorer",
                "cooldown_ms": 2000,  # Block subsequent tools
                "note": "Taskbar and desktop shell restarted"
            }
            
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "error": "Failed to kill explorer (timeout)"
            }
        except Exception as e:
            logging.error(f"Failed to restart explorer: {e}")
            return {
                "status": "error",
                "error": f"Failed to restart explorer: {str(e)}"
            }
