"""Substrate Configuration - Maps app names to execution substrates.

Used by GoalInterpreter to determine if app.launch is redundant when a
session-bootstrapping goal already provides the same substrate.

RESPONSIBILITY:
- Load substrates from apps.yaml
- Provide get_substrate(app_name) lookup
- Singleton pattern (matches BrowserConfig)

DOES NOT:
- Make execution decisions
- Know about tools or goals
"""

import logging
from pathlib import Path
from typing import Dict, Set, Optional


class SubstrateConfig:
    """Singleton substrate configuration authority.
    
    Usage:
        config = SubstrateConfig.get()
        substrate = config.get_substrate("chrome")  # Returns "browser"
        substrate = config.get_substrate("vscode")  # Returns "editor"
        substrate = config.get_substrate("unknown") # Returns None
    """
    
    _instance: Optional["SubstrateConfig"] = None
    _substrate_map: Dict[str, Set[str]] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance
    
    @classmethod
    def get(cls) -> "SubstrateConfig":
        """Get singleton instance."""
        return cls()
    
    def get_substrate(self, app_name: str) -> Optional[str]:
        """Return substrate for app, or None if unknown.
        
        Args:
            app_name: Application name (case-insensitive)
            
        Returns:
            Substrate name (e.g., "browser", "editor") or None
        """
        app_lower = app_name.lower()
        for substrate, apps in self._substrate_map.items():
            if app_lower in apps:
                return substrate
        return None
    
    def _load(self) -> None:
        """Load substrate mapping from apps.yaml."""
        config_path = Path(__file__).parent.parent / "config" / "apps.yaml"
        
        if not config_path.exists():
            logging.warning(f"No apps.yaml found at {config_path}")
            self._substrate_map = {}
            return
        
        try:
            import yaml
            with open(config_path, encoding="utf-8") as f:
                full_config = yaml.safe_load(f) or {}
            
            raw_substrates = full_config.get("substrates", {})
            
            # Convert lists to sets for O(1) lookup
            self._substrate_map = {
                substrate: set(app.lower() for app in apps)
                for substrate, apps in raw_substrates.items()
            }
            
            total_apps = sum(len(apps) for apps in self._substrate_map.values())
            logging.info(
                f"SubstrateConfig: Loaded {len(self._substrate_map)} substrates "
                f"with {total_apps} app mappings"
            )
            
        except Exception as e:
            logging.warning(f"Failed to load substrates from apps.yaml: {e}")
            self._substrate_map = {}
    
    def reload(self) -> None:
        """Force reload configuration (for testing)."""
        self._load()
    
    @property
    def substrates(self) -> Dict[str, Set[str]]:
        """Get all substrate mappings (for debugging)."""
        return self._substrate_map.copy()
