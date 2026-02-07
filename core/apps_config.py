"""Apps Configuration - Single Authority for App Launch and Search Templates

Mirrors BrowserConfig and SettingsConfig pattern. Provides access to app launch
configuration and search engine templates.

RESPONSIBILITY:
- Load apps.yaml
- Provide get() singleton
- Expose search engine templates

DOES NOT:
- Make execution decisions
- Construct URLs (that's planner/orchestrator's job)
- Know about tools
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional


class AppsConfig:
    """Singleton apps configuration authority.
    
    Usage:
        config = AppsConfig.get()
        template = config.get_search_template("google")
        default_engine = config.get_default_search_engine()
    """
    
    _instance: Optional["AppsConfig"] = None
    _config: Dict[str, Any] = {}
    
    # Minimal defaults (only used if yaml missing or invalid)
    # Real data comes from apps.yaml - these are emergency fallbacks only
    DEFAULTS = {
        "search": {
            "default_browser": "chrome",
            "default_engine": "google",
            "engines": {
                # Minimal fallback - only if apps.yaml is completely missing
                "google": "https://www.google.com/search?q={query}"
            }
        },
        "browsers": {}
    }
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance
    
    @classmethod
    def get(cls) -> "AppsConfig":
        """Get singleton instance."""
        return cls()
    
    def _load(self) -> None:
        """Load configuration from apps.yaml."""
        config_path = Path(__file__).parent.parent / "config" / "apps.yaml"
        
        raw_config: Dict[str, Any] = {}
        
        if config_path.exists():
            try:
                import yaml
                with open(config_path, encoding="utf-8") as f:
                    raw_config = yaml.safe_load(f) or {}
                    logging.info(f"Loaded apps config from {config_path}")
            except Exception as e:
                logging.warning(f"Failed to load apps.yaml: {e}, using defaults")
        else:
            logging.info(f"No apps.yaml found at {config_path}, using defaults")
        
        # Merge with defaults (deep merge for nested dicts)
        self._config = self._deep_merge(self.DEFAULTS.copy(), raw_config)
        
        logging.debug(f"AppsConfig loaded: {len(self._config.get('search', {}).get('engines', {}))} search engines")
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    def get_search_template(self, platform: str) -> Optional[str]:
        """Get search engine template for platform.
        
        Args:
            platform: Search platform (google, youtube, etc.)
            
        Returns:
            Template string with {query} placeholder, or None if not found
        """
        engines = self._config.get("search", {}).get("engines", {})
        return engines.get(platform)
    
    def get_default_search_engine(self) -> str:
        """Get default search engine name.
        
        Returns:
            Default engine name (e.g., "google")
        """
        return self._config.get("search", {}).get("default_engine", "google")
    
    def get_browser_profile(self, browser_type: str) -> Optional[str]:
        """Get profile directory name for browser from default_args.
        
        Extracts --profile-directory=Default from apps.yaml.
        
        Args:
            browser_type: Browser type (chrome, edge, etc.)
            
        Returns:
            Profile directory name (e.g., "Default") or None if not found
        """
        browsers = self._config.get("browsers", {})
        browser_config = browsers.get(browser_type, {})
        default_args = browser_config.get("default_args", [])
        
        # Extract --profile-directory=Default from args
        for arg in default_args:
            if arg.startswith("--profile-directory="):
                return arg.split("=", 1)[1]
        
        return None
    
    def reload(self) -> None:
        """Force reload configuration (for testing)."""
        self._load()

