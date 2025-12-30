"""Screenshot tool - deterministic Windows screenshot"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from ...base import Tool


class TakeScreenshot(Tool):
    """Take a screenshot on Windows"""
    
    @property
    def name(self) -> str:
        return "system.display.take_screenshot"
    
    @property
    def description(self) -> str:
        return "Takes a screenshot and saves it to the specified location"
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "save_location": {
                    "type": "string",
                    "enum": ["desktop", "current", "custom"],
                    "default": "desktop",
                    "description": "Where to save the screenshot"
                },
                "custom_path": {
                    "type": "string",
                    "description": "Custom path if save_location is 'custom'"
                }
            },
            "required": []
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute screenshot capture"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        save_location = args.get("save_location", "desktop")
        
        # Determine save path
        if save_location == "desktop":
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.exists(desktop):
                desktop = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
            save_dir = desktop
        elif save_location == "current":
            save_dir = os.getcwd()
        elif save_location == "custom":
            custom_path = args.get("custom_path")
            if not custom_path:
                raise ValueError("custom_path required when save_location is 'custom'")
            save_dir = os.path.dirname(custom_path) or os.getcwd()
            if not os.path.exists(save_dir):
                os.makedirs(save_dir, exist_ok=True)
        else:
            save_dir = os.getcwd()
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = os.path.join(save_dir, filename)
        
        # Use PowerShell to take screenshot
        ps_command = f"""
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing

        $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)

        $bitmap.Save("{filepath}", [System.Drawing.Imaging.ImageFormat]::Png)

        $graphics.Dispose()
        $bitmap.Dispose()
        """
        
        try:
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return {
                    "status": "error",
                    "error": f"PowerShell execution failed: {result.stderr}",
                    "path": None
                }
            
            if os.path.exists(filepath):
                return {
                    "status": "success",
                    "path": filepath,
                    "filename": filename
                }
            else:
                return {
                    "status": "error",
                    "error": "Screenshot file was not created",
                    "path": None
                }
                
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "error": "Screenshot operation timed out",
                "path": None
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "path": None
            }

