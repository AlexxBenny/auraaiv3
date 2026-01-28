"""Planner Agent - Reasoning-only fallback for ambiguous requests

JARVIS Architecture Role:
- This is the FALLBACK for when IntentAgent confidence < 0.75
- Used for ambiguous, underspecified, or novel requests
- NO effects, NO verification, NO eligibility checks

REMOVED (from old version):
- Effect-based planning
- Neo4j eligibility checks
- Effect → step validation
- Complex postcondition schemas

KEPT:
- Ability to reason over novel requests
- Sequence generation for multi-step tasks
- Information vs action discrimination
"""

import logging
from typing import Dict, Any, List
from models.model_manager import get_model_manager
from tools.registry import get_registry


class PlannerAgent:
    """Reasoning-only fallback for ambiguous requests.
    
    Used when:
    - IntentAgent confidence < 0.75
    - Intent is "unknown"
    - Action resolution fails
    """
    
    REASONING_SCHEMA = {
        "type": "object",
        "properties": {
            "action_type": {
                "type": "string",
                "enum": ["information", "action"],
                "description": "Is this a question (information) or a command (action)?"
            },
            "explanation": {
                "type": "string",
                "description": "For information requests: the answer. For action requests: reasoning about how to accomplish it."
            },
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string"},
                        "params": {"type": "object"}
                    },
                    "required": ["tool", "params"]
                },
                "description": "For action requests: sequence of tool calls. Empty for information requests."
            },
            "confidence": {
                "type": "number",
                "description": "How confident are you in this plan (0-1)?"
            },
            "needs_clarification": {
                "type": "boolean",
                "description": "True if the request is too ambiguous to act on"
            },
            "clarification_question": {
                "type": "string",
                "description": "If needs_clarification, what would you ask the user?"
            }
        },
        "required": ["action_type", "explanation"]
    }
    
    def __init__(self):
        self.model = get_model_manager().get_planner_model()
        self.registry = get_registry()
        logging.info("PlannerAgent initialized (reasoning-only mode)")
    
    def reason(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a reasoned response for ambiguous input.
        
        Args:
            user_input: The user's request
            context: Current system context (active window, running apps, etc.)
            
        Returns:
            {
                "action_type": "information" | "action",
                "explanation": "...",
                "steps": [...] if action,
                "confidence": 0.0-1.0,
                "needs_clarification": bool,
                "clarification_question": "..." if needs_clarification
            }
        """
        # Get available tools
        all_tools = self.registry.get_tools_for_llm()
        tool_names = [t['name'] for t in all_tools]
        
        # Build tools description
        tools_desc = "\n".join([
            f"- {t['name']}: {t['description']}" for t in all_tools
        ])
        
        # Build context description
        context_desc = self._format_context(context)
        
        # Add tool enum constraint to schema
        schema = self._generate_schema(tool_names)
        
        prompt = f"""You are a reasoning agent. Your job is to understand ambiguous or complex requests and determine how to handle them.

User request: "{user_input}"

{context_desc}

Available tools:
{tools_desc}

=============================================================================
TASK
=============================================================================

1. Determine if this is an INFORMATION request (user wants to know something) or an ACTION request (user wants you to do something).

2. If INFORMATION: Provide the answer directly in "explanation".

3. If ACTION: Figure out what sequence of tool calls would accomplish this. List them in "steps".

4. If the request is too vague or ambiguous to act on, set needs_clarification=true and provide a clarification_question.

=============================================================================
RULES
=============================================================================

- ONLY use tools from the available tools list
- If no tool can accomplish the request, explain why in "explanation"
- Be conservative - if unsure, ask for clarification
- For "steps", use exact tool names from the list

=============================================================================
OUTPUT
=============================================================================

Respond with JSON containing:
- action_type: "information" or "action"
- explanation: Your answer or reasoning
- steps: Array of {{tool, params}} (empty for information requests)
- confidence: How confident you are (0-1)
- needs_clarification: true if request is too ambiguous
- clarification_question: Only if needs_clarification=true
"""
        
        try:
            result = self.model.generate(prompt, schema=schema)
            
            # Validate steps use known tools
            steps = result.get("steps", [])
            valid_steps = []
            for step in steps:
                tool_name = step.get("tool")
                if self.registry.has(tool_name):
                    valid_steps.append(step)
                else:
                    logging.warning(f"PlannerAgent emitted unknown tool: {tool_name}")
            
            result["steps"] = valid_steps
            
            # If we had to filter steps, lower confidence
            if len(valid_steps) < len(steps):
                result["confidence"] = min(result.get("confidence", 0.5), 0.3)
            
            logging.info(
                f"PlannerAgent reasoning: type={result.get('action_type')}, "
                f"steps={len(valid_steps)}, confidence={result.get('confidence', 0):.2f}"
            )
            
            return result
            
        except Exception as e:
            logging.error(f"PlannerAgent reasoning failed: {e}")
            return {
                "action_type": "information",
                "explanation": f"I encountered an error trying to understand your request: {str(e)}",
                "steps": [],
                "confidence": 0.0,
                "needs_clarification": True,
                "clarification_question": "Could you please rephrase your request?"
            }
    
    def _generate_schema(self, tool_names: List[str]) -> Dict[str, Any]:
        """Generate schema with tool enum constraint."""
        import copy
        schema = copy.deepcopy(self.REASONING_SCHEMA)
        
        if tool_names:
            schema["properties"]["steps"]["items"]["properties"]["tool"] = {
                "type": "string",
                "enum": tool_names
            }
        
        return schema
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context for prompt."""
        parts = ["Current context:"]
        
        active_window = context.get("active_window", {})
        if active_window:
            title = active_window.get("title", "unknown")
            process = active_window.get("process_name", active_window.get("process", "unknown"))
            parts.append(f"- Active window: {title} ({process})")
        
        running_apps = context.get("running_apps", [])
        if running_apps:
            apps_str = ", ".join(running_apps[:5])
            if len(running_apps) > 5:
                apps_str += f" (+{len(running_apps) - 5} more)"
            parts.append(f"- Running apps: {apps_str}")
        
        battery = context.get("battery", {})
        if battery:
            pct = battery.get("percent", "?")
            plugged = "plugged in" if battery.get("plugged") else "on battery"
            parts.append(f"- Battery: {pct}% ({plugged})")
        
        if len(parts) == 1:
            parts.append("- No context available")
        
        return "\n".join(parts)
    
    # Legacy method for backward compatibility
    def plan(self, user_input: str, intent: str = "unknown") -> Dict[str, Any]:
        """Legacy method - redirects to reason()."""
        return self.reason(user_input, {})
