"""Tool Resolver - Two-Stage Intent-Aware Resolution

JARVIS Architecture Role:
- Maps intents to PREFERRED tool domains (not hard exclusion)
- Two-stage resolution for robustness:
  - Stage 1: Preferred domains
  - Stage 2: Global fallback with domain mismatch penalty

Key principle: Wrong intent should DEGRADE performance, not DOOM execution.
"""

import logging
from typing import Dict, Any, List, Optional
from tools.registry import get_registry
from models.model_manager import get_model_manager


# Intent to PREFERRED tool domains (soft guidance, not hard filter)
INTENT_TOOL_DOMAINS = {
    # Application lifecycle
    "application_launch": ["system.apps.launch"],
    "application_control": ["system.apps"],  # focus, close, etc.
    
    # Window management (Phase 2B')
    "window_management": ["system.window", "system.virtual_desktop"],
    
    # System operations - READ (queries)
    "system_query": ["system.state"],
    
    # System operations - WRITE (control actions)
    # Includes: audio, display, power, desktop (icons/night light), network (airplane mode)
    "system_control": ["system.audio", "system.display", "system.power", "system.desktop", "system.network"],
    
    # Screen operations
    "screen_capture": ["system.display"],
    "screen_perception": ["system.display"],  # OCR/find_text
    
    # Input operations
    "input_control": ["system.input"],
    
    # Clipboard operations
    "clipboard_operation": ["system.clipboard"],
    
    # Memory recall (Phase 3A - episodic memory)
    "memory_recall": ["memory"],
    
    # File operations (existing tools)
    "file_operation": ["files"],
    
    # Browser control Phase 1+: browser automation tools get first choice
    # Falls back to system.apps.launch if no browser tools match
    "browser_control": ["browsers"],
    
    "office_operation": ["office"],
    
    # Pure LLM (no tools needed)
    "information_query": [],
    
    # Unknown intent → consider all tools
    "unknown": [],
}


# Intent to DISALLOWED tool domains (hard exclusion from Stage 2 fallback)
# SAFETY INVARIANT: Physical input tools are opt-in only, never guessed.
INTENT_DISALLOWED_DOMAINS = {
    # browser_control must NEVER fallback to physical input
    "browser_control": ["system.input"],
    
    # File operations - no mouse guessing
    "file_operation": ["system.input"],
    
    # Office operations - no mouse guessing  
    "office_operation": ["system.input"],
    
    # Application launch/control - no input fallback
    "application_launch": ["system.input"],
    "application_control": ["system.input"],
    
    # Window management - no raw input fallback (has its own keyboard shortcuts)
    "window_management": ["system.input"],
    
    # Information queries should never execute anything physical
    "information_query": ["system.input", "system.apps", "system.power"],
    
    # Screen operations should not fall back to input
    "screen_capture": ["system.input"],
    "screen_perception": ["system.input"],
}

# Intent to ALLOWED tool domains for Stage 2 (WHITELIST - hard constraint)
# SAFETY INVARIANT: Stage 2 can ONLY select from these domains.
# If no match → hard-fail, do NOT hallucinate a random tool.
INTENT_STAGE2_ALLOWED_DOMAINS = {
    # File operations can ONLY fallback to files.*
    "file_operation": ["files"],
    
    # Browser control: browsers first, launch as fallback
    "browser_control": ["browsers", "system.apps.launch"],
    
    # Application launch stays in apps domain
    "application_launch": ["system.apps.launch"],
    "application_control": ["system.apps"],
    
    # System control stays in its domains
    "system_control": ["system.audio", "system.display", "system.power", "system.desktop", "system.network"],
    
    # Screen operations stay in display
    "screen_capture": ["system.display"],
    "screen_perception": ["system.display"],
    
    # Clipboard stays in clipboard
    "clipboard_operation": ["system.clipboard"],
    
    # Input control stays in input
    "input_control": ["system.input"],
    
    # Window management stays in window/desktop
    "window_management": ["system.window", "system.virtual_desktop"],
    
    # System query stays in state
    "system_query": ["system.state"],
    
    # Memory recall stays in memory
    "memory_recall": ["memory"],
    
    # Office operations stay in office
    "office_operation": ["office"],
    
    # Information query should never have Stage 2 tools
    "information_query": [],
    
    # Unknown - allow all (but will still be filtered by disallowed)
    "unknown": None,  # None means no whitelist restriction
}

# Resolution thresholds
CONFIDENCE_THRESHOLD = 0.7  # Below this → trigger fallback expansion
DOMAIN_MISMATCH_PENALTY = 0.15  # Applied to out-of-domain tools in Stage 2


# Schema includes confidence for two-stage routing
RESOLUTION_SCHEMA = {
    "type": "object",
    "properties": {
        "tool": {
            "type": ["string", "null"],
            "description": "Exact tool name from available list, or null if no tool matches"
        },
        "params": {
            "type": "object",
            "description": "Parameters for the tool"
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Confidence in tool match (0.0-1.0)"
        },
        "reason": {
            "type": "string",
            "description": "Brief explanation of selection or why no tool matches"
        }
    },
    "required": ["tool", "params", "confidence"]
}


class ToolResolver:
    """Two-stage tool resolution with fallback expansion.
    
    Stage 1: Search preferred domains for intent
    Stage 2: If no match or low confidence, expand to ALL tools
    
    Returns enriched metadata for downstream decisions.
    """
    
    def __init__(self):
        self.registry = get_registry()
        # Role-based model access (config-driven)
        self.model = get_model_manager().get("tool_resolver")
        logging.info("ToolResolver initialized (two-stage mode)")
    
    def resolve(self, description: str, intent: str, 
                context: Dict[str, Any],
                action_class: str = None) -> Dict[str, Any]:
        """Two-stage resolution: preferred domains → global fallback.
        
        Args:
            description: What the user wants to do
            intent: Classified intent
            context: Current system context
            action_class: Optional semantic filter ("actuate", "observe", "query").
                         If provided, ONLY tools with matching capability_class
                         will be considered. This is a HARD FILTER - no fallback.
            
        Returns:
            {
                "tool": "exact.tool.name" or None,
                "params": {...},
                "confidence": 0.85,
                "domain_match": true/false,
                "stage": 1 or 2,
                "reason": "..." (if tool is None)
            }
        """
        # ===== ACTION CLASS HARD FILTER (Phase 2) =====
        # Applied BEFORE domain filtering. If specified, ONLY tools with
        # matching capability_class are considered. No fallback, no relaxation.
        action_class_filter = None
        if action_class:
            if action_class not in ("actuate", "observe", "query"):
                logging.error(f"Invalid action_class '{action_class}' - must be actuate/observe/query")
                return {
                    "tool": None,
                    "params": {},
                    "confidence": 0.0,
                    "domain_match": False,
                    "stage": 0,
                    "status": "invalid_action_class",
                    "reason": f"Invalid action_class '{action_class}' - must be actuate/observe/query"
                }
            action_class_filter = action_class
            logging.info(f"Action class filter active: {action_class}")
        
        # ===== STAGE 1: Preferred Domains =====
        preferred_tools = self._get_preferred_tools(intent)
        
        # Apply action_class filter to preferred tools
        if action_class_filter and preferred_tools:
            original_count = len(preferred_tools)
            preferred_tools = [
                t for t in preferred_tools
                if t.get("capability_class", "actuate") == action_class_filter
            ]
            filtered_count = original_count - len(preferred_tools)
            if filtered_count > 0:
                logging.info(f"Action class filter: {filtered_count} tools filtered, {len(preferred_tools)} remain")
            
            if not preferred_tools:
                # HARD FAIL: No tools match capability_class in preferred domains
                logging.warning(f"Action class hard-fail: no '{action_class}' tools in preferred domains for '{intent}'")
                return {
                    "tool": None,
                    "params": {},
                    "confidence": 0.0,
                    "domain_match": False,
                    "stage": 1,
                    "status": "capability_class_mismatch",
                    "reason": f"No tools with capability_class='{action_class}' in preferred domains for intent '{intent}'"
                }
        
        if preferred_tools:
            stage1_result = self._resolve_with_tools(
                description, intent, context, preferred_tools, stage=1
            )
            
            # Check if Stage 1 succeeded with sufficient confidence
            if stage1_result.get("tool") and stage1_result.get("confidence", 0) >= CONFIDENCE_THRESHOLD:
                stage1_result["domain_match"] = True
                stage1_result["stage"] = 1
                logging.info(f"Stage 1 success: {stage1_result['tool']} (conf={stage1_result['confidence']:.2f})")
                return stage1_result
            
            logging.info(f"Stage 1 insufficient: tool={stage1_result.get('tool')}, conf={stage1_result.get('confidence', 0):.2f}")
        else:
            logging.info(f"No preferred domains for intent '{intent}', skipping to Stage 2")
        
        # ===== STAGE 2: Domain-Locked Fallback =====
        # SAFETY: Stage 2 is domain-locked, not a free-for-all
        all_tools = self.registry.get_tools_for_llm()
        
        if not all_tools:
            return {
                "tool": None,
                "params": {},
                "confidence": 0.0,
                "domain_match": False,
                "stage": 2,
                "reason": "No tools registered in system"
            }
        
        # STEP 1: Apply WHITELIST (allowed domains for this intent)
        # This is the PRIMARY safety filter
        allowed = INTENT_STAGE2_ALLOWED_DOMAINS.get(intent)
        
        if allowed is not None:  # None means no whitelist restriction
            if len(allowed) == 0:
                # Empty list = no Stage 2 allowed for this intent
                logging.warning(f"Stage 2 blocked: intent '{intent}' has no allowed fallback domains")
                return {
                    "tool": None,
                    "params": {},
                    "confidence": 0.0,
                    "domain_match": False,
                    "stage": 2,
                    "status": "stage2_blocked",
                    "reason": f"Intent '{intent}' does not support fallback resolution"
                }
            
            # Filter to only allowed domains
            original_count = len(all_tools)
            all_tools = [
                t for t in all_tools
                if any(t["name"].startswith(d) for d in allowed)
            ]
            filtered_count = original_count - len(all_tools)
            if filtered_count > 0:
                logging.info(f"Stage 2: restricted to {len(all_tools)} tools in allowed domains for intent '{intent}'")
            
            if not all_tools:
                # HARD-FAIL: No tools in allowed domains
                logging.warning(f"Stage 2 hard-fail: no tools in allowed domains {allowed} for intent '{intent}'")
                return {
                    "tool": None,
                    "params": {},
                    "confidence": 0.0,
                    "domain_match": False,
                    "stage": 2,
                    "status": "capability_missing",
                    "reason": f"No tools available in allowed domains {allowed} for intent '{intent}'"
                }
        
        # STEP 2: Apply BLACKLIST (disallowed domains)
        # Secondary safety filter
        disallowed = INTENT_DISALLOWED_DOMAINS.get(intent, [])
        if disallowed:
            original_count = len(all_tools)
            all_tools = [
                t for t in all_tools
                if not any(t["name"].startswith(d) for d in disallowed)
            ]
            filtered_count = original_count - len(all_tools)
            if filtered_count > 0:
                logging.info(f"Stage 2: filtered {filtered_count} disallowed tools for intent '{intent}'")
            
            if not all_tools:
                logging.warning(f"Stage 2 aborted: all tools filtered for intent '{intent}'")
                return {
                    "tool": None,
                    "params": {},
                    "confidence": 0.0,
                    "domain_match": False,
                    "stage": 2,
                    "status": "capability_missing",
                    "reason": f"No suitable tools available for intent '{intent}'"
                }
        
        # STEP 3: Apply ACTION CLASS FILTER (Phase 2)
        # This is a HARD filter - no fallback if no tools match
        if action_class_filter:
            original_count = len(all_tools)
            all_tools = [
                t for t in all_tools
                if t.get("capability_class", "actuate") == action_class_filter
            ]
            filtered_count = original_count - len(all_tools)
            if filtered_count > 0:
                logging.info(f"Stage 2 action class filter: {filtered_count} tools filtered, {len(all_tools)} remain")
            
            if not all_tools:
                # HARD FAIL: No tools match capability_class in Stage 2
                logging.warning(f"Stage 2 action class hard-fail: no '{action_class}' tools for intent '{intent}'")
                return {
                    "tool": None,
                    "params": {},
                    "confidence": 0.0,
                    "domain_match": False,
                    "stage": 2,
                    "status": "capability_class_mismatch",
                    "reason": f"No tools with capability_class='{action_class}' available for intent '{intent}'"
                }
        
        stage2_result = self._resolve_with_tools(
            description, intent, context, all_tools, stage=2
        )
        
        # Apply domain mismatch penalty
        tool_name = stage2_result.get("tool")
        raw_confidence = stage2_result.get("confidence", 0)
        
        if tool_name:
            is_in_preferred = self._is_in_preferred_domain(tool_name, intent)
            
            if not is_in_preferred:
                # Penalize but don't exclude
                adjusted_confidence = max(0, raw_confidence - DOMAIN_MISMATCH_PENALTY)
                stage2_result["confidence"] = adjusted_confidence
                stage2_result["domain_match"] = False
                logging.info(f"Stage 2 domain mismatch: {tool_name} (conf: {raw_confidence:.2f} → {adjusted_confidence:.2f})")
            else:
                stage2_result["domain_match"] = True
        else:
            stage2_result["domain_match"] = False
        
        stage2_result["stage"] = 2
        logging.info(f"Stage 2 result: {stage2_result.get('tool')} (conf={stage2_result.get('confidence', 0):.2f})")
        return stage2_result
    
    def _get_preferred_tools(self, intent: str) -> List[Dict[str, Any]]:
        """Get tools from preferred domains for this intent."""
        domains = INTENT_TOOL_DOMAINS.get(intent, [])
        
        if not domains:
            return []
        
        all_tools = self.registry.get_tools_for_llm()
        return [
            t for t in all_tools
            if any(t["name"].startswith(d) for d in domains)
        ]
    
    def _is_in_preferred_domain(self, tool_name: str, intent: str) -> bool:
        """Check if tool is in preferred domain for intent."""
        domains = INTENT_TOOL_DOMAINS.get(intent, [])
        return any(tool_name.startswith(d) for d in domains)
    
    def _resolve_with_tools(self, description: str, intent: str, 
                            context: Dict[str, Any], tools: List[Dict[str, Any]],
                            stage: int) -> Dict[str, Any]:
        """Core resolution logic with given tool set."""
        # Build tool descriptions
        tools_desc = "\n".join([
            f"- {t['name']}: {t['description']}\n  Schema: {t['schema']}"
            for t in tools
        ])
        
        # Build context
        context_desc = self._format_context(context)
        
        # Generate schema with tool enum
        tool_names = [t['name'] for t in tools]
        schema = self._generate_schema(tool_names)
        
        stage_hint = f" (Stage {stage}: {'preferred domains' if stage == 1 else 'global search'})"
        
        prompt = f"""Match this request to a tool and provide parameters.{stage_hint}

Request: "{description}"
Intent: {intent}

{context_desc}

Available tools:
{tools_desc}

=============================================================================
TASK
=============================================================================

1. Find the tool that BEST matches this request
2. Provide correct parameters based on tool's schema
3. Rate your CONFIDENCE (0.0-1.0) in this match:
   - 0.9-1.0: Perfect match, exactly the right tool
   - 0.7-0.9: Good match, tool can accomplish this
   - 0.5-0.7: Partial match, might work
   - 0.0-0.5: Poor match or no suitable tool
4. If no tool can accomplish this, set tool to null

=============================================================================
RULES
=============================================================================

- Use EXACT tool names from the list
- Parameters must match tool's schema
- Be honest about confidence - don't overestimate
- If ambiguous, explain in reason field

Return JSON with tool, params, confidence, and reason.
"""
        
        try:
            result = self.model.generate(prompt, schema=schema)
            
            tool_name = result.get("tool")
            
            # Validate tool exists
            if tool_name and not self.registry.has(tool_name):
                logging.warning(f"ToolResolver: LLM returned unknown tool '{tool_name}'")
                return {
                    "tool": None,
                    "params": {},
                    "confidence": 0.0,
                    "reason": f"Tool '{tool_name}' does not exist"
                }
            
            # Ensure confidence is float
            if "confidence" in result:
                result["confidence"] = float(result["confidence"])
            else:
                result["confidence"] = 0.5  # Default if LLM omits
            
            if "reason" not in result:
                result["reason"] = "No explanation provided"
            
            # === AGGRESSIVE DEBUG: Trace resolver output ===
            logging.info(f"=== ToolResolver OUTPUT ===")
            logging.info(f"  tool: {result.get('tool')}")
            logging.info(f"  params: {result.get('params')}")
            if 'selector' in result.get('params', {}):
                logging.info(f"  params.selector: '{result['params']['selector']}'")
                logging.info(f"  params.selector repr: {repr(result['params']['selector'])}")
            
            return result
            
        except Exception as e:
            logging.error(f"ToolResolver Stage {stage} failed: {e}")
            return {
                "tool": None,
                "params": {},
                "confidence": 0.0,
                "reason": f"Resolution failed: {str(e)}"
            }
    
    def _generate_schema(self, tool_names: List[str]) -> Dict[str, Any]:
        """Generate schema with tool enum constraint."""
        import copy
        schema = copy.deepcopy(RESOLUTION_SCHEMA)
        
        if tool_names:
            schema["properties"]["tool"] = {
                "type": ["string", "null"],
                "enum": [None] + tool_names
            }
        
        return schema
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context for prompt."""
        if not context:
            return "Context: No context available"
        
        parts = ["Context:"]
        
        active_window = context.get("active_window", {})
        if active_window:
            title = active_window.get("title", "unknown")
            process = active_window.get("process_name", "unknown")
            parts.append(f"- Active window appears to be: {title} ({process})")
        
        running_apps = context.get("running_apps", [])
        if running_apps:
            parts.append(f"- Running apps: {', '.join(running_apps[:5])}")
        
        return "\n".join(parts)
    
    # Legacy method for backward compatibility
    def get_tools_for_intent(self, intent: str) -> List[Dict[str, Any]]:
        """Get tools for intent (legacy, prefer _get_preferred_tools)."""
        return self._get_preferred_tools(intent) or self.registry.get_tools_for_llm()
