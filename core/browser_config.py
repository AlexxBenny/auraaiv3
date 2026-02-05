"""Browser Configuration - Single Authority for Browser Policy

Mirrors LocationConfig pattern. Tools read from here, never decide policy.

RESPONSIBILITY:
- Load browser.yaml
- Provide get() singleton
- Expose typed config values

DOES NOT:
- Make execution decisions
- Manage sessions (BrowserSessionManager's job)
- Know about tools
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass


@dataclass(frozen=True)
class BrowserSettings:
    """Immutable browser configuration snapshot."""
    backend: Literal["playwright", "selenium", "cdp"]
    default_browser: Literal["chromium", "chrome", "edge", "firefox"]
    headless: bool
    user_data_dir: str  # "auto" | "isolated" | path
    timeout_ms: int
    reuse_session: bool


class BrowserConfig:
    """Singleton browser configuration authority.
    
    Usage:
        config = BrowserConfig.get()
        settings = config.settings
        browser = settings.default_browser
    """
    
    _instance: Optional["BrowserConfig"] = None
    _settings: Optional[BrowserSettings] = None
    
    # Defaults (used if yaml missing or invalid)
    DEFAULTS = {
        "backend": "playwright",
        "default_browser": "chromium",
        "headless": False,
        "user_data_dir": "auto",
        "timeout_ms": 10000,
        "reuse_session": True,
    }
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance
    
    @classmethod
    def get(cls) -> "BrowserConfig":
        """Get singleton instance."""
        return cls()
    
    @property
    def settings(self) -> BrowserSettings:
        """Get current browser settings."""
        if self._settings is None:
            self._load()
        return self._settings
    
    def _load(self) -> None:
        """Load configuration from browser.yaml."""
        config_path = Path(__file__).parent.parent / "config" / "browser.yaml"
        
        raw_config: Dict[str, Any] = {}
        
        if config_path.exists():
            try:
                import yaml
                with open(config_path, encoding="utf-8") as f:
                    full_config = yaml.safe_load(f) or {}
                    raw_config = full_config.get("browser", {})
                    logging.info(f"Loaded browser config from {config_path}")
            except Exception as e:
                logging.warning(f"Failed to load browser.yaml: {e}, using defaults")
        else:
            logging.info(f"No browser.yaml found at {config_path}, using defaults")
        
        # Merge with defaults
        merged = {**self.DEFAULTS, **raw_config}
        
        self._settings = BrowserSettings(
            backend=merged["backend"],
            default_browser=merged["default_browser"],
            headless=merged["headless"],
            user_data_dir=merged["user_data_dir"],
            timeout_ms=merged["timeout_ms"],
            reuse_session=merged["reuse_session"],
        )
        
        logging.debug(f"BrowserConfig: {self._settings}")
    
    def reload(self) -> None:
        """Force reload configuration (for testing)."""
        self._load()
