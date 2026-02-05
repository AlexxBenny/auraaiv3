"""LocationConfig - Single authority for location/anchor definitions.

Loads anchor configuration from config/locations.yaml and provides:
- Anchor name → Path resolution
- Natural language alias → Anchor matching
- Scope annotation → Anchor conversion
- Validation (no duplicate aliases, no keyword collisions)

INVARIANT: WORKSPACE is always the default anchor and is NOT defined in YAML.
           It is dynamically set from SessionContext.cwd.
"""

from pathlib import Path
from typing import Dict, List, Optional, Set, TYPE_CHECKING
from dataclasses import dataclass, field
import logging
import yaml

if TYPE_CHECKING:
    from core.context import SessionContext


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class AnchorDefinition:
    """A single anchor with its path template and aliases."""
    name: str                    # e.g., "DRIVE_D", "DESKTOP"
    path_template: str           # e.g., "{letter}:/", "{home}/Desktop"
    aliases: List[str]           # e.g., ["d drive", "drive d"]


@dataclass
class LocationConfigData:
    """Parsed location configuration."""
    anchors: Dict[str, AnchorDefinition] = field(default_factory=dict)
    reserved_keywords: Set[str] = field(default_factory=set)


# =============================================================================
# LOCATION CONFIG SINGLETON
# =============================================================================

class LocationConfig:
    """Single authority for location/anchor configuration.
    
    RESPONSIBILITIES:
    - Load and cache config from config/locations.yaml
    - Resolve anchor names to filesystem Paths
    - Match natural language to anchor names
    - Convert scope annotations to anchor names
    - Validate config on load (fail fast)
    
    DOES NOT:
    - Define scope grammar (that's GoalInterpreter's job)
    - Execute anything
    - Resolve relative paths (that's PathResolver's job)
    """
    
    _instance: Optional["LocationConfig"] = None
    _config: Optional[LocationConfigData] = None
    
    def __init__(self):
        """Private constructor. Use LocationConfig.get() instead."""
        self._load_config()
    
    @classmethod
    def get(cls) -> "LocationConfig":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None
        cls._config = None
    
    # =========================================================================
    # CONFIG LOADING
    # =========================================================================
    
    def _load_config(self) -> None:
        """Load and validate configuration from YAML."""
        config_path = Path(__file__).parent.parent / "config" / "locations.yaml"
        
        if not config_path.exists():
            logging.warning(f"LocationConfig: {config_path} not found, using defaults")
            self._config = self._get_default_config()
            return
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
        except Exception as e:
            logging.error(f"LocationConfig: Failed to load YAML: {e}")
            self._config = self._get_default_config()
            return
        
        self._config = self._parse_config(raw)
        self._validate()
    
    def _parse_config(self, raw: dict) -> LocationConfigData:
        """Parse raw YAML into structured config."""
        config = LocationConfigData()
        
        # Parse reserved keywords
        config.reserved_keywords = set(raw.get("reserved_keywords", []))
        
        # Parse named anchors
        for name, data in raw.get("anchors", {}).items():
            config.anchors[name] = AnchorDefinition(
                name=name,
                path_template=data.get("path", ""),
                aliases=[a.lower() for a in data.get("aliases", [])]
            )
        
        # Parse drive anchors (auto-generate from templates)
        drives = raw.get("drives", {})
        enabled_letters = drives.get("enabled_letters", [])
        path_template = drives.get("path_template", "{letter}:/")
        alias_templates = drives.get("alias_templates", [])
        
        for letter in enabled_letters:
            anchor_name = f"DRIVE_{letter.upper()}"
            path = path_template.replace("{letter}", letter.upper())
            aliases = [
                t.replace("{letter}", letter.lower())
                for t in alias_templates
            ]
            
            config.anchors[anchor_name] = AnchorDefinition(
                name=anchor_name,
                path_template=path,
                aliases=aliases
            )
        
        return config
    
    def _get_default_config(self) -> LocationConfigData:
        """Fallback defaults if YAML is missing."""
        config = LocationConfigData()
        config.reserved_keywords = {"root", "inside", "after", "drive"}
        
        # Minimal defaults
        config.anchors = {
            "DESKTOP": AnchorDefinition("DESKTOP", "{home}/Desktop", ["desktop"]),
            "DOCUMENTS": AnchorDefinition("DOCUMENTS", "{home}/Documents", ["documents"]),
            "DOWNLOADS": AnchorDefinition("DOWNLOADS", "{home}/Downloads", ["downloads"]),
            "DRIVE_C": AnchorDefinition("DRIVE_C", "C:/", ["c drive", "drive c"]),
            "DRIVE_D": AnchorDefinition("DRIVE_D", "D:/", ["d drive", "drive d"]),
            "DRIVE_E": AnchorDefinition("DRIVE_E", "E:/", ["e drive", "drive e"]),
            "HOME": AnchorDefinition("HOME", "{home}", ["home"]),
        }
        
        return config
    
    # =========================================================================
    # VALIDATION
    # =========================================================================
    
    def _validate(self) -> None:
        """Validate config on load. Fail fast on errors.
        
        Checks:
        - No duplicate aliases across anchors
        - No alias collides with reserved keywords
        """
        if self._config is None:
            return
        
        seen_aliases: Dict[str, str] = {}  # alias → anchor_name
        
        for anchor_name, anchor in self._config.anchors.items():
            for alias in anchor.aliases:
                alias_lower = alias.lower()
                
                # Check for reserved keyword collision (exact match only)
                # e.g., "root" as alias is bad, but "d drive" containing "drive" is fine
                if alias_lower in self._config.reserved_keywords:
                    raise ValueError(
                        f"LocationConfig: Alias '{alias}' for {anchor_name} "
                        f"is a reserved scope keyword"
                    )
                
                # Check for duplicate alias
                if alias_lower in seen_aliases:
                    raise ValueError(
                        f"LocationConfig: Duplicate alias '{alias}' - "
                        f"used by both {seen_aliases[alias_lower]} and {anchor_name}"
                    )
                
                seen_aliases[alias_lower] = anchor_name
        
        logging.info(f"LocationConfig: Validated {len(self._config.anchors)} anchors")
    
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    def get_anchor_path(
        self, 
        anchor_name: str, 
        context: Optional["SessionContext"] = None
    ) -> Optional[Path]:
        """Resolve anchor name to absolute Path.
        
        Args:
            anchor_name: e.g., "DRIVE_D", "DESKTOP", "WORKSPACE"
            context: Session context (required for WORKSPACE)
        
        Returns:
            Resolved Path or None if anchor unknown
        """
        # WORKSPACE is special - always from context
        if anchor_name == "WORKSPACE":
            if context is None:
                logging.warning("LocationConfig: WORKSPACE requested but no context")
                return Path.cwd()
            return context.cwd
        
        # HOME is special - always Path.home()
        if anchor_name == "HOME":
            return Path.home()
        
        if self._config is None:
            return None
        
        anchor = self._config.anchors.get(anchor_name)
        if anchor is None:
            return None
        
        # Resolve path template
        path_str = anchor.path_template.replace("{home}", str(Path.home()))
        return Path(path_str)
    
    def get_all_anchors(
        self, 
        context: Optional["SessionContext"] = None
    ) -> Dict[str, Path]:
        """Get all anchors as name → Path dict.
        
        Args:
            context: Session context (required for WORKSPACE)
        
        Returns:
            Dict of anchor_name → Path
        """
        result: Dict[str, Path] = {}
        
        # Always include WORKSPACE and HOME
        if context is not None:
            result["WORKSPACE"] = context.cwd
        else:
            logging.warning("LocationConfig: No context, using Path.cwd() for WORKSPACE")
            result["WORKSPACE"] = Path.cwd()
        
        result["HOME"] = Path.home()
        
        # Add all configured anchors
        if self._config is not None:
            for name in self._config.anchors:
                path = self.get_anchor_path(name, context)
                if path is not None:
                    result[name] = path
        
        return result
    
    def infer_anchor_from_text(self, text: str) -> Optional[str]:
        """Match natural language text against aliases.
        
        Args:
            text: User input text (e.g., "in D drive", "on desktop")
        
        Returns:
            Anchor name if matched, None otherwise
        """
        if self._config is None:
            return None
        
        lower = text.lower()
        
        # Check all aliases
        for anchor_name, anchor in self._config.anchors.items():
            for alias in anchor.aliases:
                if alias in lower:
                    return anchor_name
        
        return None
    
    def get_anchor_from_scope(self, scope: str) -> Optional[str]:
        """Convert scope annotation to anchor name.
        
        INVARIANT: Scope GRAMMAR is defined in Python, not YAML.
        This method only handles the "drive:X" → "DRIVE_X" conversion.
        
        Args:
            scope: Scope string (e.g., "drive:D", "root", "inside:X")
        
        Returns:
            Anchor name for drive: scopes, None for others
        """
        # Only drive: scope maps to an anchor
        if scope.startswith("drive:"):
            letter = scope[6:].upper()
            anchor_name = f"DRIVE_{letter}"
            
            # Validate that this anchor is configured
            if self._config is not None and anchor_name in self._config.anchors:
                return anchor_name
            
            # Even if not in config, return the standard name
            # (PathResolver will validate later)
            return anchor_name
        
        # All other scopes: no explicit anchor
        # Orchestrator handles inheritance via dependencies or defaults to WORKSPACE
        return None
