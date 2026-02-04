"""Context Snapshot - Faceted system state for LLM consumption

ARCHITECTURE ROLE:
- Single source of truth for context formatting
- Used by IntentAgent, GoalInterpreter (NOT QueryClassifier - stays syntactic)
- Provides situational awareness without rule-based logic

FACETS STRUCTURE:
- media: playback state (active, playing, source)
- focus: foreground window, attention type
- resources: battery, CPU, memory pressure
- history: recent intent/action (for "do it again", "undo")

INVARIANT: Only actionable or disambiguating state, not everything.
"""

from typing import Dict, Any, Optional


class ContextSnapshot:
    """Builds faceted context snapshots for LLM consumption.
    
    DESIGN PRINCIPLE:
    Intelligence comes from the right state, shaped for reasoning.
    Not "everything available" - only what disambiguates or enables action.
    """
    
    @staticmethod
    def build(ambient_context: Optional[Dict[str, Any]]) -> str:
        """Format ambient context for LLM prompt injection.
        
        Args:
            ambient_context: Raw context from AmbientMemory.get_context()
            
        Returns:
            Formatted string for prompt injection (faceted)
        """
        if not ambient_context:
            return "No system context available."
        
        facets = ContextSnapshot.build_facets(ambient_context)
        return ContextSnapshot.format_facets(facets)
    
    @staticmethod
    def build_facets(ambient_context: Dict[str, Any]) -> Dict[str, Any]:
        """Build structured facets from raw context.
        
        Returns facets dict with: media, focus, resources
        """
        facets = {}
        
        # === MEDIA FACET ===
        media = ambient_context.get("media", {})
        if media:
            facets["media"] = {
                "active": media.get("active", False),
                "playing": media.get("playing", False),
                "source": media.get("source")
            }
        
        # === FOCUS FACET ===
        active_window = ambient_context.get("active_window", {})
        if active_window:
            process = active_window.get("process", active_window.get("process_name", ""))
            title = active_window.get("title", "")
            
            # Infer attention type from process/title
            attention = ContextSnapshot._infer_attention(process, title)
            
            facets["focus"] = {
                "app": process,
                "title": title[:50] if title else None,
                "attention": attention
            }
        
        # === RESOURCES FACET ===
        battery = ambient_context.get("battery", {})
        cpu = ambient_context.get("cpu_percent", 0)
        memory = ambient_context.get("memory_percent", 0)
        
        if battery or cpu or memory:
            facets["resources"] = {}
            
            if battery:
                facets["resources"]["battery"] = {
                    "level": battery.get("percent"),
                    "charging": battery.get("plugged", False)
                }
            
            if cpu:
                facets["resources"]["cpu_load"] = "high" if cpu > 70 else "medium" if cpu > 40 else "low"
            
            if memory:
                facets["resources"]["memory_pressure"] = "high" if memory > 80 else "normal"
        
        # === RUNNING APPS (for launch vs focus disambiguation) ===
        running = ambient_context.get("running_apps", [])
        if running:
            facets["running_apps"] = running[:5]
        
        return facets
    
    @staticmethod
    def format_facets(facets: Dict[str, Any]) -> str:
        """Format facets dict into LLM-readable string."""
        if not facets:
            return "No system context available."
        
        lines = []
        
        # Media facet
        media = facets.get("media", {})
        if media.get("active"):
            state = "playing" if media.get("playing") else "paused"
            source = media.get("source", "unknown")
            lines.append(f"media: {state} ({source})")
        
        # Focus facet
        focus = facets.get("focus", {})
        if focus.get("app"):
            app = focus["app"]
            title = focus.get("title", "")
            attention = focus.get("attention", "")
            if title:
                lines.append(f"focus: {app} - {title}")
            else:
                lines.append(f"focus: {app}")
            if attention:
                lines.append(f"attention: {attention}")
        
        # Resources facet
        resources = facets.get("resources", {})
        if resources:
            battery = resources.get("battery", {})
            if battery:
                level = battery.get("level")
                charging = "charging" if battery.get("charging") else "battery"
                lines.append(f"power: {level}% ({charging})")
            
            cpu = resources.get("cpu_load")
            if cpu and cpu != "low":
                lines.append(f"cpu: {cpu}")
            
            mem = resources.get("memory_pressure")
            if mem and mem != "normal":
                lines.append(f"memory: {mem}")
        
        # Running apps (compact)
        running = facets.get("running_apps", [])
        if running:
            lines.append(f"running: {', '.join(running)}")
        
        return "\n".join(lines) if lines else "No system context available."
    
    @staticmethod
    def _infer_attention(process: str, title: str) -> str:
        """Infer user attention type from window context.
        
        Returns: 'media' | 'work' | 'browser' | 'idle' | ''
        """
        process_lower = (process or "").lower()
        title_lower = (title or "").lower()
        
        # Media attention
        media_apps = {"spotify", "vlc", "groove", "musicbee", "foobar", "winamp", "netflix", "plex"}
        if any(app in process_lower for app in media_apps):
            return "media"
        if "youtube" in title_lower:
            return "media"
        
        # Work attention
        work_apps = {"code", "devenv", "notepad", "word", "excel", "powerpoint", "outlook"}
        if any(app in process_lower for app in work_apps):
            return "work"
        
        # Browser
        if any(b in process_lower for b in ["chrome", "firefox", "edge", "brave"]):
            return "browser"
        
        return ""
