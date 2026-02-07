"""Settings Configuration - Single Authority for Global Preferences

Mirrors BrowserConfig pattern. Provides access to semantic defaults and global settings.

RESPONSIBILITY:
- Load settings.yaml
- Provide get() singleton
- Expose semantic defaults for SemanticResolver

DOES NOT:
- Make execution decisions
- Resolve semantic tokens (SemanticResolver's job)
- Know about tools
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional


class SettingsConfig:
    """Singleton settings configuration authority.
    
    Usage:
        config = SettingsConfig.get()
        default_platform = config.get_semantic_default("browser", "search", "platform")
    """
    
    _instance: Optional["SettingsConfig"] = None
    _config: Dict[str, Any] = {}
    
    # Defaults (used if yaml missing or invalid)
    DEFAULTS = {
        "semantic_defaults": {
            "browser": {
                "search": {
                    "platform": "google"
                }
            }
        }
    }
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance
    
    @classmethod
    def get(cls) -> "SettingsConfig":
        """Get singleton instance."""
        return cls()
    
    def _load(self) -> None:
        """Load configuration from settings.yaml."""
        config_path = Path(__file__).parent.parent / "config" / "settings.yaml"
        
        raw_config: Dict[str, Any] = {}
        
        if config_path.exists():
            try:
                import yaml
                with open(config_path, encoding="utf-8") as f:
                    raw_config = yaml.safe_load(f) or {}
                    logging.info(f"Loaded settings config from {config_path}")
            except Exception as e:
                logging.warning(f"Failed to load settings.yaml: {e}, using defaults")
        else:
            logging.info(f"No settings.yaml found at {config_path}, using defaults")
        
        # Merge with defaults (deep merge for nested dicts)
        self._config = self._deep_merge(self.DEFAULTS.copy(), raw_config)
        
        logging.debug(f"SettingsConfig loaded: semantic_defaults={self._config.get('semantic_defaults', {})}")
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    def get_semantic_default(
        self, 
        domain: str, 
        verb: str, 
        param: str
    ) -> Optional[str]:
        """Get semantic default for (domain, verb, param).
        
        Args:
            domain: Goal domain (e.g., "browser")
            verb: Goal verb (e.g., "search")
            param: Parameter name (e.g., "platform")
            
        Returns:
            Default value from config, or None if not found
        """
        defaults = self._config.get("semantic_defaults", {})
        return defaults.get(domain, {}).get(verb, {}).get(param)
    
    def reload(self) -> None:
        """Force reload configuration (for testing)."""
        self._load()

