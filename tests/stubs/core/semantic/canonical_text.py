import logging

logging.warning("Using test stub for core.semantic.canonical_text")

def get_capability_synonyms(capability: str):
    # Simple deterministic synonym set - include a small common alias
    aliases = {
        "click": ["click", "press", "tap"],
        "open": ["open"],
    }
    return aliases.get(capability, [capability])

def derive_category(tool_name: str) -> str:
    # If no namespace, return 'general' for single-token names
    if "." not in tool_name:
        return "general"
    parts = tool_name.split(".")
    if len(parts) >= 2:
        return parts[1]
    return parts[0] if parts else "unknown"

def derive_capability(tool_name: str) -> str:
    parts = tool_name.split(".")
    return parts[-1] if parts else "unknown"

def generate_canonical_text(tool) -> str:
    # Minimal canonical representation expected by tests
    try:
        name = getattr(tool, "name", "unknown")
        desc = getattr(tool, "description", "")
    except Exception:
        name = "unknown"
        desc = ""
    cat = derive_category(name)
    cap = derive_capability(name)
    syns = ", ".join(get_capability_synonyms(cap))
    return f"Tool name: {name}\nDescription: {desc}\nCategory: {cat}\nCapability: {cap}\nSynonyms: {syns}\n"


