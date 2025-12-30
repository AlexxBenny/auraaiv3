"""Tool Executor - Executes tools deterministically

NO AI. NO retries. NO recursion. Just execution.
"""

import logging
from typing import Dict, Any, List
from tools.registry import get_registry
from tools.base import Tool


class ToolExecutor:
    """Executes tool execution plans"""
    
    def __init__(self):
        self.registry = get_registry()
        logging.info("ToolExecutor initialized")
    
    def execute_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a complete plan
        
        Args:
            plan: Plan from PlannerAgent
            
        Returns:
            {
                "status": "success",
                "results": [...],
                "errors": [...]
            }
        """
        steps = plan.get("steps", [])
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
        """Execute a single tool step
        
        Args:
            tool_name: Name of tool
            args: Tool arguments
            
        Returns:
            Tool execution result
        """
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
        
        try:
            return tool.execute(args)
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

