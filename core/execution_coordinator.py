"""Execution Coordinator - LLM-driven orchestration over pipelines

ARCHITECTURE ROLE:
- Sits ABOVE pipelines as conductor
- LLM decides structure, order, iteration
- Pipelines remain deterministic syscalls

INVARIANTS:
- LLM cannot execute tools directly
- LLM cannot mutate world state
- LLM cannot bypass pipelines
- Pipelines stay frozen (unchanged)
- All tool calls logged and auditable
- Conditional target blocks must be dependency-free

EXECUTION MODES:
- direct: Single pipeline, LLM exits (gate short-circuit)
- orchestrated: Coordinator loop, LLM may iterate

NOTE: parallel_safe is declared in schema but NOT YET ENFORCED.
Execution is currently sequential. Parallel execution is a future enhancement.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Literal

from models.model_manager import get_model_manager


# =============================================================================
# SAFETY CONSTANTS
# =============================================================================

MAX_ITERATIONS = 5  # Hard safety rail - prevents infinite loops


# =============================================================================
# COORDINATOR SCHEMA (LLM output format)
# =============================================================================

COORDINATOR_SCHEMA = {
    "type": "object",
    "properties": {
        "needs_iteration": {
            "type": "boolean",
            "description": "True if LLM must observe results before continuing"
        },
        "blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Unique block identifier (b0, b1, ...)"
                    },
                    "pipeline": {
                        "type": "string",
                        "enum": ["goal", "single"],
                        "description": "goal = batch plannable goals, single = imperative action"
                    },
                    "input": {
                        "type": "string",
                        "description": "For goal pipeline: the declarative goals to plan. For single pipeline: MUST be exact text from user input, never paraphrased."
                    },
                    "source_span": {
                        "type": "string",
                        "description": "For single pipeline ONLY: the EXACT substring from user input. Required for single blocks."
                    },
                    "depends_on": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Block IDs that must complete before this"
                    },
                    "parallel_safe": {
                        "type": "boolean",
                        "description": "True if can execute in parallel with siblings"
                    }
                },
                "required": ["id", "pipeline", "input"]
            }
        },
        "conditionals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "after_block": {
                        "type": "string",
                        "description": "Block ID to evaluate after"
                    },
                    "condition": {
                        "type": "string",
                        "enum": ["success", "failure", "any", "content_empty", "content_nonempty"],
                        "description": "When to trigger: status-based (success/failure/any) or content-based (content_empty/content_nonempty)"
                    },
                    "then_block": {
                        "type": "string",
                        "description": "Block ID to execute if condition met"
                    },
                    "else_block": {
                        "type": "string",
                        "description": "Block ID to execute if condition not met"
                    }
                },
                "required": ["after_block", "condition"]
            }
        },
        "stop_when": {
            "type": "string",
            "enum": ["completion", "condition_met", "failure", "explicit"],
            "description": "When to stop the orchestration loop"
        },
        "reasoning": {
            "type": "string",
            "description": "Brief explanation of the execution plan"
        }
    },
    "required": ["needs_iteration", "blocks", "stop_when"]
}


# =============================================================================
# COORDINATOR PROMPT
# =============================================================================

COORDINATOR_PROMPT = """You are an execution planner for a desktop assistant.

Your job is to decompose a user request into execution blocks that can be run by pipelines.

## Available Pipelines

1. **goal** pipeline: For plannable, declarative goals
   - Opening applications: "open chrome", "launch notepad"
   - Browser navigation: "go to youtube", "search google for X"
   - File operations: "create folder X", "delete file Y"
   
2. **single** pipeline: For imperative, context-sensitive actions
   - Media control: "pause music", "play next track"
   - System control: "set brightness to 50", "mute volume"
   - Queries: "what's the battery level", "show running apps"

## Rules

1. Group related plannable goals into ONE goal pipeline block
2. Keep imperative actions as separate single pipeline blocks
3. Mark `needs_iteration: true` ONLY if you need to see results before continuing
4. Mark `parallel_safe: true` for independent blocks (advisory, not enforced yet)
5. Use conditionals ONLY when the user explicitly requests conditional behavior
6. **CRITICAL**: Conditional target blocks (then_block, else_block) must have empty depends_on
7. Do NOT generate blocks that modify working directory or environment state (no cd, no "set directory")
8. For file locations, use explicit paths or preserve user phrases like "in D drive", "on desktop"
9. For "if empty" patterns, use `content_empty`. For "if not empty", use `content_nonempty`
10. Only file-reading actions can be sources for content-based conditionals
11. **CRITICAL**: For single pipeline blocks, `source_span` MUST be the EXACT substring from user input. NEVER paraphrase imperative commands (e.g., "unmute" must stay "unmute", not become "mute")

## User Request

{user_input}

## Context

{context}

Respond with a JSON execution plan."""


# =============================================================================
# EXECUTION COORDINATOR
# =============================================================================

class ExecutionCoordinator:
    """LLM-driven orchestration over pipelines.
    
    RESPONSIBILITY:
    - Analyze query into execution blocks
    - Dispatch to appropriate pipelines
    - Observe results (if iteration needed)
    - Decide next step
    
    DOES NOT:
    - Execute tools directly
    - Modify pipeline behavior
    - Bypass IntentAgent or GoalInterpreter
    """
    
    def __init__(self, orchestrator: "Orchestrator"):  # Forward reference
        self.orchestrator = orchestrator
        self.model = get_model_manager().get_planner_model()
        logging.info("ExecutionCoordinator initialized")
    
    def execute(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Main entry point for coordinated execution.
        
        Args:
            user_input: User's command
            context: Current system context
            
        Returns:
            Aggregated results from all executed blocks
        """
        logging.info(f"Coordinator: analyzing '{user_input[:50]}...'")
        
        # Step 1: LLM analyzes and decomposes
        try:
            plan = self._analyze(user_input, context)
        except Exception as e:
            logging.error(f"Coordinator analysis failed: {e}")
            # Fallback to single pipeline
            return self.orchestrator._process_single(user_input, context)
        
        blocks = plan.get("blocks", [])
        needs_iteration = plan.get("needs_iteration", False)
        conditionals = plan.get("conditionals", [])
        
        if not blocks:
            logging.warning("Coordinator: no blocks produced, falling back to single")
            return self.orchestrator._process_single(user_input, context)
        
        logging.info(
            f"Coordinator: {len(blocks)} block(s), "
            f"iteration={needs_iteration}, "
            f"conditionals={len(conditionals)}"
        )
        
        # Step 2: Execute blocks (pass original input for single pipeline verification)
        if not needs_iteration:
            # One-shot: execute all blocks
            return self._execute_all_blocks(blocks, context, user_input)
        else:
            # Iterative: execute with observation
            return self._execute_with_iteration(blocks, conditionals, context, user_input)
    
    def _analyze(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """LLM analyzes query and produces execution plan.
        
        THIS IS WHERE THE INTELLIGENCE LIVES.
        """
        from core.context_snapshot import ContextSnapshot
        
        # Format context for prompt
        context_str = ContextSnapshot.build(context)
        
        prompt = COORDINATOR_PROMPT.format(
            user_input=user_input,
            context=context_str
        )
        
        result = self.model.generate(prompt, schema=COORDINATOR_SCHEMA)
        
        logging.info(f"Coordinator analysis: {result.get('reasoning', 'N/A')}")
        
        return result
    
    def _execute_all_blocks(
        self, 
        blocks: List[Dict], 
        context: Dict[str, Any],
        original_input: str = ""
    ) -> Dict[str, Any]:
        """Execute all blocks without iteration (one-shot).
        
        NOTE: Currently sequential execution only.
        parallel_safe is advisory - parallel execution not yet implemented.
        """
        results = []
        
        # Sequential execution (parallel_safe not enforced yet)
        for block in blocks:
            result = self._execute_block(block, context, original_input)
            normalized_status = self._normalize_status(result)
            results.append({
                "block_id": block["id"],
                "status": normalized_status,
                "result": result
            })
        
        return self._summarize_results(results)
    
    def _execute_with_iteration(
        self,
        blocks: List[Dict],
        conditionals: List[Dict],
        context: Dict[str, Any],
        original_input: str = ""
    ) -> Dict[str, Any]:
        """Execute blocks with observation and conditional branching."""
        results = []
        executed_ids = set()
        iteration_count = 0
        
        # Build execution queue (respecting dependencies)
        pending = list(blocks)
        
        while pending and iteration_count < MAX_ITERATIONS:
            iteration_count += 1
            
            # Find next executable block
            block = self._find_next_block(pending, executed_ids)
            
            if block is None:
                logging.warning("Coordinator: no executable block found, stopping")
                break
            
            # Execute block
            logging.info(f"Coordinator: executing block {block['id']}")
            result = self._execute_block(block, context, original_input)
            normalized_status = self._normalize_status(result)
            
            results.append({
                "block_id": block["id"],
                "status": normalized_status,
                "result": result
            })
            executed_ids.add(block["id"])
            pending.remove(block)
            
            # Evaluate conditionals
            next_action = self._evaluate_conditionals(
                conditionals, block["id"], result
            )
            
            if next_action.get("action") == "stop":
                logging.info("Coordinator: conditional triggered stop")
                break
            elif next_action.get("action") == "skip_to":
                # Remove blocks until we hit the target
                target_id = next_action.get("target")
                pending = [b for b in pending if b["id"] == target_id]
        
        if iteration_count >= MAX_ITERATIONS:
            logging.error(f"Coordinator: MAX_ITERATIONS ({MAX_ITERATIONS}) reached, forcing stop")
            results.append({
                "block_id": "safety_stop",
                "status": "error",
                "result": {"error": "Maximum iterations exceeded"}
            })
        
        return self._summarize_results(results)
    
    def _find_next_block(
        self, 
        pending: List[Dict], 
        executed: set
    ) -> Optional[Dict]:
        """Find next block whose dependencies are satisfied."""
        for block in pending:
            deps = block.get("depends_on", [])
            if all(d in executed for d in deps):
                return block
        return None
    
    def _execute_block(
        self, 
        block: Dict, 
        context: Dict[str, Any],
        original_input: str = ""
    ) -> Dict[str, Any]:
        """Dispatch block to appropriate pipeline.
        
        INVARIANT: For single pipeline, we use source_span or original_input
        to preserve exact user semantics. LLM must never paraphrase imperatives.
        """
        pipeline = block.get("pipeline", "single")
        
        if pipeline == "goal":
            # Goal pipeline: LLM can compose declarative text
            input_str = block.get("input", "")
            logging.info(f"Coordinator: dispatching to goal pipeline: {input_str[:50]}")
            return self.orchestrator._process_goal(input_str, context)
        else:
            # Single pipeline: MUST use exact user text, never LLM-generated
            # Priority: source_span > input (if exact) > original_input
            source_span = block.get("source_span", "")
            input_str = block.get("input", "")
            
            # Use source_span if provided (preferred)
            if source_span and source_span.lower() in original_input.lower():
                execution_input = source_span
                logging.info(f"Coordinator: using source_span for single pipeline: {source_span}")
            # Otherwise check if input is exact substring of original
            elif input_str and input_str.lower() in original_input.lower():
                execution_input = input_str
                logging.info(f"Coordinator: using verified input for single pipeline: {input_str}")
            else:
                # Fallback: Log warning, use input but this may be paraphrased
                execution_input = input_str or original_input
                logging.warning(
                    f"Coordinator: single block input may be paraphrased. "
                    f"source_span='{source_span}', input='{input_str}', original='{original_input[:30]}'"
                )
            
            logging.info(f"Coordinator: dispatching to single pipeline: {execution_input[:50]}")
            return self.orchestrator._process_single(execution_input, context)
    
    def _evaluate_conditionals(
        self,
        conditionals: List[Dict],
        block_id: str,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate conditionals after block execution.
        
        Supports both status-based (success/failure/any) and content-based
        (content_empty/content_nonempty) conditions.
        
        INVARIANT: Content-based conditions require observable content in result.
        If content is missing, the condition does NOT trigger.
        """
        normalized_status = self._normalize_status(result)
        
        for cond in conditionals:
            if cond.get("after_block") != block_id:
                continue
            
            condition = cond.get("condition", "any")
            
            # Evaluate condition
            triggered = False
            
            # Status-based conditions
            if condition == "success" and normalized_status == "success":
                triggered = True
            elif condition == "failure" and normalized_status == "failure":
                triggered = True
            elif condition == "any":
                triggered = True
            
            # Content-based conditions
            elif condition in ("content_empty", "content_nonempty"):
                # Extract content from nested result structure
                # Pipeline returns: {status, result: {content: "..."}, ...}
                content = self._extract_content(result)
                
                if content is not None:
                    is_empty = content.strip() == ""
                    if condition == "content_empty" and is_empty:
                        triggered = True
                        logging.info(f"Conditional: content_empty triggered (content is empty)")
                    elif condition == "content_nonempty" and not is_empty:
                        triggered = True
                        logging.info(f"Conditional: content_nonempty triggered (content has {len(content)} chars)")
                else:
                    # No content found - do NOT trigger, log warning
                    logging.warning(
                        f"Conditional: {condition} cannot evaluate - no content in result. "
                        f"Only file-reading actions can be sources for content-based conditionals."
                    )
            
            # Determine branch
            if triggered:
                if cond.get("then_block"):
                    return {"action": "skip_to", "target": cond["then_block"]}
                elif cond.get("else_block") and not triggered:
                    return {"action": "skip_to", "target": cond["else_block"]}
            else:
                # Condition not met, check else_block
                if cond.get("else_block"):
                    return {"action": "skip_to", "target": cond["else_block"]}
        
        return {"action": "continue"}
    
    def _extract_content(self, result: Dict[str, Any]) -> Optional[str]:
        """Extract observable content from pipeline result.
        
        Handles nested result structures from different pipelines.
        
        Returns:
            Content string if found, None if not observable.
        """
        # Direct content in result
        if "content" in result:
            return result["content"]
        
        # Nested in 'result' key (goal pipeline structure)
        nested = result.get("result", {})
        if isinstance(nested, dict) and "content" in nested:
            return nested["content"]
        
        # Check in results array (multi-action goal pipeline)
        results_list = result.get("results", [])
        for r in results_list:
            if isinstance(r, dict):
                # Check nested result within each item
                inner = r.get("result", {})
                if isinstance(inner, dict) and "content" in inner:
                    return inner["content"]
        
        return None
    
    def _normalize_status(self, result: Dict[str, Any]) -> str:
        """Normalize pipeline status to success/failure.
        
        Pipelines return various statuses:
        - success, error, failed, partial, needs_fallback, blocked, etc.
        
        For conditionals, we reduce to binary: success or failure.
        """
        status = result.get("status", "unknown")
        if status == "success":
            return "success"
        return "failure"
    
    def _summarize_results(self, results: List[Dict]) -> Dict[str, Any]:
        """Aggregate block results into final response."""
        success_count = sum(1 for r in results if r["status"] == "success")
        total = len(results)
        
        if success_count == total:
            status = "success"
            response = f"Completed all {total} block(s)"
        elif success_count > 0:
            status = "partial"
            response = f"Completed {success_count} of {total} block(s)"
        else:
            status = "error"
            response = "All blocks failed"
        
        return {
            "status": status,
            "type": "coordinated",
            "response": response,
            "blocks": results,
            "total_blocks": total,
            "successful_blocks": success_count
        }
