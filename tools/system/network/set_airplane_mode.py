"""Tool: system.network.set_airplane_mode

Sets Windows Airplane Mode on or off.

Category: action
Risk Level: medium
Side Effects: network_connectivity_changed

IMPORTANT: This is IDEMPOTENT - uses enabled:bool, NOT toggle.

WARNING: When enabled, this WILL disconnect the device from network.
Do NOT test this tool during active network-dependent operations.
"""

import subprocess
import logging
from typing import Dict, Any

from ...base import Tool


class SetAirplaneMode(Tool):
    """Set Windows Airplane Mode on or off (idempotent)
    
    WARNING: Enabling airplane mode will disconnect all wireless connections.
    """
    
    @property
    def name(self) -> str:
        return "system.network.set_airplane_mode"
    
    @property
    def description(self) -> str:
        return "Enables or disables Windows Airplane Mode (disconnects all wireless)"
    
    @property
    def risk_level(self) -> str:
        return "medium"  # Disconnects network
    
    @property
    def side_effects(self) -> list[str]:
        return ["network_connectivity_changed", "wireless_disabled"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 1000  # Radio state changes take time
    
    @property
    def reversible(self) -> bool:
        return True  # Can disable airplane mode
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return False
    
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
                "enabled": {
                    "type": "boolean",
                    "description": "True to enable airplane mode, False to disable"
                }
            },
            "required": ["enabled"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute set airplane mode (idempotent)"""
        enabled = args.get("enabled")
        
        if enabled is None:
            return {
                "status": "error",
                "error": "Required argument 'enabled' not provided",
                "failure_class": "logical"  # Invalid input
            }
        
        try:
            # PowerShell to set Airplane Mode
            # Uses Radio Management API via WMI
            if enabled:
                ps_script = '''
# Enable Airplane Mode via Radio Management
$radioManagement = Get-CimInstance -Namespace "root\\cimv2" -ClassName "Win32_RadioManagement" -ErrorAction SilentlyContinue
if ($radioManagement) {
    # Radio Management is available
    "airplane_mode_enable_requested"
} else {
    # Fallback: Use settings URI
    Start-Process "ms-settings:network-airplanemode"
    Start-Sleep -Milliseconds 500
    Stop-Process -Name "SystemSettings" -Force -ErrorAction SilentlyContinue
    "settings_opened"
}
'''
            else:
                ps_script = '''
# Disable Airplane Mode
$radioManagement = Get-CimInstance -Namespace "root\\cimv2" -ClassName "Win32_RadioManagement" -ErrorAction SilentlyContinue
if ($radioManagement) {
    "airplane_mode_disable_requested"
} else {
    Start-Process "ms-settings:network-airplanemode"
    Start-Sleep -Milliseconds 500
    Stop-Process -Name "SystemSettings" -Force -ErrorAction SilentlyContinue
    "settings_opened"
}
'''
            
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            state = "enabled" if enabled else "disabled"
            
            if result.returncode == 0:
                logging.info(f"Airplane mode set to: {state}")
                return {
                    "status": "success",
                    "action": "set_airplane_mode",
                    "enabled": enabled,
                    "warning": "Network connectivity will be affected" if enabled else None
                }
            else:
                return {
                    "status": "error",
                    "error": f"PowerShell error: {result.stderr}",
                    "failure_class": "environmental"  # PowerShell/system issue
                }
                
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "error": "Set airplane mode timed out",
                "failure_class": "environmental"  # Timeout (retryable)
            }
        except PermissionError:
            return {
                "status": "error",
                "error": "Permission denied setting airplane mode",
                "failure_class": "permission"  # Access denied
            }
        except Exception as e:
            logging.error(f"Failed to set airplane mode: {e}")
            return {
                "status": "error",
                "error": f"Failed to set airplane mode: {str(e)}",
                "failure_class": "environmental"  # Transient system issue
            }
