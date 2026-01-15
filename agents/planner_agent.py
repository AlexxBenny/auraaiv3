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
            "action_type": {
                "type": "string",
                "enum": ["information", "planning", "action", "system"],
                "description": "Type of action: information (answer only), planning (explain steps), action (execute tools), system (meta commands)"
            },
            "goal": {"type": "string"},
            "response": {
                "type": "string",
                "description": "Textual response for information, planning, or system requests. Must be present for non-action types."
            },
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string"},
                        "args": {"type": "object"}
                    },
                    "required": ["tool", "args"]
                },
                "description": "Tool execution steps. MUST be empty unless action_type == 'action'"
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
        "required": ["action_type", "goal"]
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
                        "tool": "system.display.take_screenshot",
                        "args": {"save_location": "desktop"}
                    }
                ],
                "requires_new_tool": false
            }
        """
        # Get available tools metadata
        available_tools = self.registry.get_tools_for_llm()
        
        tools_list = []
        for tool in available_tools:
            # Create simplified args summary (Name: Type)
            # e.g., "x: int, y: int, text: str"
            args_summary = []
            if "properties" in tool["schema"]:
                for prop_name, prop_data in tool["schema"]["properties"].items():
                    prop_type = prop_data.get("type", "any")
                    required = prop_name in tool["schema"].get("required", [])
                    req_mark = "*" if required else ""
                    args_summary.append(f"{prop_name}{req_mark}: {prop_type}")
            
            args_str = ", ".join(args_summary) if args_summary else "None"

            # Format: - name (Args: ...) : Description [Meta]
            tools_list.append(
                f"- {tool['name']}\n"
                f"  Args: {args_str}\n" # Simplified schema
                f"  Desc: {tool['description']}\n"
                f"  Meta: Risk={tool.get('risk_level', 'medium')}, "
                f"Time={tool.get('stabilization_time_ms', 0)}ms, "
                f"SideFx={tool.get('side_effects', [])}, "
                f"Rev={tool.get('reversible', False)}"
            )
        
        tools_list_str = "\n".join(tools_list)
        
        prompt = f"""You are an intelligent task planner. Your job is to classify the user's request based on USER INTENT, not on current capabilities.

User Input: "{user_input}"
Intent: {intent}

Available Tools:
{tools_list_str if available_tools else "No tools available"}

CRITICAL DECISION PROCESS:

STEP 1: Determine ACTION INTENT (user's desire for real-world change)
Ask yourself: "Does the user want something to happen in the real world?"

Real-world changes include:
- Changing system state (brightness, volume, power)
- Creating/modifying files
- Launching applications
- Automating tasks
- Taking screenshots
- Any physical or digital effect

If YES → action_type MUST be "action" (regardless of whether tools exist)
If NO → Continue to STEP 2

STEP 2: Classify non-action requests:

1. INFORMATION - User is asking a question that can be answered WITHOUT executing tools
   Examples:
   - "What tools are available?"
   - "What can you do?"
   - "Explain how brightness control works"
   - "List your capabilities"
   - "hi" / "hello"
   → action_type = "information"
   → response = Answer the question using your knowledge
   → steps = [] (MUST be empty)

2. PLANNING - User is asking HOW something could be done, or IF something is possible
   Examples:
   - "How would you automate backups?"
   - "How would you increase brightness?"
   - "What would you need to schedule a task?"
   → action_type = "planning"
   → response = Explain the approach or propose tools needed
   → steps = [] (MUST be empty)

3. SYSTEM - Meta commands (exit, help, status)
   Examples:
   - "Exit"
   - "Help"
   - "Status"
   → action_type = "system"
   → response = System message
   → steps = [] (MUST be empty)

STEP 3: For ACTION type, check capabilities:
- If suitable tool exists → steps = [tool execution steps]
- If NO suitable tool exists → requires_new_skill = true, steps = []

PLANNING RULES:
1. RISK: Avoid HIGH risk tools unless user explicitly requests dangerous action.
2. LATENCY: Prefer tools with lower 'Time' (latency) if multiple options exist.
3. CONFLICTS: Check 'SideFx' - do not chain conflicting tools without waiting or verifying.
4. REVERSIBILITY: Prefer 'Reversible=True' tools when possible.
5. STABILIZATION: If tool has high stabilization_time_ms, consider separate steps or verify success.

ABSOLUTE RULES (DO NOT VIOLATE):
❌ WRONG: "Increase brightness" → INFORMATION (because no tool exists)
✅ CORRECT: "Increase brightness" → ACTION → requires_new_skill = true

- ACTION is determined by USER INTENT, not by tool availability
- If user intends a real-world effect, action_type MUST be "action"
- steps MUST be empty unless action_type == "action" AND tool exists
- response MUST be present for information, planning, and system types
- NEVER generate executable code
- ONLY use tools from the available tools list
- If action_type == "action" and no tool exists, set requires_new_skill=true

DECISION TABLE:
User Request Type | Example | Action Intent? | action_type
Greeting | "hi" | ❌ No | INFORMATION
Knowledge question | "What tools do you have?" | ❌ No | INFORMATION
Explanation | "How does brightness work?" | ❌ No | INFORMATION
How-to | "How would you increase brightness?" | ❌ No | PLANNING
Real-world command | "Increase brightness to max" | ✅ Yes | ACTION (even if no tool)
Real-world command | "Take a screenshot" | ✅ Yes | ACTION (if tool exists)
System command | "exit" | ❌ No | SYSTEM

Respond with JSON containing:
- action_type: "information" | "planning" | "action" | "system" (REQUIRED)
- goal: What the user wants to accomplish
- response: Textual response (required for information/planning/system, null for action)
- steps: Array of tool steps (ONLY for action_type == "action" AND tool exists)
- requires_new_skill: true if action_type == "action" and no suitable tool exists
- missing_capability: What capability is missing (if requires_new_skill=true)
- reason: Why existing tools cannot accomplish this (if requires_new_skill=true)
"""
        
        try:
            result = self.model.generate(prompt, schema=self.PLAN_SCHEMA)
            
            # Validate action_type
            action_type = result.get("action_type", "action")  # Default to action for backward compatibility
            if action_type not in ["information", "planning", "action", "system"]:
                logging.warning(f"Invalid action_type '{action_type}', defaulting to 'action'")
                action_type = "action"
            result["action_type"] = action_type
            
            # Enforce action_type rules
            if action_type != "action":
                # Non-action types MUST have empty steps
                if result.get("steps"):
                    logging.warning(f"Non-action type '{action_type}' has steps - clearing steps")
                    result["steps"] = []
                
                # Non-action types MUST have response
                if not result.get("response"):
                    logging.warning(f"Non-action type '{action_type}' missing response - generating default")
                    result["response"] = self._generate_default_response(action_type, result.get("goal", user_input))
            
            # For action type, validate steps
            if action_type == "action":
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
                            result["requires_new_skill"] = True
                            result["steps"] = []
                            result["missing_capability"] = f"Tool '{tool_name}' does not exist"
                            result["reason"] = f"Referenced tool '{tool_name}' is not in registry"
            
            logging.info(f"Plan created: action_type={action_type}, goal='{result.get('goal')}', steps={len(result.get('steps', []))}")
            return result
            
        except Exception as e:
            logging.error(f"Planning failed: {e}")
            return {
                "action_type": "action",
                "goal": user_input,
                "response": None,
                "steps": [],
                "requires_new_skill": True,
                "missing_capability": "Planning failed",
                "reason": f"Planning failed: {str(e)}"
            }
    
    def _generate_default_response(self, action_type: str, goal: str) -> str:
        """Generate default response for non-action types"""
        if action_type == "information":
            return f"I can help you with: {goal}. Let me check what capabilities are available."
        elif action_type == "planning":
            return f"To accomplish '{goal}', I would need to plan the steps. Let me think about this."
        elif action_type == "system":
            return f"System command: {goal}"
        return "Processing your request..."

