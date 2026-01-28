"""Tool: system.state.get_network_status

Gets current network connectivity status.

Category: query
Risk Level: low
Side Effects: none (read-only)

Returns structured data about WiFi and Ethernet connections.
"""

import logging
import socket
from typing import Dict, Any, List, Optional

from ...base import Tool


class GetNetworkStatus(Tool):
    """Get network connectivity status
    
    Returns detailed info about WiFi, Ethernet, and IP addresses.
    """
    
    @property
    def name(self) -> str:
        return "system.state.get_network_status"
    
    @property
    def description(self) -> str:
        return "Gets current network status (WiFi, Ethernet, IP addresses)"
    
    @property
    def risk_level(self) -> str:
        return "low"
    
    @property
    def side_effects(self) -> list[str]:
        return []  # Read-only
    
    @property
    def stabilization_time_ms(self) -> int:
        return 0
    
    @property
    def reversible(self) -> bool:
        return True
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return False
    
    @property
    def requires_focus(self) -> bool:
        return False
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return False
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def _get_wifi_info(self) -> Dict[str, Any]:
        """Get WiFi connection info using netsh"""
        import subprocess
        
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode != 0:
                return {"connected": False, "ssid": None, "ip": None}
            
            output = result.stdout
            
            # Check if connected
            if "State" not in output or "connected" not in output.lower():
                return {"connected": False, "ssid": None, "ip": None}
            
            # Parse SSID
            ssid = None
            for line in output.split('\n'):
                if 'SSID' in line and 'BSSID' not in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        ssid = parts[1].strip()
                        break
            
            # Get WiFi adapter IP (simplified - uses psutil if available)
            ip = self._get_interface_ip("Wi-Fi")
            
            return {"connected": True, "ssid": ssid, "ip": ip}
            
        except Exception as e:
            logging.debug(f"WiFi check failed: {e}")
            return {"connected": False, "ssid": None, "ip": None, "error": str(e)}
    
    def _get_ethernet_info(self) -> Dict[str, Any]:
        """Get Ethernet connection info"""
        try:
            import psutil
            
            # Look for Ethernet adapter
            net_if_addrs = psutil.net_if_addrs()
            net_if_stats = psutil.net_if_stats()
            
            # Common Ethernet interface names
            eth_names = ["Ethernet", "eth0", "eth1", "Local Area Connection"]
            
            for name in eth_names:
                if name in net_if_stats and net_if_stats[name].isup:
                    addrs = net_if_addrs.get(name, [])
                    ipv4 = next((a.address for a in addrs if a.family == socket.AF_INET), None)
                    return {"connected": True, "ip": ipv4}
            
            return {"connected": False, "ip": None}
            
        except ImportError:
            # Fallback without psutil
            ip = self._get_interface_ip("Ethernet")
            return {"connected": ip is not None, "ip": ip}
        except Exception as e:
            logging.debug(f"Ethernet check failed: {e}")
            return {"connected": False, "ip": None}
    
    def _get_interface_ip(self, interface_hint: str) -> Optional[str]:
        """Get IP address for an interface"""
        try:
            import psutil
            
            net_if_addrs = psutil.net_if_addrs()
            
            for name, addrs in net_if_addrs.items():
                if interface_hint.lower() in name.lower():
                    for addr in addrs:
                        if addr.family == socket.AF_INET:
                            return addr.address
            return None
        except:
            return None
    
    def _get_default_route(self) -> str:
        """Determine the default route (which interface is primary)"""
        try:
            # Simple test: can we reach the internet?
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # Try to determine if this is WiFi or Ethernet
            import psutil
            net_if_addrs = psutil.net_if_addrs()
            
            for name, addrs in net_if_addrs.items():
                for addr in addrs:
                    if addr.address == local_ip:
                        if "wi" in name.lower() or "wlan" in name.lower():
                            return "wifi"
                        elif "eth" in name.lower():
                            return "ethernet"
                        else:
                            return name
            
            return "unknown"
        except:
            return "none"
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute network status query"""
        try:
            wifi = self._get_wifi_info()
            ethernet = self._get_ethernet_info()
            default_route = self._get_default_route()
            
            # Overall connectivity
            is_connected = wifi.get("connected", False) or ethernet.get("connected", False)
            
            result = {
                "status": "success",
                "action": "get_network_status",
                "connected": is_connected,
                "wifi": wifi,
                "ethernet": ethernet,
                "default_route": default_route
            }
            
            logging.info(f"Network status: connected={is_connected}, route={default_route}")
            return result
            
        except Exception as e:
            logging.error(f"Failed to get network status: {e}")
            return {
                "status": "error",
                "error": f"Failed to get network status: {str(e)}"
            }
