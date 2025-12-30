"""Limitation Analysis Agent - Converts limitations into skill proposals"""

import logging
from typing import Dict, Any
from models.model_manager import get_model_manager


class LimitationAnalysisAgent:
    """Analyzes limitations and proposes new skills/tools"""
    
    PROPOSAL_SCHEMA = {
        "type": "object",
        "properties": {
            "proposed_tool": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "pattern": "^[a-z][a-z0-9_]*$",
                        "description": "Tool name (snake_case, no spaces)"
                    },
                    "description": {
                        "type": "string",
                        "minLength": 10,
                        "description": "Clear description of what tool does"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["system", "file", "network", "application", "other"],
                        "default": "other"
                    },
                    "inputs": {
                        "type": "object",
                        "description": "JSON Schema for tool inputs",
                        "additionalProperties": True
                    },
                    "side_effects": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "What side effects this tool has"
                    },
                    "risk_level": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "default": "medium"
                    },
                    "os_permissions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Required OS permissions (e.g., 'admin', 'registry_write')"
                    }
                },
                "required": ["name", "description", "inputs"]
            },
            "rationale": {
                "type": "string",
                "description": "Why this tool is needed"
            },
            "alternative_approaches": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Alternative ways to accomplish the goal"
            }
        },
        "required": ["proposed_tool", "rationale"]
    }
    
    def __init__(self):
        self.model = get_model_manager().get_planner_model()  # Use reasoning model
        logging.info("LimitationAnalysisAgent initialized")
    
    def analyze(self, goal: str, missing_capability: str, reason: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze limitation and propose new skill
        
        Args:
            goal: Original user goal
            missing_capability: What capability is missing
            reason: Why existing tools can't do this
            context: Additional context
            
        Returns:
            Tool proposal with schema
        """
        available_tools = self._get_available_tools_summary()
        
        prompt = f"""You are a capability analyst. A user wants to accomplish this goal but the system lacks the required capability.

Goal: {goal}
Missing Capability: {missing_capability}
Reason: {reason}

Available Tools: {available_tools}

Your task: Propose a NEW tool that would enable this goal.

CRITICAL RULES:
1. NEVER propose executable code
2. ONLY propose tool metadata (name, description, inputs schema)
3. Tool name must be snake_case, no spaces
4. Inputs must be valid JSON Schema
5. Be specific about side effects and risks
6. Consider OS permissions required

Respond with JSON containing:
- proposed_tool: Complete tool specification
- rationale: Why this tool solves the problem
- alternative_approaches: Other ways to accomplish goal (if any)
"""
        
        try:
            result = self.model.generate(prompt, schema=self.PROPOSAL_SCHEMA)
            
            # Validate tool name format
            tool_name = result.get("proposed_tool", {}).get("name", "")
            if not tool_name or not tool_name.replace("_", "").isalnum():
                raise ValueError(f"Invalid tool name format: {tool_name}")
            
            logging.info(f"Tool proposal generated: {tool_name}")
            return result
            
        except Exception as e:
            logging.error(f"Limitation analysis failed: {e}")
            return {
                "proposed_tool": {
                    "name": "unknown_tool",
                    "description": f"Failed to analyze: {str(e)}",
                    "category": "other",
                    "inputs": {},
                    "side_effects": [],
                    "risk_level": "high"
                },
                "rationale": f"Analysis failed: {str(e)}",
                "alternative_approaches": []
            }
    
    def _get_available_tools_summary(self) -> str:
        """Get summary of available tools for context"""
        from tools.registry import get_registry
        registry = get_registry()
        tools = registry.list_all()
        
        if not tools:
            return "No tools available"
        
        return ", ".join([tool["name"] for tool in tools.values()])

