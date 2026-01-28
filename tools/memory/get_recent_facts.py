"""Memory Recall Tool - Get recent facts from episodic memory

Allows users to ask about previously queried information:
- "What was my RAM usage earlier?"
- "What did I check in the last hour?"
- "What battery level did I have before?"

INVARIANT: Returns facts exactly as stored, no interpretation.
"""

from typing import Dict, Any
from tools.base import Tool


class GetRecentFactsTool(Tool):
    """Recall facts from episodic memory (FactsMemory).
    
    Examples:
    - "What was my RAM usage earlier?"
    - "What apps did I check today?"
    - "What was my battery level?"
    """
    
    @property
    def name(self) -> str:
        return "memory.get_recent_facts"
    
    @property
    def description(self) -> str:
        return "Recall previously queried system information from memory"
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "minutes": {
                    "type": "integer",
                    "description": "How many minutes back to search (default 60)",
                    "default": 60
                },
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific fact keys to filter by (e.g., ['ram_used_percent'])"
                },
                "tool_filter": {
                    "type": "string",
                    "description": "Filter by specific tool (e.g., 'system.state.get_memory_usage')"
                }
            },
            "required": []
        }
    
    @property
    def risk_level(self) -> str:
        return "low"
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return False  # Memory queries don't need screen access
    
    # Schema for fact extraction (Phase 2D requirement)
    fact_schema = {
        "recalled_facts": {
            "path": ["facts"],
            "type": list,
            "required": True
        },
        "recall_count": {
            "path": ["count"],
            "type": int,
            "required": True
        },
        "time_range_minutes": {
            "path": ["time_range_minutes"],
            "type": int,
            "required": False
        }
    }
    
    # Tags for tool resolution
    tags = ["memory", "recall", "history", "earlier", "previous", "before"]
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Recall facts from FactsMemory.
        
        Args:
            args: {
                "minutes": int (default 60),
                "keys": List[str] (optional),
                "tool_filter": str (optional)
            }
            
        Returns:
            {
                "status": "success",
                "facts": [...],  # List of recalled facts
                "count": int,
                "time_range_minutes": int
            }
        """
        # Import here to ensure singleton is shared with action_pipeline
        from memory.facts import get_facts_memory
        
        minutes = args.get("minutes", 60)
        keys = args.get("keys", [])
        tool_filter = args.get("tool_filter")
        
        try:
            memory = get_facts_memory()
            
            # Query with bounded defaults
            results = memory.query_by_keys(
                keys=keys if keys else [],
                tool=tool_filter,
                max_age_minutes=minutes,
                limit=20
            )
            
            # Format results for display
            formatted_facts = []
            for stored in results:
                formatted_facts.append({
                    "timestamp": stored.timestamp,
                    "tool": stored.tool,
                    "query": stored.query,
                    "facts": stored.facts,
                    "keys": stored.fact_keys
                })
            
            return {
                "status": "success",
                "facts": formatted_facts,
                "count": len(formatted_facts),
                "time_range_minutes": minutes
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "facts": [],
                "count": 0
            }
