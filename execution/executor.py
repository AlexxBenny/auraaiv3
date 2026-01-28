"""Tool Executor - Executes tools deterministically

NO AI. NO retries. NO recursion. Just execution.

Phase 2B' Safety Features:
- Modifier key kill-switch (pressed_keys tracking)
- Executor cooldown support (for explorer restart, etc.)
- Key release on any failure
"""

import time
import logging
from typing import Dict, Any, List, Set, Optional
from tools.registry import get_registry
from tools.base import Tool


class ToolExecutor:
    """Executes tool execution plans
    
    Safety Features:
    - pressed_keys: Tracks modifier keys currently held down
    - cooldown_until: Blocks execution until this timestamp
    - _release_all_keys(): Emergency key release on failure
    """
    
    def __init__(self):
        self.registry = get_registry()
        
        # Phase 2B' Safety: Modifier key tracking
        self.pressed_keys: Set[str] = set()
        
        # Phase 2B' Safety: Executor cooldown (e.g., after explorer restart)
        self.cooldown_until: float = 0.0
        
        logging.info("ToolExecutor initialized with Phase 2B' safety features")
    
    def execute_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a complete plan
        
        HARD GUARD: Only executes if action_type == "action"
        
        Args:
            plan: Plan from PlannerAgent (must have steps to execute)
            
        Returns:
            {
                "status": "success",
                "results": [...],
                "errors": [...]
            }
            
        Raises:
            RuntimeError: If no steps are present
        """
        steps = plan.get("steps", [])
        
        # =========================================================================
        # MODERN EXECUTION GUARD (2024-2025)
        # =========================================================================
        # Primary check: Steps must be present
        # action_type is advisory (LLM output, not authoritative)
        # Neo4j eligibility is checked BEFORE this point by PlannerAgent
        # =========================================================================
        if not steps:
            raise RuntimeError(
                "CRITICAL: ToolExecutor called with no steps. "
                "Nothing to execute. This is a logic error."
            )
        
        results = []
        errors = []
        
        for i, step in enumerate(steps):
            tool_name = step.get("tool")
            args = step.get("args", {})
            
            logging.info(f"Executing step {i+1}/{len(steps)}: {tool_name}")
            
            # Get tool
            tool = self.registry.get(tool_name)
            if not tool:
                error_msg = f"Tool '{tool_name}' not found in registry"
                logging.error(error_msg)
                errors.append({
                    "step": i + 1,
                    "tool": tool_name,
                    "error": error_msg
                })
                continue
            
            # Validate arguments
            if not tool.validate_args(args):
                error_msg = f"Invalid arguments for tool '{tool_name}'"
                logging.error(error_msg)
                errors.append({
                    "step": i + 1,
                    "tool": tool_name,
                    "error": error_msg
                })
                continue
            
            # Execute tool
            try:
                result = tool.execute(args)
                results.append({
                    "step": i + 1,
                    "tool": tool_name,
                    "result": result
                })
                
                # If tool failed, record error
                if result.get("status") != "success":
                    errors.append({
                        "step": i + 1,
                        "tool": tool_name,
                        "error": result.get("error", "Tool execution failed")
                    })
                    
            except Exception as e:
                error_msg = f"Tool execution error: {str(e)}"
                logging.error(error_msg)
                errors.append({
                    "step": i + 1,
                    "tool": tool_name,
                    "error": error_msg
                })
        
        # Determine overall status
        if not errors:
            status = "success"
        elif len(errors) < len(steps):
            status = "partial"
        else:
            status = "failure"
        
        return {
            "status": status,
            "results": results,
            "errors": errors
        }
    
    def execute_step(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single tool step with mandatory precondition enforcement.
        
        CRITICAL: LLMs cannot be trusted with safety invariants.
        Preconditions are enforced HERE, not by prompts.
        
        Phase 2B' Safety:
        - Cooldown check before execution
        - Key release on any failure
        
        Args:
            tool_name: Name of tool
            args: Tool arguments
            
        Returns:
            Tool execution result
        """
        # =====================================================================
        # PHASE 2B' SAFETY: COOLDOWN CHECK
        # =====================================================================
        cooldown_result = self._check_cooldown()
        if cooldown_result:
            return cooldown_result
        
        tool = self.registry.get(tool_name)
        if not tool:
            return {
                "status": "error",
                "error": f"Tool '{tool_name}' not found"
            }
        
        if not tool.validate_args(args):
            return {
                "status": "error",
                "error": f"Invalid arguments for tool '{tool_name}'"
            }
        
        # =====================================================================
        # MANDATORY PRECONDITION ENFORCEMENT
        # =====================================================================
        # These checks are NON-NEGOTIABLE. The LLM does not get a vote.
        # =====================================================================
        
        precondition_result = self._check_preconditions(tool)
        if not precondition_result["satisfied"]:
            logging.warning(f"Precondition failed for {tool_name}: {precondition_result['reason']}")
            return {
                "status": "blocked",
                "error": precondition_result["reason"],
                "precondition_failed": precondition_result["failed_check"]
            }
        
        # =====================================================================
        # PHASE 2B' SAFETY: EXECUTE WITH KEY RELEASE GUARANTEE
        # =====================================================================
        try:
            result = tool.execute(args)
            
            # Handle cooldown requests from tools (e.g., explorer restart)
            if result.get("cooldown_ms"):
                self.set_cooldown(result["cooldown_ms"])
            
            return result
        except Exception as e:
            # CRITICAL: Release all modifier keys on ANY failure
            self._release_all_keys()
            return {
                "status": "error",
                "error": str(e)
            }
    
    # =========================================================================
    # PHASE 2B' SAFETY METHODS
    # =========================================================================
    
    def _release_all_keys(self) -> None:
        """Emergency release of all tracked modifier keys.
        
        Called on any tool failure to prevent stuck keys.
        Uses pyautogui for reliable key release.
        """
        if not self.pressed_keys:
            return
        
        try:
            import pyautogui
            for key in list(self.pressed_keys):
                try:
                    pyautogui.keyUp(key)
                    logging.warning(f"Emergency key release: {key}")
                except Exception as e:
                    logging.error(f"Failed to release key {key}: {e}")
            self.pressed_keys.clear()
        except ImportError:
            logging.error("pyautogui not available for emergency key release")
            self.pressed_keys.clear()
    
    def _check_cooldown(self) -> Optional[Dict[str, Any]]:
        """Check if executor is in cooldown period.
        
        Returns:
            None if no cooldown active, or error dict if cooldown blocks execution
        """
        if self.cooldown_until > 0:
            remaining = self.cooldown_until - time.time()
            if remaining > 0:
                return {
                    "status": "blocked",
                    "error": f"Executor in cooldown for {remaining:.1f}s (previous tool requested stabilization)",
                    "cooldown_remaining_ms": int(remaining * 1000)
                }
            else:
                # Cooldown expired, reset
                self.cooldown_until = 0.0
        return None
    
    def set_cooldown(self, duration_ms: int) -> None:
        """Set executor cooldown period.
        
        Args:
            duration_ms: Cooldown duration in milliseconds
        """
        self.cooldown_until = time.time() + (duration_ms / 1000.0)
        logging.info(f"Executor cooldown set for {duration_ms}ms")
    
    def register_key_press(self, key: str) -> None:
        """Register a modifier key as pressed (for tracking).
        
        Tools should call this before keyDown operations.
        """
        self.pressed_keys.add(key.lower())
        logging.debug(f"Key registered as pressed: {key}")
    
    def register_key_release(self, key: str) -> None:
        """Register a modifier key as released.
        
        Tools should call this after keyUp operations.
        """
        self.pressed_keys.discard(key.lower())
        logging.debug(f"Key registered as released: {key}")
    
    def _check_preconditions(self, tool: Tool) -> Dict[str, Any]:
        """Enforce tool preconditions. Returns satisfied/reason/failed_check."""
        import win32gui
        import win32process
        import psutil
        
        # Check 1: Unlocked screen (most restrictive)
        if tool.requires_unlocked_screen:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd == 0:
                return {
                    "satisfied": False,
                    "reason": "Screen appears to be locked (no foreground window)",
                    "failed_check": "requires_unlocked_screen"
                }
        
        # Check 2: Focused window required
        if tool.requires_focus:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd == 0:
                return {
                    "satisfied": False,
                    "reason": "No window is focused. Tool requires an active window.",
                    "failed_check": "requires_focus"
                }
            title = win32gui.GetWindowText(hwnd)
            if not title or title.strip() == "":
                return {
                    "satisfied": False,
                    "reason": "Focused window has no title (may be desktop or system UI)",
                    "failed_check": "requires_focus"
                }
        
        # Check 3: Specific app required
        required_app = tool.requires_active_app
        if required_app:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd == 0:
                return {
                    "satisfied": False,
                    "reason": f"No window focused, but tool requires '{required_app}'",
                    "failed_check": "requires_active_app"
                }
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                process = psutil.Process(pid)
                process_name = process.name().lower()
                if required_app.lower() not in process_name:
                    title = win32gui.GetWindowText(hwnd)
                    return {
                        "satisfied": False,
                        "reason": f"Tool requires '{required_app}' but active window is '{process_name}' ({title})",
                        "failed_check": "requires_active_app"
                    }
            except Exception as e:
                return {
                    "satisfied": False,
                    "reason": f"Could not verify active app: {e}",
                    "failed_check": "requires_active_app"
                }
        
        return {"satisfied": True, "reason": None, "failed_check": None}
    
    # Alias for pipeline compatibility
    execute_tool = execute_step
