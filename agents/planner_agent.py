"""Planner Agent - Decomposes tasks into tool execution plans

This is where "agentic" reasoning happens.
NO code generation. Only tool selection and planning.
"""

import logging
from typing import Dict, Any, List
from models.model_manager import get_model_manager
from tools.registry import get_registry


class PlannerAgent:
    """Plans task execution using available tools"""
    
    PLAN_SCHEMA = {
        "type": "object",
        "properties": {
            "goal": {"type": "string"},
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string"},
                        "args": {"type": "object"}
                    },
                    "required": ["tool", "args"]
                }
            },
            "requires_new_skill": {
                "type": "boolean",
                "default": False
            },
            "missing_capability": {
                "type": "string",
                "description": "What capability is missing"
            },
            "reason": {
                "type": "string",
                "description": "Why existing tools cannot accomplish this"
            }
        },
        "required": ["goal"]
    }
    
    def __init__(self):
        self.model = get_model_manager().get_planner_model()
        self.registry = get_registry()
        logging.info("PlannerAgent initialized")
    
    def plan(self, user_input: str, intent: str) -> Dict[str, Any]:
        """Create execution plan for user input
        
        Args:
            user_input: User's command
            intent: Classified intent from IntentAgent
            
        Returns:
            {
                "goal": "Take a screenshot",
                "steps": [
                    {
                        "tool": "take_screenshot",
                        "args": {"save_location": "desktop"}
                    }
                ],
                "requires_new_tool": false
            }
        """
        # Get available tools metadata
        available_tools = self.registry.get_tools_for_llm()
        
        tools_list = "\n".join([
            f"- {tool['name']}: {tool['description']}\n  Schema: {tool['schema']}"
            for tool in available_tools
        ])
        
        prompt = f"""You are a task planner. Create an execution plan for this user request:

User Input: "{user_input}"
Intent: {intent}

Available Tools:
{tools_list if available_tools else "No tools available"}

CRITICAL RULES:
1. NEVER generate executable code
2. ONLY use tools from the available tools list
3. If no tool exists for the task, set requires_new_skill=true and provide missing_capability and reason
4. When requires_new_skill=true, steps must be empty
5. Break complex tasks into multiple steps
6. Each step must reference a tool by name and provide arguments matching the tool's schema

Respond with JSON containing:
- goal: What the user wants to accomplish
- steps: Array of tool execution steps (empty if requires_new_skill=true)
- requires_new_skill: true if no suitable tool exists
- missing_capability: What capability is missing (if requires_new_skill=true)
- reason: Why existing tools cannot accomplish this (if requires_new_skill=true)
"""
        
        try:
            result = self.model.generate(prompt, schema=self.PLAN_SCHEMA)
            
            # Validate limitation detection
            if result.get("requires_new_skill", False):
                # If skill is required, steps must be empty
                if result.get("steps"):
                    logging.warning("Plan has steps but also requires_new_skill - clearing steps")
                    result["steps"] = []
                
                # Ensure required fields
                if not result.get("missing_capability"):
                    result["missing_capability"] = "Unknown capability"
                if not result.get("reason"):
                    result["reason"] = "No suitable tool found"
            else:
                # Validate that referenced tools exist
                for step in result.get("steps", []):
                    tool_name = step.get("tool")
                    if not self.registry.has(tool_name):
                        logging.warning(f"Planner referenced unknown tool: {tool_name}")
                        return {
                            "goal": result.get("goal", ""),
                            "steps": [],
                            "requires_new_skill": True,
                            "missing_capability": f"Tool '{tool_name}' does not exist",
                            "reason": f"Referenced tool '{tool_name}' is not in registry"
                        }
            
            logging.info(f"Plan created: {result.get('goal')} with {len(result.get('steps', []))} steps")
            return result
            
        except Exception as e:
            logging.error(f"Planning failed: {e}")
            return {
                "goal": user_input,
                "steps": [],
                "requires_new_tool": True,
                "tool_description": f"Planning failed: {str(e)}"
            }

