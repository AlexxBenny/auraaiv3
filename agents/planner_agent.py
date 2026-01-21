"""Planner Agent - Decomposes tasks into effect-based execution plans

This is where "agentic" reasoning happens.
NO code generation. Only effect identification and tool selection.

Effect-Based Execution Model:
- Planner identifies EFFECTS (what should be true after execution)
- Steps are DERIVED from effects (not generated independently)
- action_type is advisory (for backward compat), not authoritative
- Execution is gated by effect presence, not mode classification

Neo4j Integration:
- After LLM generates plan, eligibility is checked via Neo4j
- Blocking constraints cause refusal (steps=[])
- Soft constraints are attached as warnings
- LLMs decide WHAT, Neo4j decides IF
"""

import logging
from typing import Dict, Any, List, Optional
from models.model_manager import get_model_manager
from tools.registry import get_registry
from core.ontology.eligibility import check_plan_eligibility, verify_neo4j_connection


class PlannerAgent:
    """Plans task execution using effect-based model"""
    
    # =========================================================================
    # EFFECT-BASED PLAN SCHEMA (BASE TEMPLATE)
    # =========================================================================
    # NOTE: steps[].tool is dynamically populated with enum constraint at runtime
    # See _generate_plan_schema() for dynamic generation
    # =========================================================================
    
    PLAN_SCHEMA_BASE = {
        "type": "object",
        "properties": {
            # NEW: Effects array (first-class)
            "effects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Semantic ID: domain.entity.operation (e.g., app.chrome.running)"
                        },
                        "target": {
                            "type": "string",
                            "description": "Entity reference (domain:name format)"
                        },
                        "operation": {
                            "type": "string",
                            "enum": ["running", "closed", "created", "modified", "deleted", "captured", "changed"]
                        },
                        "postcondition": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["process_running", "window_visible", "file_exists", 
                                             "file_modified", "state_changed", "content_captured", "custom"]
                                },
                                "params": {"type": "object"},
                                "description": {"type": "string"}
                            },
                            "required": ["type"]
                        },
                        "precondition": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "params": {"type": "object"},
                                "description": {"type": "string"}
                            }
                        }
                    },
                    "required": ["id", "target", "operation", "postcondition"]
                },
                "description": "Observable effects to achieve. Empty for pure information requests."
            },
            # NEW: Explanation object (first-class)
            "explanation": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "content": {"type": "string"},
                    "required": {"type": "boolean"}
                },
                "description": "Non-state-changing information to deliver. Can coexist with effects."
            },
            "goal": {"type": "string"},
            # KEPT: action_type (now advisory, for backward compat)
            "action_type": {
                "type": "string",
                "enum": ["information", "planning", "action", "system"],
                "description": "ADVISORY ONLY - for backward compatibility. Effects presence is authoritative."
            },
            "response": {
                "type": "string",
                "description": "Textual response for information/planning/system requests."
            },
            # NOTE: steps[].tool is populated dynamically - see _generate_plan_schema()
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string"},  # Enum added dynamically
                        "args": {"type": "object"},
                        "achieves_effect": {
                            "type": "string",
                            "description": "ID of the effect this step satisfies"
                        }
                    },
                    "required": ["tool", "args"]
                },
                "description": "Tool execution steps. DERIVED from effects, not generated independently."
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
            },
            # Neo4j eligibility fields (unchanged)
            "refused": {
                "type": "boolean",
                "default": False,
                "description": "True if plan was refused due to blocking constraints"
            },
            "refusal": {
                "type": "object",
                "description": "Structured refusal object (when refused=True)",
                "properties": {
                    "blocked_tools": {"type": "array", "items": {"type": "string"}},
                    "blocking_constraints": {"type": "array"}
                }
            },
            "safety_warnings": {
                "type": "array",
                "description": "Soft constraint warnings (non-blocking)"
            },
            "eligibility_checked": {
                "type": "boolean",
                "default": False,
                "description": "True if Neo4j was consulted for eligibility"
            }
        },
        "required": ["effects", "goal"]
    }
    
    def _generate_plan_schema(self, available_tool_names: list) -> Dict[str, Any]:
        """
        Generate PLAN_SCHEMA with dynamic tool enum constraint.
        
        This is the CORE FIX for tool name mismatches.
        By constraining the LLM to emit only valid tool names at generation time,
        we eliminate the root cause of "tool_not_in_registry" errors.
        
        Args:
            available_tool_names: List of canonical tool names to allow
            
        Returns:
            Complete schema with steps[].tool constrained to enum
        """
        import copy
        
        # Deep copy base schema to avoid mutation
        schema = copy.deepcopy(self.PLAN_SCHEMA_BASE)
        
        # Add enum constraint to steps[].tool
        if available_tool_names:
            schema["properties"]["steps"]["items"]["properties"]["tool"] = {
                "type": "string",
                "enum": available_tool_names,
                "description": "Tool name from available tools list. MUST be exact match."
            }
            logging.debug(f"Generated schema with {len(available_tool_names)} tools in enum")
        else:
            # No tools available - keep as string (will result in requires_new_skill)
            logging.warning("No tools available for enum - using unconstrained string")
        
        return schema
    
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
        all_tools = self.registry.get_tools_for_llm()
        
        # =========================================================================
        # QDRANT SEMANTIC FILTERING (optional - fail soft)
        # =========================================================================
        # Query Qdrant for candidate tools based on semantic similarity.
        # If Qdrant fails or returns empty, fall back to all tools.
        # Candidates are SUGGESTIONS only - LLM may still hallucinate.
        # =========================================================================
        available_tools = all_tools  # Default: use all
        try:
            from core.semantic.tool_search import find_candidates
            candidates = find_candidates(user_input, top_k=10)
            if candidates:
                candidate_names = {c.name for c in candidates}
                available_tools = [t for t in all_tools if t['name'] in candidate_names]
                logging.info(f"Qdrant filtered: {len(available_tools)}/{len(all_tools)} tools")
            else:
                logging.debug("No Qdrant candidates - using all tools")
        except Exception as e:
            logging.debug(f"Qdrant unavailable (using all tools): {e}")
        
        # =========================================================================
        # EXTRACT TOOL NAMES FOR ENUM CONSTRAINT (Phase 1 fix)
        # =========================================================================
        # This is the CORE FIX: constrain LLM to emit only valid tool names.
        # =========================================================================
        available_tool_names = [t['name'] for t in available_tools]
        logging.info(f"Tool enum constraint: {len(available_tool_names)} tools available")
        
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
        
        # Build prompt with escaped braces for JSON examples
        tools_section = tools_list_str if available_tools else "No tools available"
        
        prompt = f"""You are an intelligent task planner. Your job is to identify what OBSERVABLE EFFECTS should be true after fulfilling the user's request.

User Input: "{user_input}"
Intent: {intent}

Available Tools:
{tools_section}

=============================================================================
EFFECT-BASED PLANNING PROCESS
=============================================================================

STEP 1: IDENTIFY EFFECTS
What observable changes should exist after fulfilling this request?

An EFFECT is a postcondition that requires execution:
- Application running/closed
- File created/modified/deleted  
- Screenshot captured
- System state changed (volume, brightness)

If the user wants a real-world change → identify the effect(s)
If no real-world change needed → effects = []

STEP 2: IDENTIFY EXPLANATION
Does the user also want information delivered?

An EXPLANATION is non-state-changing information:
- Can coexist with effects (e.g., "open chrome and explain tabs")
- Required if user asked a question
- Not required for pure action commands

STEP 3: DERIVE STEPS FROM EFFECTS
For each effect, find a tool that achieves it.

Steps are DERIVED from effects - one step per effect typically.
Each step MUST declare which effect it achieves (achieves_effect field).

=============================================================================
EFFECT EXAMPLES (Note: use proper JSON syntax)
=============================================================================

"launch chrome":
  effects: [{{"id": "app.chrome.running", "target": "application:chrome", "operation": "running", 
             "postcondition": {{"type": "process_running", "params": {{"process": "chrome"}}}}}}]
  explanation: null
  steps: [{{"tool": "system.apps.launch.shell", "args": {{"app_name": "chrome"}}, "achieves_effect": "app.chrome.running"}}]

"open chrome and explain how tabs work":
  effects: [{{"id": "app.chrome.running", ...same as above...}}]
  explanation: {{"topic": "chrome tabs", "content": "Chrome tabs allow...", "required": true}}
  steps: [{{"tool": "system.apps.launch.shell", "args": {{"app_name": "chrome"}}, "achieves_effect": "app.chrome.running"}}]

"what time is it":
  effects: []
  explanation: {{"topic": "current time", "required": true}}
  steps: []

"close notepad if it's open":
  effects: [{{"id": "app.notepad.closed", "target": "application:notepad", "operation": "closed",
             "postcondition": {{"type": "process_running", "params": {{"process": "notepad"}}}},
             "precondition": {{"type": "process_running", "params": {{"process": "notepad"}}}}}}]

=============================================================================
POSTCONDITION TYPES (use these in effects)
=============================================================================

- process_running: params: {{"process": "name", "window_visible": bool}}
- window_visible: params: {{"title": "substr", "process": "name"}}  
- file_exists: params: {{"path": "filepath"}}
- file_modified: params: {{"path": "filepath"}}
- content_captured: params: {{"format": "image", "location": "clipboard_or_file"}}
- state_changed: params: {{"state_type": "volume/brightness/etc"}}
- custom: params: {{}}, description: "human-readable for LLM judgment"

=============================================================================
CRITICAL RULES
=============================================================================

1. EFFECTS are determined by USER INTENT, not tool availability
2. If user wants a real-world change but no tool exists → requires_new_skill = true
3. Effects MUST be empty only if NO observable change is desired
4. Steps MUST be empty if effects are empty
5. Every step MUST have achieves_effect matching an effect ID
6. ONLY use tools from the available tools list
7. NEVER generate executable code

SEMANTIC ID FORMAT: domain.entity.operation
- app.chrome.running
- file.readme.created  
- display.screenshot.captured

=============================================================================
OUTPUT
=============================================================================

Respond with JSON containing:
- effects: Array of effects to achieve (empty if pure information)
- explanation: {{"topic", "content", "required"}} if user wants information
- goal: What the user wants to accomplish
- steps: Array of tool steps (DERIVED from effects)
- action_type: "action"|"information"|"planning"|"system" (ADVISORY for backward compat)
- requires_new_skill: true if effect exists but no tool can achieve it
- missing_capability: What capability is missing (if requires_new_skill=true)
- reason: Why existing tools cannot accomplish this (if requires_new_skill=true)
"""
        
        try:
            # Generate schema with dynamic tool enum constraint
            plan_schema = self._generate_plan_schema(available_tool_names)
            result = self.model.generate(prompt, schema=plan_schema)
            
            # =========================================================================
            # EFFECT-BASED VALIDATION (Phase 2)
            # =========================================================================
            # Execution routing is now based on EFFECTS presence, not action_type.
            # action_type is kept for backward compat but is ADVISORY only.
            # =========================================================================
            
            # Ensure effects is always a list
            if not isinstance(result.get("effects"), list):
                result["effects"] = []
            
            # Ensure explanation is properly structured
            # ADJUSTMENT 1: Don't populate explanation.content - leave for AgentLoop (lazy generation)
            if result.get("explanation") and not isinstance(result["explanation"], dict):
                result["explanation"] = {"required": False}
            if result.get("explanation") and result["explanation"].get("content"):
                # Log that we're clearing eager content (for Phase 3 lazy generation)
                logging.debug("Clearing eager explanation.content - will be generated by AgentLoop")
                result["explanation"]["content"] = None
            
            effects = result.get("effects", [])
            explanation = result.get("explanation", {})
            
            # ADJUSTMENT 2: Don't auto-derive action_type
            # Let LLM set it explicitly, or leave unset for AgentLoop to infer if needed
            # action_type is now purely advisory - effects presence is authoritative
            action_type = result.get("action_type")  # May be None, that's OK
            
            # =========================================================================
            # SEMANTIC EFFECT VALIDATION
            # =========================================================================
            # Reject invalid effect domains. Effects must be observable state changes.
            # Valid domains: app, file, system, state, device, display
            # Invalid domains: info (information is not a state change)
            # =========================================================================
            
            VALID_EFFECT_DOMAINS = {"app", "file", "system", "state", "device", "display", "window", "process"}
            
            valid_effects = []
            for effect in effects:
                effect_id = effect.get("id", "")
                domain = effect_id.split(".")[0] if "." in effect_id else ""
                
                if domain and domain not in VALID_EFFECT_DOMAINS:
                    logging.warning(
                        f"Rejecting invalid effect domain '{domain}' in '{effect_id}' - "
                        "effects must be state changes, not information"
                    )
                else:
                    valid_effects.append(effect)
            
            if len(valid_effects) < len(effects):
                logging.info(f"Filtered effects: {len(valid_effects)}/{len(effects)} valid")
            
            effects = valid_effects
            result["effects"] = effects
            
            # =========================================================================
            # EFFECT → STEP VALIDATION (Phase 2)
            # =========================================================================
            # Validate that steps are properly derived from effects.
            # This is capability matching, not hardcoding.
            # =========================================================================
            
            steps = result.get("steps", [])
            
            if effects:
                # Effects present = execution path
                
                # Check requires_new_skill
                if result.get("requires_new_skill", False):
                    if steps:
                        logging.warning("Plan has steps but also requires_new_skill - clearing steps")
                        result["steps"] = []
                    if not result.get("missing_capability"):
                        result["missing_capability"] = "Unknown capability"
                    if not result.get("reason"):
                        result["reason"] = "No suitable tool found"
                else:
                    # Validate effect→step bindings (soft check, log only)
                    effect_ids = {e.get("id") for e in effects}
                    for step in steps:
                        if step.get("achieves_effect") and step["achieves_effect"] not in effect_ids:
                            logging.warning(
                                f"Step '{step.get('tool')}' references invalid effect '{step['achieves_effect']}'"
                            )
                    
                    # Check for orphaned effects (effects with no achieving step)
                    achieved_effects = {s.get("achieves_effect") for s in steps if s.get("achieves_effect")}
                    orphaned = effect_ids - achieved_effects
                    if orphaned and not result.get("requires_new_skill"):
                        logging.info(f"Effects without achieving steps: {orphaned}")
                        # Don't force requires_new_skill - might be intentional
                    
                    # =========================================================================
                    # HARD GUARD: Unknown tool rejection (BEFORE Neo4j)
                    # =========================================================================
                    for step in steps:
                        tool_name = step.get("tool")
                        if not self.registry.has(tool_name):
                            logging.warning(f"HARD REJECT: LLM emitted unknown tool '{tool_name}'")
                            result["refused"] = True
                            result["refusal"] = {
                                "error_type": "unknown_tool",
                                "blocked_tools": [tool_name],
                                "blocking_constraints": [{
                                    "constraint": "tool_not_in_registry",
                                    "type": "existence",
                                    "resolvable": False,
                                    "resolution_hint": "Tool does not exist in registry"
                                }]
                            }
                            result["steps"] = []
                            result["eligibility_checked"] = False
                            return result  # Early exit - no Neo4j call needed
            else:
                # No effects = pure explanation/information path
                if steps:
                    logging.warning("No effects but steps generated - clearing steps")
                    result["steps"] = []
                
                # Don't generate explanation content here - AgentLoop owns that (lazy generation)
            
            # =========================================================================
            # NEO4J ELIGIBILITY CHECK
            # =========================================================================
            # Check eligibility ONLY if effects are present and steps are generated.
            # =========================================================================
            
            if effects and result.get("steps") and not result.get("requires_new_skill"):
                steps = result.get("steps", [])
                
                try:
                    eligibility = check_plan_eligibility(steps)
                    result["eligibility_checked"] = eligibility.checked
                    
                    if not eligibility.eligible:
                        # REFUSE - blocking constraints exist
                        logging.warning(
                            f"Plan refused by Neo4j: {len(eligibility.blocking_reasons)} blocking constraint(s)"
                        )
                        
                        # Build structured refusal object
                        blocked_tools = list(set(r.tool for r in eligibility.blocking_reasons))
                        blocking_constraints = [
                            {
                                "constraint": r.constraint,
                                "type": r.constraint_type,
                                "resolvable": r.resolvable,
                                "resolution_hint": r.resolution_hint
                            }
                            for r in eligibility.blocking_reasons
                        ]
                        
                        result["refused"] = True
                        result["refusal"] = {
                            "blocked_tools": blocked_tools,
                            "blocking_constraints": blocking_constraints
                        }
                        result["steps"] = []  # Clear steps - not allowed to execute
                        
                        # Log each blocking reason
                        for reason in eligibility.blocking_reasons:
                            logging.info(
                                f"  Blocked: {reason.tool} -> {reason.constraint} ({reason.constraint_type})"
                            )
                    else:
                        # ALLOWED - no blocking constraints
                        result["refused"] = False
                        
                        # Attach soft constraints as warnings
                        if eligibility.warnings:
                            result["safety_warnings"] = [
                                {
                                    "tool": w.tool,
                                    "warning": w.constraint,
                                    "type": w.constraint_type,
                                    "recommendation": w.resolution_hint
                                }
                                for w in eligibility.warnings
                            ]
                            logging.info(f"Plan allowed with {len(eligibility.warnings)} warning(s)")
                            
                except Exception as e:
                    # FAIL CLOSED - if eligibility check fails, refuse
                    logging.error(f"Eligibility check failed: {e}")
                    result["eligibility_checked"] = False
                    result["refused"] = True
                    result["refusal"] = {
                        "error_type": "eligibility_check_failed",
                        "blocked_tools": [s.get("tool") for s in steps],
                        "blocking_constraints": []
                    }
                    result["steps"] = []
            else:
                # Non-action or no steps - eligibility not applicable
                result["eligibility_checked"] = False
                result["refused"] = False
            
            logging.info(f"Plan created: action_type={action_type}, goal='{result.get('goal')}', steps={len(result.get('steps', []))}, refused={result.get('refused', False)}")
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

