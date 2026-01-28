"""Tool: system.desktop.toggle_icons

Toggles desktop icons visibility.

Category: action
Risk Level: low
Side Effects: desktop_state_changed

Uses Windows Shell API via PowerShell.
"""

import subprocess
import logging
from typing import Dict, Any

from ...base import Tool


class ToggleIcons(Tool):
    """Toggle desktop icons visibility"""
    
    @property
    def name(self) -> str:
        return "system.desktop.toggle_icons"
    
    @property
    def description(self) -> str:
        return "Toggles the visibility of desktop icons (show/hide)"
    
    @property
    def risk_level(self) -> str:
        return "low"
    
    @property
    def side_effects(self) -> list[str]:
        return ["desktop_state_changed"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 200
    
    @property
    def reversible(self) -> bool:
        return True  # Toggle again to reverse
    
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
        """Execute toggle desktop icons"""
        try:
            # PowerShell script to toggle desktop icons
            # This uses the HideIcons registry value and refreshes the desktop
            ps_script = '''
$path = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced"
$current = (Get-ItemProperty -Path $path -Name "HideIcons" -ErrorAction SilentlyContinue).HideIcons
if ($current -eq 1) {
    Set-ItemProperty -Path $path -Name "HideIcons" -Value 0
    $result = "shown"
} else {
    Set-ItemProperty -Path $path -Name "HideIcons" -Value 1
    $result = "hidden"
}
# Refresh desktop
$shell = New-Object -ComObject Shell.Application
$shell.ToggleDesktop()
$shell.ToggleDesktop()
$result
'''
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                new_state = result.stdout.strip()
                logging.info(f"Desktop icons toggled: {new_state}")
                return {
                    "status": "success",
                    "action": "toggle_icons",
                    "icons_state": new_state
                }
            else:
                return {
                    "status": "error",
                    "error": f"PowerShell error: {result.stderr}"
                }
                
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "error": "Toggle icons timed out"
            }
        except Exception as e:
            logging.error(f"Failed to toggle icons: {e}")
            return {
                "status": "error",
                "error": f"Failed to toggle icons: {str(e)}"
            }
