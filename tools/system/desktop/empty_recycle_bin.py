"""Tool: system.desktop.empty_recycle_bin

Permanently deletes all files in the Recycle Bin.

Category: action
Risk Level: HIGH
Side Effects: permanent_data_loss

CRITICAL: Requires confirm=true argument as a safety gate.
Tool REFUSES to execute without explicit confirmation.
"""

import ctypes
import logging
from typing import Dict, Any

from ...base import Tool


class EmptyRecycleBin(Tool):
    """Empty the Windows Recycle Bin
    
    SAFETY: Requires confirm=true to execute.
    This is a CONFIRMATION GATE - no exceptions.
    """
    
    @property
    def name(self) -> str:
        return "system.desktop.empty_recycle_bin"
    
    @property
    def description(self) -> str:
        return "Permanently deletes all files in the Recycle Bin. REQUIRES confirm=true."
    
    @property
    def risk_level(self) -> str:
        return "high"  # Permanent data deletion
    
    @property
    def side_effects(self) -> list[str]:
        return ["permanent_data_loss", "recycle_bin_emptied"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 500
    
    @property
    def reversible(self) -> bool:
        return False  # DATA IS PERMANENTLY DELETED
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return False  # Silent operation
    
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
                    "description": "Must be true to permanently delete files. Safety gate."
                }
            },
            "required": ["confirm"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute empty recycle bin WITH CONFIRMATION GATE"""
        confirm = args.get("confirm")
        
        # =====================================================================
        # CONFIRMATION GATE - NON-NEGOTIABLE
        # =====================================================================
        if confirm is not True:
            logging.warning("Empty recycle bin BLOCKED - confirm not True")
            return {
                "status": "refused",
                "error": "SAFETY GATE: Empty recycle bin requires confirm=true. "
                         "This action permanently deletes all files in the Recycle Bin.",
                "required": {"confirm": True}
            }
        
        try:
            # SH_EMPTY_RECYCLE_BIN flags
            # SHERB_NOCONFIRMATION = 0x00000001 - No dialog
            # SHERB_NOPROGRESSUI = 0x00000002 - No progress UI
            # SHERB_NOSOUND = 0x00000004 - No sound
            flags = 0x00000001 | 0x00000002 | 0x00000004
            
            # NULL path = all drives
            result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
            
            if result == 0:
                logging.info("Recycle Bin emptied successfully")
                return {
                    "status": "success",
                    "action": "empty_recycle_bin",
                    "warning": "All files permanently deleted"
                }
            elif result == -2147418113:  # 0x8000FFFF - Operation completed (bin was empty)
                logging.info("Recycle Bin was already empty")
                return {
                    "status": "success",
                    "action": "empty_recycle_bin",
                    "note": "Recycle Bin was already empty"
                }
            else:
                return {
                    "status": "error",
                    "error": f"SHEmptyRecycleBinW returned: {result}"
                }
                
        except Exception as e:
            logging.error(f"Failed to empty recycle bin: {e}")
            return {
                "status": "error",
                "error": f"Failed to empty recycle bin: {str(e)}"
            }
