"""Intent Agent - Strategy-first reasoning with context awareness

CRITICAL: This is the FIRST gate in the pipeline.
Wrong strategy = wrong execution.

STRATEGY-FIRST ARCHITECTURE:
- Receives system state context via ContextSnapshot
- Chooses the BEST STRATEGY given context (not just a category)
- Derives intent from strategy for backward-compatible routing
- Intent is a routing artifact, strategy is the decision

Uses mistral:7b for better reasoning.
"""

import logging
from typing import Dict, Any, Optional
from models.model_manager import get_model_manager
from core.context_snapshot import ContextSnapshot


# =============================================================================
# STRATEGY → INTENT MAPPING (Backward Compatibility)
# =============================================================================
# Strategies are verbs (what to do), intents are categories (where to route)
# This mapping allows downstream code to remain unchanged.

STRATEGY_TO_INTENT = {
    # Media control
    "resume_media": "system_control",
    "pause_media": "system_control",
    "control_volume": "system_control",
    "control_audio": "system_control",
    
    # Application lifecycle
    "launch_app": "application_launch",
    "focus_app": "application_control",
    "close_app": "application_control",
    
    # Window management
    "manage_window": "window_management",
    "snap_window": "window_management",
    "switch_desktop": "window_management",
    
    # System queries (read-only)
    "query_time": "system_query",
    "query_battery": "system_query",
    "query_system": "system_query",
    
    # System control (write)
    "control_display": "system_control",
    "control_power": "system_control",
    
    # Screen operations
    "capture_screen": "screen_capture",
    "find_on_screen": "screen_perception",
    
    # Input
    "send_input": "input_control",
    
    # Files
    "file_operation": "file_operation",
    
    # Browser
    "open_url": "browser_control",
    "browser_action": "browser_control",
    
    # Clipboard
    "clipboard_action": "clipboard_operation",
    
    # Memory
    "recall_memory": "memory_recall",
    
    # Office
    "office_action": "office_operation",
    
    # Meta-strategies
    "ask_user": None,  # Terminal state - need more info
    "out_of_scope": None,  # Terminal state - can't do this
    "answer_question": "information_query",
}


class IntentAgent:
    """Strategy-first reasoning agent.
    
    ARCHITECTURE:
    - Chooses STRATEGY based on user input + context
    - Derives INTENT from strategy for routing
    - Downstream code sees intent, reasoning happens here
    
    INVARIANTS:
    - Strategy is REQUIRED in output
    - Intent is DERIVED, never chosen by LLM
    - Context rules are HARD CONSTRAINTS
    """
    
    # Strategy-first schema - strategy is REQUIRED, intent is DERIVED
    INTENT_SCHEMA = {
        "type": "object",
        "properties": {
            # PRIMARY: Strategy is the decision
            "strategy": {
                "type": "string",
                "enum": list(STRATEGY_TO_INTENT.keys()),
                "description": "The best action strategy given context"
            },
            "target": {
                "type": "string",
                "description": "Target of the action (app name, file path, etc.)"
            },
            # DELIBERATION TRACE (for logging/debugging)
            "candidates": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of 2-3 candidate strategies considered"
            },
            "eliminated": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Strategies eliminated due to context (with reason)"
            },
            "reasoning": {
                "type": "string",
                "description": "WHY this strategy was chosen after elimination"
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1
            },
            # ONLY for ask_user strategy
            "question": {
                "type": "string",
                "description": "Clarification question (only if strategy is ask_user)"
            }
        },
        "required": ["strategy", "reasoning", "confidence"]
    }
    
    # Strategy-first few-shot examples with context-dependent cases
    FEW_SHOT_EXAMPLES = """
## STRATEGY EXAMPLES (learn the pattern)

### CONTEXT-DEPENDENT STRATEGIES (CRITICAL - study these carefully)

# When media is PAUSED, "play" means RESUME, not launch
User: "play music"
Context: media: paused (Spotify.exe)
→ {"strategy": "resume_media", "target": "spotify", "confidence": 0.95, "reasoning": "Media is paused, resuming playback"}

# When media is INACTIVE, "play" means LAUNCH
User: "play music"  
Context: media: inactive
→ {"strategy": "launch_app", "target": "spotify", "confidence": 0.85, "reasoning": "No active media, launching player"}

# When app is RUNNING, "open" means FOCUS, not launch
User: "open notepad"
Context: focus: notepad.exe - Untitled
→ {"strategy": "focus_app", "target": "notepad", "confidence": 0.95, "reasoning": "Notepad already running, bringing to focus"}

# When app is NOT running, "open" means LAUNCH
User: "open notepad"
Context: focus: chrome.exe - Google
→ {"strategy": "launch_app", "target": "notepad", "confidence": 0.95, "reasoning": "Notepad not running, launching it"}

### MEDIA STRATEGIES
User: "pause the music"
→ {"strategy": "pause_media", "confidence": 0.95, "reasoning": "Explicit pause request"}

User: "set volume to 50"
→ {"strategy": "control_volume", "target": "50", "confidence": 0.95, "reasoning": "Volume control action"}

User: "mute"
→ {"strategy": "control_audio", "target": "mute", "confidence": 0.95, "reasoning": "Audio mute action"}

### APPLICATION STRATEGIES
User: "launch spotify"
→ {"strategy": "launch_app", "target": "spotify", "confidence": 0.95, "reasoning": "Explicit launch request"}

User: "close this window"
→ {"strategy": "close_app", "confidence": 0.90, "reasoning": "Close current window"}

User: "focus on chrome"
→ {"strategy": "focus_app", "target": "chrome", "confidence": 0.95, "reasoning": "Bring existing window to front"}

### WINDOW STRATEGIES
User: "snap this window to the left"
→ {"strategy": "snap_window", "target": "left", "confidence": 0.95, "reasoning": "Window positioning"}

User: "maximize this"
→ {"strategy": "manage_window", "target": "maximize", "confidence": 0.95, "reasoning": "Window geometry change"}

User: "move to desktop 2"
→ {"strategy": "switch_desktop", "target": "2", "confidence": 0.95, "reasoning": "Virtual desktop movement"}

### SYSTEM QUERY STRATEGIES (read-only)
User: "what time is it"
→ {"strategy": "query_time", "confidence": 0.95, "reasoning": "System clock query, no action needed"}

User: "what's my battery level"
→ {"strategy": "query_battery", "confidence": 0.95, "reasoning": "System state query"}

### SYSTEM CONTROL STRATEGIES (write)
User: "set brightness to 80"
→ {"strategy": "control_display", "target": "80", "confidence": 0.95, "reasoning": "Display brightness change"}

User: "lock my computer"
→ {"strategy": "control_power", "target": "lock", "confidence": 0.95, "reasoning": "Power/security action"}

### SCREEN STRATEGIES
User: "take a screenshot"
→ {"strategy": "capture_screen", "confidence": 0.95, "reasoning": "Screen capture action"}

User: "find the submit button on screen"
→ {"strategy": "find_on_screen", "target": "submit button", "confidence": 0.90, "reasoning": "OCR/visual search"}

### FILE STRATEGIES
User: "create a file called notes.txt"
→ {"strategy": "file_operation", "target": "notes.txt", "confidence": 0.95, "reasoning": "File creation"}

### INPUT STRATEGIES
User: "type hello world"
→ {"strategy": "send_input", "target": "hello world", "confidence": 0.95, "reasoning": "Keyboard input"}

### BROWSER STRATEGIES
User: "open google.com"
→ {"strategy": "open_url", "target": "google.com", "confidence": 0.95, "reasoning": "Web navigation"}

### KNOWLEDGE STRATEGIES
User: "what is the capital of France"
→ {"strategy": "answer_question", "confidence": 0.95, "reasoning": "General knowledge, no tool needed"}

### ASK USER STRATEGY (when truly ambiguous)
User: "do the thing"
→ {"strategy": "ask_user", "question": "Could you please specify what you'd like me to do?", "confidence": 0.50, "reasoning": "Request is too ambiguous"}

---

## CRITICAL CONTEXT RULES (MANDATORY - violating these is an ERROR)

1. If context shows PAUSED MEDIA and user says "play/continue/resume":
   → strategy MUST be resume_media, NOT launch_app
   
2. If context shows APP ALREADY RUNNING and user says "open [app]":
   → strategy MUST be focus_app, NOT launch_app
   
3. If context shows MEDIA PLAYING and user says "pause/stop":
   → strategy MUST be pause_media
   
4. If request is truly ambiguous and context provides no help:
   → strategy MUST be ask_user
   
5. DO NOT choose a strategy if you're guessing. ask_user is preferable to wrong action.
"""

    def __init__(self):
        # Use planner model (mistral:7b) for better reasoning
        # Strategy selection is too critical for phi3:mini
        self.model = get_model_manager().get_planner_model()
        logging.info("IntentAgent initialized with strategy-first architecture")
    
    def classify(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Choose best strategy given user input and context.
        
        STRATEGY-FIRST CONTRACT:
        - LLM chooses a STRATEGY (what to do)
        - Intent is DERIVED from strategy (for routing)
        - strategy=ask_user means clarification needed (terminal)
        
        Args:
            user_input: Raw user text
            context: Optional system state from AmbientMemory
            
        Returns:
            {
                "strategy": "resume_media",           # REQUIRED
                "target": "spotify",                   # Optional
                "confidence": 0.95,                    # REQUIRED
                "reasoning": "Media is paused...",    # REQUIRED
                "intent": "system_control",            # DERIVED (for backward compat)
                "decision": "execute" | "ask",         # DERIVED (for backward compat)
                "question": "..."                      # Only if strategy == ask_user
            }
        """
        # Build context snapshot for LLM
        context_section = ""
        if context:
            context_str = ContextSnapshot.build(context)
            context_section = f"""## CURRENT SYSTEM STATE
{context_str}
"""
        
        # DELIBERATIVE REASONING PROMPT
        # Force multi-step internal reasoning before output
        prompt = f"""You are a strategy selector for a desktop assistant.

{context_section}

## YOUR TASK

Given the user input and system state, select the best strategy.

## REASONING PROCESS (you MUST follow these steps)

STEP 1: List 2-3 plausible strategies for this input.
STEP 2: For each strategy, check if context INVALIDATES it.
STEP 3: Choose the best remaining strategy.

## EXAMPLE REASONING

User: "play music"
Context: media: paused (Spotify.exe)

Step 1 - Candidates:
- resume_media (continue what's paused)
- launch_app (start a player)

Step 2 - Elimination:
- launch_app: INVALID - media is already active/paused
- resume_media: VALID - context shows paused media

Step 3 - Choice: resume_media

---

{self.FEW_SHOT_EXAMPLES}

---

## NOW REASON ABOUT THIS INPUT

User: "{user_input}"

Think through Steps 1-3 internally, then respond with JSON:
- candidates: list of 2-3 strategies you considered (REQUIRED for logging)
- eliminated: list of strategies eliminated with brief reason (REQUIRED for logging)
- strategy: the strategy you chose after elimination (REQUIRED)
- target: what the action applies to (if applicable)
- confidence: 0.0 to 1.0 (REQUIRED)
- reasoning: your elimination logic condensed (REQUIRED)
- question: (ONLY if strategy is ask_user) the clarification question

SPECIAL STRATEGIES:
- ask_user: Use when you need more information to decide
- out_of_scope: Use when you understand the request but CANNOT do it
  Example response: "I understand you want X, but I don't have the capability to do that yet."

CRITICAL: If a strategy is INVALIDATED by context, do NOT choose it.
"""
        
        try:
            result = self.model.generate(prompt, schema=self.INTENT_SCHEMA)
            
            # INVARIANT: Strategy must be present
            strategy = result.get("strategy")
            if not strategy:
                logging.error("LLM did not return a strategy - treating as failure")
                return {
                    "strategy": "ask_user",
                    "intent": None,
                    "decision": "ask",
                    "confidence": 0.0,
                    "reasoning": "Model failed to select a strategy",
                    "question": "I'm not sure what you'd like me to do. Could you please clarify?"
                }
            
            # DERIVE intent from strategy (backward compatibility)
            derived_intent = STRATEGY_TO_INTENT.get(strategy)
            result["intent"] = derived_intent
            
            # DERIVE decision from strategy
            if strategy in ("ask_user", "out_of_scope"):
                result["decision"] = "ask"
            else:
                result["decision"] = "execute"
            
            # Ensure confidence is float
            if "confidence" in result:
                result["confidence"] = float(result["confidence"])
            
            # ===== COMPREHENSIVE STRATEGY LOGGING =====
            # Log full deliberation trace for debugging and training data
            candidates = result.get("candidates", [])
            eliminated = result.get("eliminated", [])
            target = result.get("target", "")
            
            logging.info(
                f"STRATEGY DECISION: {strategy} → intent={derived_intent} "
                f"(conf={result.get('confidence', 0):.2f})"
            )
            logging.info(f"  Input: {user_input[:80]}...")
            logging.info(f"  Candidates: {candidates}")
            logging.info(f"  Eliminated: {eliminated}")
            logging.info(f"  Target: {target}")
            logging.info(f"  Reasoning: {result.get('reasoning', 'N/A')}")
            
            if context_section:
                # Log context summary (first 200 chars)
                logging.debug(f"  Context: {context_section[:200].replace(chr(10), ' ')}")
            
            # Handle terminal strategies
            if strategy == "ask_user":
                question = result.get("question", "Could you please clarify what you'd like me to do?")
                logging.info(f"  → Clarification needed: {question}")
                result["question"] = question
            
            elif strategy == "out_of_scope":
                # Generate mature "I can't do this" response
                result["response"] = (
                    "I understand what you want, but I don't have the capability to do that yet."
                )
                logging.info(f"  → Out of scope: {result.get('reasoning', 'No capability')}")
                result["question"] = result["response"]  # For display consistency
            
            return result
            
        except Exception as e:
            logging.error(f"Strategy selection failed: {e}")
            return {
                "strategy": "ask_user",
                "intent": None,
                "decision": "ask",
                "confidence": 0.0,
                "reasoning": f"Strategy selection error: {str(e)}",
                "question": "I encountered an error. Could you please try again?"
            }
