"""Verb Taxonomy - Closed set of semantic verbs per domain.

ARCHITECTURAL CONSTRAINT: Do not expand this without design review.

Verbs describe WHAT the user wants, not HOW to achieve it.
Tools describe HOW. Planner maps between them.

The verb set must be:
- Small (finite)
- Stable (rarely changes)
- Semantic (describes intent, not implementation)
"""

from typing import Set, Dict, FrozenSet


# =============================================================================
# VERB TAXONOMY (HARD-LOCKED)
# =============================================================================

BROWSER_VERBS: FrozenSet[str] = frozenset({
    "navigate",  # Go to URL
    "wait",      # Wait for element state
    "click",     # Click element
    "type",      # Type text into element
    "read",      # Read page content (title, text, url)
    "select",    # Select dropdown/option
    "scroll",    # Scroll page/element
    "search",    # Search on platform (google, youtube)
})

FILE_VERBS: FrozenSet[str] = frozenset({
    "create",    # Create file/folder
    "delete",    # Delete file/folder
    "move",      # Move file/folder
    "copy",      # Copy file/folder
    "read",      # Read file content
    "write",     # Write to file
    "rename",    # Rename file/folder
    "list",      # List directory contents
})

SYSTEM_VERBS: FrozenSet[str] = frozenset({
    "set",       # Set system state (volume, brightness)
    "get",       # Get system state (battery, time)
    "toggle",    # Toggle state (mute, wifi)
    "query",     # Query system info
})

APP_VERBS: FrozenSet[str] = frozenset({
    "launch",    # Launch application
    "focus",     # Focus/switch to application
    "close",     # Close application
})

MEMORY_VERBS: FrozenSet[str] = frozenset({
    "store",     # Store fact
    "recall",    # Recall facts
})

MEDIA_VERBS: FrozenSet[str] = frozenset({
    "play",      # Play media
    "pause",     # Pause media
    "stop",      # Stop media
    "next",      # Next track
    "previous",  # Previous track
})


# =============================================================================
# DOMAIN → VERB MAPPING
# =============================================================================

DOMAIN_VERBS: Dict[str, FrozenSet[str]] = {
    "browser": BROWSER_VERBS,
    "file": FILE_VERBS,
    "system": SYSTEM_VERBS,
    "app": APP_VERBS,
    "memory": MEMORY_VERBS,
    "media": MEDIA_VERBS,
}

ALL_DOMAINS: FrozenSet[str] = frozenset(DOMAIN_VERBS.keys())


# =============================================================================
# VALIDATION
# =============================================================================

def is_valid_verb(domain: str, verb: str) -> bool:
    """Check if verb is valid for domain."""
    if domain not in DOMAIN_VERBS:
        return False
    return verb in DOMAIN_VERBS[domain]


def get_verbs_for_domain(domain: str) -> FrozenSet[str]:
    """Get valid verbs for a domain."""
    return DOMAIN_VERBS.get(domain, frozenset())
