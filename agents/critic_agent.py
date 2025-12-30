"""Critic Agent - Evaluates execution results

Post-execution analysis. Determines if retry is needed.
"""

import logging
from typing import Dict, Any
from models.model_manager import get_model_manager


class CriticAgent:
    """Evaluates tool execution results"""
    
    CRITIC_SCHEMA = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["success", "partial", "failure"]
            },
            "retry": {"type": "boolean"},
            "retry_reason": {"type": "string"},
            "notes": {"type": "string"},
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1
            },
            "tool_effectiveness": {
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string"},
                    "satisfaction": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1
                    },
                    "issues": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "recommendations": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            }
        },
        "required": ["status", "retry", "notes"]
    }
    
    def __init__(self):
        self.model = get_model_manager().get_critic_model()
        logging.info("CriticAgent initialized")
    
    def evaluate(self, goal: str, result: Dict[str, Any], error: str = None) -> Dict[str, Any]:
        """Evaluate execution result
        
        Args:
            goal: Original goal
            result: Tool execution result
            error: Error message if any
            
        Returns:
            {
                "status": "success",
                "retry": false,
                "notes": "Task completed successfully",
                "confidence": 0.95
            }
        """
        result_status = result.get("status", "unknown")
        result_data = result.get("data", {})
        
        prompt = f"""Evaluate this task execution:

Goal: {goal}
Result Status: {result_status}
Result Data: {result_data}
Error: {error if error else "None"}

Determine:
1. Was the task successful? (success/partial/failure)
2. Should we retry? (true/false)
3. Why retry or not retry?
4. Any notes about the execution?

Respond with JSON containing your evaluation.
"""
        
        try:
            evaluation = self.model.generate(prompt, schema=self.CRITIC_SCHEMA)
            
            # Ensure confidence is a float
            if "confidence" in evaluation:
                evaluation["confidence"] = float(evaluation.get("confidence", 0.5))
            
            logging.info(f"Critic evaluation: {evaluation.get('status')}, retry={evaluation.get('retry')}")
            return evaluation
            
        except Exception as e:
            logging.error(f"Critic evaluation failed: {e}")
            # Default to failure if evaluation fails
            return {
                "status": "failure",
                "retry": False,
                "retry_reason": f"Evaluation failed: {str(e)}",
                "notes": "Could not evaluate result",
                "confidence": 0.0
            }
    
    def evaluate_tool_effectiveness(self, tool_name: str, result: Dict[str, Any], goal: str) -> Dict[str, Any]:
        """Evaluate how well a tool performed
        
        Args:
            tool_name: Name of the tool used
            result: Tool execution result
            goal: Original goal
            
        Returns:
            {
                "tool_name": "system.display.take_screenshot",
                "satisfaction": 0.9,
                "issues": [],
                "recommendations": ["Tool worked well"]
            }
        """
        result_status = result.get("status", "unknown")
        error = result.get("error")
        
        prompt = f"""Evaluate the effectiveness of this tool execution:

Tool: {tool_name}
Goal: {goal}
Result Status: {result_status}
Error: {error if error else "None"}

Determine:
1. How satisfied are you with the result? (0.0 to 1.0)
2. What issues, if any, were encountered?
3. What recommendations do you have for improvement?

Respond with JSON containing your evaluation.
"""
        
        try:
            evaluation = self.model.generate(prompt, schema={
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string"},
                    "satisfaction": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1
                    },
                    "issues": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "recommendations": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["tool_name", "satisfaction"]
            })
            
            evaluation["tool_name"] = tool_name
            if "satisfaction" in evaluation:
                evaluation["satisfaction"] = float(evaluation.get("satisfaction", 0.5))
            
            logging.info(f"Tool effectiveness evaluated: {tool_name} - satisfaction: {evaluation.get('satisfaction', 0)}")
            return evaluation
            
        except Exception as e:
            logging.error(f"Tool effectiveness evaluation failed: {e}")
            return {
                "tool_name": tool_name,
                "satisfaction": 0.5,
                "issues": [f"Evaluation failed: {str(e)}"],
                "recommendations": []
            }

