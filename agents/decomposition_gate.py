"""Decomposition Gate v2 - Semantic Segmentation with Action Extraction

RESPONSIBILITY: Detect executable actions and their dependencies.

Question answered:
"How many executable actions exist in this prompt?"

NOT: what the actions do, how to execute them, or if they're feasible.

CRITICAL RULE:
If the user request requires performing actions in SEQUENCE
(e.g., open X then do Y), classify as MULTI even if it's one sentence.
"""

import logging
from typing import Dict, Any, List
from models.model_manager import get_model_manager


class DecompositionGate:
    """Semantic segmentation gate with action extraction.
    
    Uses mistral-7B for verb + dependency reasoning.
    Outputs structured action list, not just single/multi boolean.
    
    INVARIANTS:
    - Detects executable verbs and their count
    - Detects implicit sequencing ("and then", "after", "then")
    - Does NOT infer feasibility, safety, or capability
    """
    
    GATE_SCHEMA = {
        "type": "object",
        "properties": {
            "classification": {
                "type": "string",
                "enum": ["single", "multi"]
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of action count"
            },
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Short description of the action"
                        },
                        "depends_on_previous": {
                            "type": "boolean",
                            "description": "True if this action requires the previous action to complete first"
                        }
                    },
                    "required": ["description", "depends_on_previous"]
                },
                "description": "List of executable actions in order"
            }
        },
        "required": ["classification", "reasoning", "actions"]
    }
    
    # Few-shot examples for reliable classification
    FEW_SHOT_EXAMPLES = """
## FEW-SHOT EXAMPLES (learn from these):

### SINGLE (one executable action)
User: "take a screenshot"
→ {"classification": "single", "reasoning": "One action: capture screen", "actions": [{"description": "take screenshot", "depends_on_previous": false}]}

User: "what time is it"
→ {"classification": "single", "reasoning": "One query: get time", "actions": [{"description": "get current time", "depends_on_previous": false}]}

User: "increase the volume"
→ {"classification": "single", "reasoning": "One action: adjust volume", "actions": [{"description": "increase volume", "depends_on_previous": false}]}

User: "open notepad"
→ {"classification": "single", "reasoning": "One action: launch application", "actions": [{"description": "open notepad", "depends_on_previous": false}]}

### MULTI (multiple executable actions with sequencing)
User: "open notepad and type hello"
→ {"classification": "multi", "reasoning": "Two actions: open app, then type text. Typing requires notepad to be open.", "actions": [{"description": "open notepad", "depends_on_previous": false}, {"description": "type hello", "depends_on_previous": true}]}

User: "open chrome and search for AI"
→ {"classification": "multi", "reasoning": "Two actions: launch browser, then search. Searching requires browser to be open.", "actions": [{"description": "open chrome", "depends_on_previous": false}, {"description": "search for AI", "depends_on_previous": true}]}

User: "take a screenshot and save it to documents"
→ {"classification": "multi", "reasoning": "Two actions: capture screen, then save file. Saving requires screenshot to exist.", "actions": [{"description": "take screenshot", "depends_on_previous": false}, {"description": "save to documents", "depends_on_previous": true}]}

User: "focus notepad, type hello, and press enter"
→ {"classification": "multi", "reasoning": "Three sequential actions with dependencies.", "actions": [{"description": "focus notepad", "depends_on_previous": false}, {"description": "type hello", "depends_on_previous": true}, {"description": "press enter", "depends_on_previous": true}]}

User: "increase volume and take a screenshot"
→ {"classification": "multi", "reasoning": "Two independent actions, no dependencies.", "actions": [{"description": "increase volume", "depends_on_previous": false}, {"description": "take screenshot", "depends_on_previous": false}]}

### FILE OPERATIONS (Important: these are SINGLE atomic operations!)
User: "write hello world into notes.txt"
→ {"classification": "single", "reasoning": "One action: write content to file (files.write_file handles this atomically)", "actions": [{"description": "write 'hello world' to notes.txt", "depends_on_previous": false}]}

User: "create a file called test.txt with content hello"
→ {"classification": "single", "reasoning": "One action: create file with content (files.create_file handles this atomically)", "actions": [{"description": "create test.txt with content 'hello'", "depends_on_previous": false}]}

User: "append goodbye to notes.txt"
→ {"classification": "single", "reasoning": "One action: append to file", "actions": [{"description": "append 'goodbye' to notes.txt", "depends_on_previous": false}]}

User: "delete the old logs"
→ {"classification": "single", "reasoning": "One action: delete file", "actions": [{"description": "delete old logs", "depends_on_previous": false}]}

User: "read config.json"
→ {"classification": "single", "reasoning": "One action: read file", "actions": [{"description": "read config.json", "depends_on_previous": false}]}

User: "list files in downloads"
→ {"classification": "single", "reasoning": "One action: list directory", "actions": [{"description": "list files in downloads", "depends_on_previous": false}]}

### MULTI FILE OPERATIONS (only when truly separate steps)
User: "create a folder called projects and put a readme.txt inside it"
→ {"classification": "multi", "reasoning": "Two actions: create folder, then create file inside. File creation depends on folder existing.", "actions": [{"description": "create folder 'projects'", "depends_on_previous": false}, {"description": "create readme.txt in projects folder", "depends_on_previous": true}]}

### CRITICAL DISTINCTIONS:
- "write X into FILE" = SINGLE (file operation is atomic)
- "create FILE with content X" = SINGLE (file operation is atomic)
- "append X to FILE" = SINGLE (file operation is atomic)
- "create FOLDER and put FILE inside" = MULTI (folder then file)
- "open X AND do Y" = MULTI (sequencing via "and")
- "do X then do Y" = MULTI (explicit sequencing)
- "do X, Y, and Z" = MULTI (list of actions)
- "do X" = SINGLE (one action only)
"""
    
    def __init__(self):
        # Use planner model (mistral:7b) for verb + dependency reasoning
        self.model = get_model_manager().get_planner_model()
        logging.info("DecompositionGate v2 initialized (semantic segmentation)")
    
    def classify(self, user_input: str) -> str:
        """Classify input as single or multi-goal.
        
        For backward compatibility, returns just the classification string.
        Use classify_with_actions() for full structured output.
        
        Args:
            user_input: Raw user command
            
        Returns:
            "single" or "multi"
        """
        result = self.classify_with_actions(user_input)
        return result.get("classification", "single")
    
    def classify_with_actions(self, user_input: str) -> Dict[str, Any]:
        """Full semantic segmentation with action extraction.
        
        Args:
            user_input: Raw user command
            
        Returns:
            {
                "classification": "single" | "multi",
                "reasoning": "...",
                "actions": [
                    {"description": "...", "depends_on_previous": bool},
                    ...
                ]
            }
        """
        prompt = f"""You are an action segmentation agent.

Your job: Count executable actions in a user request and detect dependencies.

{self.FEW_SHOT_EXAMPLES}

---

NOW ANALYZE THIS INPUT:
User: "{user_input}"

RULES:
1. Count how many DISTINCT executable actions exist
2. If actions must happen in sequence (open X THEN do Y), classify as MULTI
3. Detect implicit dependencies (e.g., typing requires a focused window)
4. The word "and" between verbs usually means MULTI
5. Do NOT consider feasibility or system capabilities

Return JSON with:
- classification: "single" or "multi"
- reasoning: brief explanation (1 sentence)
- actions: list of actions with depends_on_previous flag
"""
        
        try:
            result = self.model.generate(prompt, schema=self.GATE_SCHEMA)
            
            classification = result.get("classification", "single")
            actions = result.get("actions", [])
            reasoning = result.get("reasoning", "No reasoning provided")
            
            # Safety: if we got multiple actions, force multi classification
            if len(actions) > 1 and classification == "single":
                logging.warning(f"Gate conflict: {len(actions)} actions but classified as single, forcing multi")
                classification = "multi"
                result["classification"] = "multi"
            
            logging.info(
                f"DecompositionGate: '{user_input[:50]}...' → {classification} "
                f"({len(actions)} action(s))"
            )
            logging.debug(f"Actions: {actions}")
            
            return result
            
        except Exception as e:
            logging.warning(f"DecompositionGate failed: {e}, defaulting to single")
            return {
                "classification": "single",
                "reasoning": f"Error: {str(e)}",
                "actions": [{"description": user_input, "depends_on_previous": False}]
            }
    
    def get_action_descriptions(self, user_input: str) -> List[str]:
        """Convenience method to get just action descriptions.
        
        Useful for passing to TDA or multi-pipeline.
        """
        result = self.classify_with_actions(user_input)
        return [a.get("description", "") for a in result.get("actions", [])]
