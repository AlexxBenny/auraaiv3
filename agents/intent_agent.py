"""Intent Agent - Classifies user intent with few-shot examples

CRITICAL: This is the FIRST gate in the pipeline.
Wrong classification = wrong tools = wrong execution.

LLM-CENTRIC ARCHITECTURE:
- Receives system state context via ContextSnapshot
- Decides whether to act or ask for clarification
- Uses context to resolve ambiguity (e.g., "play" when media is paused)

Uses mistral:7b for better reasoning.
Includes 2-3 few-shot examples per intent for reliability.
"""

import logging
from typing import Dict, Any, Optional
from models.model_manager import get_model_manager
from core.context_snapshot import ContextSnapshot


class IntentAgent:
    """Classifies user intent into 10 precise categories
    
    Design principles:
    - Every existing tool must map to exactly one intent
    - Few-shot examples prevent misclassification
    - Output includes reasoning for debugging
    """
    
    INTENT_SCHEMA = {
        "type": "object",
        "properties": {
            "decision": {
                "type": "string",
                "enum": ["execute", "ask"],
                "description": "Execute the intent or ask for clarification"
            },
            "intent": {
                "type": "string",
                "enum": [
                    "application_launch",      # Open/start applications
                    "application_control",     # Focus, close, switch windows
                    "window_management",       # Snap, minimize, maximize, switch windows, virtual desktops
                    "system_query",            # Time, battery, system state (read-only)
                    "system_control",          # Volume, brightness, lock, power (actions)
                    "screen_capture",          # Screenshots, screen recording
                    "screen_perception",       # OCR, find text on screen
                    "input_control",           # Keyboard, mouse actions
                    "file_operation",          # Create, read, write, delete files
                    "browser_control",         # Web navigation, tabs
                    "office_operation",        # Excel, Word, PowerPoint
                    "clipboard_operation",     # Copy, paste, clipboard
                    "memory_recall",           # Asking about previous queries/facts
                    "information_query",       # Questions answerable by LLM
                    "unknown"                  # Cannot determine
                ]
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of classification"
            },
            "question": {
                "type": "string",
                "description": "Clarification question if decision is 'ask'"
            }
        },
        "required": ["decision", "intent", "confidence", "reasoning"]
    }
    
    # Few-shot examples for reliable classification
    FEW_SHOT_EXAMPLES = """
## FEW-SHOT EXAMPLES (learn from these):

### application_launch
User: "open notepad"
→ {"intent": "application_launch", "confidence": 0.95, "reasoning": "User wants to start an application"}

User: "launch spotify"
→ {"intent": "application_launch", "confidence": 0.95, "reasoning": "Launching an app by name"}

User: "start chrome"
→ {"intent": "application_launch", "confidence": 0.95, "reasoning": "Starting a browser application"}

### application_control (NOT launch!)
User: "focus on notepad"
→ {"intent": "application_control", "confidence": 0.95, "reasoning": "Switching to existing window, not launching"}

User: "close this window"
→ {"intent": "application_control", "confidence": 0.95, "reasoning": "Closing existing window"}

User: "minimize spotify"
→ {"intent": "application_control", "confidence": 0.90, "reasoning": "Window management, not launch"}

### window_management (NEW - window geometry/arrangement)
User: "snap this window to the left"
→ {"intent": "window_management", "confidence": 0.95, "reasoning": "Window positioning/snapping"}

User: "minimize all windows"
→ {"intent": "window_management", "confidence": 0.95, "reasoning": "Desktop-level window action"}

User: "switch to the next window"
→ {"intent": "window_management", "confidence": 0.90, "reasoning": "Alt+Tab style window switching"}

User: "open task view"
→ {"intent": "window_management", "confidence": 0.95, "reasoning": "Virtual desktop overview"}

User: "move this to desktop 2"
→ {"intent": "window_management", "confidence": 0.95, "reasoning": "Virtual desktop window movement"}

User: "maximize this window"
→ {"intent": "window_management", "confidence": 0.95, "reasoning": "Window geometry change"}

User: "snap right"
→ {"intent": "window_management", "confidence": 0.95, "reasoning": "Window snapping action"}

### system_query (read-only state queries)
User: "what time is it"
→ {"intent": "system_query", "confidence": 0.95, "reasoning": "Asking for system clock, read-only"}

User: "what year is this"
→ {"intent": "system_query", "confidence": 0.95, "reasoning": "Asking for current date/year, system tool handles this"}

User: "what's the date today"
→ {"intent": "system_query", "confidence": 0.95, "reasoning": "Asking for current date, read-only system query"}

User: "what day is it"
→ {"intent": "system_query", "confidence": 0.95, "reasoning": "Asking for day of week, system datetime query"}

User: "what's my battery level"
→ {"intent": "system_query", "confidence": 0.95, "reasoning": "System state query, read-only"}

User: "how much disk space do I have"
→ {"intent": "system_query", "confidence": 0.90, "reasoning": "System resource query, read-only"}

User: "what is the current volume"
→ {"intent": "system_query", "confidence": 0.90, "reasoning": "Querying audio state, not changing it"}

### system_control (NOT system_query - these CHANGE system state!)
User: "set volume to 50"
→ {"intent": "system_control", "confidence": 0.95, "reasoning": "Changing system volume, this is an ACTION"}

User: "mute the audio"
→ {"intent": "system_control", "confidence": 0.95, "reasoning": "Changing audio state, not querying"}

User: "set brightness to 80"
→ {"intent": "system_control", "confidence": 0.95, "reasoning": "Changing display brightness"}

User: "lock my computer"
→ {"intent": "system_control", "confidence": 0.95, "reasoning": "Power/security action"}

User: "turn on night light"
→ {"intent": "system_control", "confidence": 0.90, "reasoning": "Changing display settings"}

### clipboard_operation
User: "copy hello to clipboard"
→ {"intent": "clipboard_operation", "confidence": 0.95, "reasoning": "Clipboard write operation"}

User: "what's in my clipboard"
→ {"intent": "clipboard_operation", "confidence": 0.90, "reasoning": "Clipboard read operation"}

User: "paste this text"
→ {"intent": "clipboard_operation", "confidence": 0.90, "reasoning": "Clipboard paste operation"}

### memory_recall (NEW - asking about PREVIOUS queries)
User: "what was my RAM usage earlier"
→ {"intent": "memory_recall", "confidence": 0.95, "reasoning": "Asking about previously queried information"}

User: "what did I check before"
→ {"intent": "memory_recall", "confidence": 0.90, "reasoning": "Recalling previous system queries"}

User: "what was my battery level earlier"
→ {"intent": "memory_recall", "confidence": 0.95, "reasoning": "Asking about previous battery check"}

User: "what did I ask you about disk space"
→ {"intent": "memory_recall", "confidence": 0.90, "reasoning": "Recalling previous disk query"}


### screen_capture (NOT application_launch!)
User: "take a screenshot"
→ {"intent": "screen_capture", "confidence": 0.98, "reasoning": "Capturing screen, NOT launching screenshot app"}

User: "capture my screen"
→ {"intent": "screen_capture", "confidence": 0.95, "reasoning": "Screen capture action"}

User: "screenshot this"
→ {"intent": "screen_capture", "confidence": 0.95, "reasoning": "Taking screenshot"}

### screen_perception
User: "find the submit button"
→ {"intent": "screen_perception", "confidence": 0.95, "reasoning": "Looking for UI element on screen"}

User: "where is the login text"
→ {"intent": "screen_perception", "confidence": 0.90, "reasoning": "OCR/visual search needed"}

### input_control
User: "type hello world"
→ {"intent": "input_control", "confidence": 0.95, "reasoning": "Keyboard input action"}

User: "click on the file menu"
→ {"intent": "input_control", "confidence": 0.90, "reasoning": "Mouse click action"}

User: "press enter"
→ {"intent": "input_control", "confidence": 0.95, "reasoning": "Key press action"}

### file_operation
User: "create a file called notes.txt"
→ {"intent": "file_operation", "confidence": 0.95, "reasoning": "File creation"}

User: "delete the old logs"
→ {"intent": "file_operation", "confidence": 0.90, "reasoning": "File deletion"}

User: "read the config file"
→ {"intent": "file_operation", "confidence": 0.90, "reasoning": "File reading"}

User: "list files in my downloads"
→ {"intent": "file_operation", "confidence": 0.95, "reasoning": "Directory listing"}

User: "move notes.txt to documents"
→ {"intent": "file_operation", "confidence": 0.95, "reasoning": "File move operation"}

User: "copy config.json to backup folder"
→ {"intent": "file_operation", "confidence": 0.95, "reasoning": "File copy operation"}

User: "rename todo.txt to done.txt"
→ {"intent": "file_operation", "confidence": 0.95, "reasoning": "File rename"}

User: "create a folder called projects and put a readme.txt inside"
→ {"intent": "file_operation", "confidence": 0.95, "reasoning": "Multi-step: folder + file creation"}

User: "what's in the downloads folder"
→ {"intent": "file_operation", "confidence": 0.90, "reasoning": "Directory listing query"}

### browser_control
User: "open chrome"
→ {"intent": "browser_control", "confidence": 0.95, "reasoning": "Browser launch"}

User: "open google.com"
→ {"intent": "browser_control", "confidence": 0.90, "reasoning": "Web navigation"}

User: "close this tab"
→ {"intent": "browser_control", "confidence": 0.85, "reasoning": "Browser tab control"}

### office_operation
User: "write hello in cell A1"
→ {"intent": "office_operation", "confidence": 0.95, "reasoning": "Excel operation"}

User: "format this text as bold"
→ {"intent": "office_operation", "confidence": 0.85, "reasoning": "Word formatting"}

### information_query (ONLY if LLM can answer without tools)
User: "what is the capital of France"
→ {"intent": "information_query", "confidence": 0.95, "reasoning": "General knowledge, no tool needed"}

User: "explain quantum physics"
→ {"intent": "information_query", "confidence": 0.95, "reasoning": "Knowledge question, LLM can answer"}

User: "how do I use Excel formulas"
→ {"intent": "information_query", "confidence": 0.90, "reasoning": "Asking for explanation, not action"}

### CRITICAL DISTINCTIONS:
- "take a screenshot" = screen_capture (NOT application_launch!)
- "what time is it" = system_query (NOT information_query - needs system clock)
- "focus notepad" = application_control (NOT application_launch - window exists)
- "open google.com" = browser_control (NOT application_launch - it's navigation)

### INTENT COLLISION RULE (MANDATORY):
Window geometry, focus, snapping, minimizing, maximizing, closing, switching, task view, virtual desktops
→ ALWAYS window_management, NEVER application_control.

Examples that MUST be window_management:
- "snap left/right" → window_management
- "minimize all" → window_management
- "switch window" → window_management
- "maximize this" → window_management
- "move to desktop 2" → window_management
- "close this window" → window_management (NOT application_control)
"""
    
    def __init__(self):
        # Use planner model (mistral:7b) for better reasoning
        # Intent classification is too critical for phi3:mini
        self.model = get_model_manager().get_planner_model()
        logging.info("IntentAgent initialized with planner model for reliability")
    
    def classify(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Classify user intent with few-shot examples and system context.
        
        UNIFIED DECISION CONTRACT:
        Returns decision="execute" to proceed, or decision="ask" for clarification.
        
        Args:
            user_input: Raw user text
            context: Optional system state from AmbientMemory
            
        Returns:
            {
                "decision": "execute" | "ask",
                "intent": "screen_capture",
                "confidence": 0.95,
                "reasoning": "User wants to capture the screen",
                "question": "..."  # Only if decision == "ask"
            }
        """
        # Build context snapshot for LLM
        context_section = ""
        if context:
            context_str = ContextSnapshot.build(context)
            context_section = f"""## CURRENT SYSTEM STATE
{context_str}

"""
        
        prompt = f"""You are an intent classifier for a desktop assistant.

{context_section}Your job: Classify the user's intent into ONE category.

Use the system state to resolve ambiguity when possible.
Prefer acting without asking if the intent is unambiguous given the context.
If truly ambiguous and you cannot determine the user's intent, set decision to "ask".

{self.FEW_SHOT_EXAMPLES}

---

NOW CLASSIFY THIS INPUT:
User: "{user_input}"

Respond with JSON:
- decision: "execute" if you can determine the intent, "ask" if clarification needed
- intent: exactly one of the enum values
- confidence: 0.0 to 1.0
- reasoning: brief explanation (1 sentence)
- question: (only if decision is "ask") the clarification question to ask

REMEMBER:
- "screenshot" = screen_capture, NOT application_launch
- "what time" = system_query, NOT information_query  
- "focus/close window" = application_control, NOT application_launch
"""
        
        try:
            result = self.model.generate(prompt, schema=self.INTENT_SCHEMA)
            
            # Ensure expected types and defaults
            if "decision" not in result:
                result["decision"] = "execute"  # Default to execute for backward compatibility
            if "confidence" in result:
                result["confidence"] = float(result["confidence"])
            if "reasoning" not in result:
                result["reasoning"] = "No reasoning provided"
            
            decision = result.get("decision", "execute")
            logging.info(f"Intent classified: {result['intent']} ({result['confidence']:.2f}) decision={decision}")
            logging.debug(f"Reasoning: {result.get('reasoning', 'N/A')}")
            
            if decision == "ask":
                logging.info(f"Clarification requested: {result.get('question', 'No question provided')}")
            
            return result
            
        except Exception as e:
            logging.error(f"Intent classification failed: {e}")
            return {
                "decision": "execute",
                "intent": "unknown",
                "confidence": 0.0,
                "reasoning": f"Classification error: {str(e)}"
            }
