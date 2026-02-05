"""Query Classifier - Semantic routing for single vs multi-goal queries

RESPONSIBILITY: Route user input to correct pipeline.

Question answered:
"Does this request contain ONE semantic goal or MULTIPLE goals?"

Classification Rules:
1. SINGLE: One atomic goal (even if multiple verbs in same context)
2. MULTI: Multiple independent goals OR dependent sequential goals

CRITICAL DETECTION:
- "open youtube and search nvidia" = SINGLE (search IS the goal, youtube is context)
- "open chrome and open spotify" = MULTI (two independent launches)
- "create folder X and put file inside it" = MULTI (dependent sequence)

Dependent = multi. Always.
"""

import logging
import re
from typing import Dict, Any, Literal
from models.model_manager import get_model_manager


# Syntactic heuristics for dependency detection
DEPENDENCY_PATTERNS = [
    # Pronoun references to prior entity
    r'\b(inside|into|in)\s+(it|that|the)\b',
    r'\b(to|from)\s+(it|that|the)\b',
    r'\b(with|using)\s+(it|that)\b',
    # Explicit sequence markers
    r'\bthen\b',
    r'\bafter\s+that\b',
    r'\bonce\s+(it|that|done)\b',
    # Object creation + usage
    r'\bcreate\b.*\b(and|then)\b.*\b(inside|in|into)\b',
    r'\bmake\b.*\b(and|then)\b.*\b(inside|in|into)\b',
]

# Indicators of independent multi-goal
INDEPENDENT_MULTI_PATTERNS = [
    # Two distinct app names with "and"
    r'\bopen\s+\w+\s+and\s+open\s+\w+\b',
    # Multiple system controls
    r'\b(mute|unmute|increase|decrease|set)\b.*\band\b.*\b(mute|unmute|increase|decrease|set|take|capture)\b',
]


class QueryClassifier:
    """Lightweight semantic classifier for query routing.
    
    INVARIANTS:
    - Outputs ONLY single or multi
    - NEVER extracts actions (that's GoalInterpreter's job)
    - NEVER creates execution structure (that's GoalPlanner's job)
    - Dependent sequences → MULTI (not single!)
    
    This is a ROUTER, not a planner.
    """
    
    CLASSIFIER_SCHEMA = {
        "type": "object",
        "properties": {
            "classification": {
                "type": "string",
                "enum": ["single", "multi"]
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation (1 sentence)"
            }
        },
        "required": ["classification", "reasoning"]
    }
    
    # Semantic few-shot examples - CRITICAL: dependent = multi
    FEW_SHOT_EXAMPLES = """
## SEMANTIC GOAL CLASSIFICATION

### SINGLE GOAL (one atomic objective)

User: "open youtube and search nvidia"
→ {"classification": "single", "reasoning": "One goal: search nvidia on youtube"}

User: "open spotify and play my playlist"  
→ {"classification": "single", "reasoning": "One goal: play music in spotify"}

User: "launch chrome and go to google.com"
→ {"classification": "single", "reasoning": "One goal: navigate to google in browser"}

User: "take a screenshot"
→ {"classification": "single", "reasoning": "One goal: capture screen"}

User: "what time is it"
→ {"classification": "single", "reasoning": "One goal: get current time"}

User: "open chrome and search for AI news"
→ {"classification": "single", "reasoning": "One goal: search AI news in browser"}

User: "mute the volume"
→ {"classification": "single", "reasoning": "One goal: mute audio"}

### MULTI GOAL - INDEPENDENT (unrelated objectives)

User: "open chrome and open spotify"
→ {"classification": "multi", "reasoning": "Two independent goals: open browser, open music app"}

User: "increase volume and take a screenshot"
→ {"classification": "multi", "reasoning": "Two independent goals: adjust audio, capture screen"}

User: "open calculator, open notepad, and open chrome"
→ {"classification": "multi", "reasoning": "Three independent app launches"}

User: "set brightness to 50 and mute the audio"
→ {"classification": "multi", "reasoning": "Two independent system settings"}

### MULTI GOAL - DEPENDENT (sequential, B needs A)

User: "create a folder called projects and put a readme inside it"
→ {"classification": "multi", "reasoning": "Dependent: file creation depends on folder existing"}

User: "create folder nvidia and create an empty text file inside it"
→ {"classification": "multi", "reasoning": "Dependent: file creation requires folder to exist first"}

User: "make a new folder called test then add a document to it"
→ {"classification": "multi", "reasoning": "Dependent: 'to it' references the folder"}

User: "open notepad then type hello world"
→ {"classification": "multi", "reasoning": "Dependent: typing requires notepad to be open and focused"}

User: "create a spreadsheet and add data to it"
→ {"classification": "multi", "reasoning": "Dependent: adding data requires spreadsheet to exist"}

### CRITICAL RULES:

- "open X and do Y in X" where Y is the GOAL = SINGLE (X is just context)
- "open X and open Y" = MULTI (independent apps)
- "create X and put Y inside X" = MULTI (dependent sequence!)
- "do X then do Y" where Y references X = MULTI (dependent)
- Any pronoun reference to prior entity = MULTI (dependent)

KEY: If action B references output/state of action A → MULTI
"""
    
    def __init__(self):
        # Role-based model access (config-driven)
        self.model = get_model_manager().get("classifier")
        logging.info("QueryClassifier initialized (semantic goal routing)")
    
    def classify(self, user_input: str) -> Literal["single", "multi"]:
        """Classify query structure semantically.
        
        Args:
            user_input: Raw user command
            
        Returns:
            "single" - One atomic goal
            "multi" - Multiple goals (independent OR dependent)
        """
        # STEP 1: Syntactic heuristics (fast, deterministic)
        if self._has_dependency_pattern(user_input):
            logging.info(f"QueryClassifier: '{user_input[:40]}...' → multi (syntactic dependency)")
            return "multi"
        
        if self._has_independent_multi_pattern(user_input):
            logging.info(f"QueryClassifier: '{user_input[:40]}...' → multi (independent pattern)")
            return "multi"
        
        # STEP 2: LLM semantic classification (for ambiguous cases)
        prompt = f"""You are a semantic goal classifier.

Your job: Determine if this request contains ONE atomic goal or MULTIPLE goals.

{self.FEW_SHOT_EXAMPLES}

---

CLASSIFY THIS INPUT:
User: "{user_input}"

CRITICAL RULES:
1. Count SEMANTIC GOALS, not verbs
2. "open X and do Y in X" where Y is the purpose = SINGLE
3. "open X and open Y" = MULTI (independent apps)
4. "create X and put Y inside X" = MULTI (dependent sequence!)
5. Any pronoun reference to prior entity ("it", "that", "inside it") = MULTI
6. If unsure and request has multiple steps → classify as MULTI

Return JSON with:
- classification: "single" or "multi"  
- reasoning: brief explanation (1 sentence)
"""
        
        try:
            result = self.model.generate(prompt, schema=self.CLASSIFIER_SCHEMA)
            
            classification = result.get("classification", "single")
            reasoning = result.get("reasoning", "No reasoning provided")
            
            logging.info(
                f"QueryClassifier: '{user_input[:50]}...' → {classification} "
                f"({reasoning})"
            )
            
            return classification
            
        except Exception as e:
            logging.warning(f"QueryClassifier failed: {e}, defaulting to single")
            return "single"
    
    def _has_dependency_pattern(self, text: str) -> bool:
        """Check for syntactic dependency patterns."""
        text_lower = text.lower()
        for pattern in DEPENDENCY_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False
    
    def _has_independent_multi_pattern(self, text: str) -> bool:
        """Check for independent multi-goal patterns."""
        text_lower = text.lower()
        for pattern in INDEPENDENT_MULTI_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False
    
    def classify_with_confidence(self, user_input: str) -> Dict[str, Any]:
        """Classify with confidence for QC-LLM authority contract.
        
        AUTHORITY CONTRACT:
        - Syntactic patterns → high confidence (0.90-0.95)
        - LLM fallback → lower confidence (0.75)
        
        When confidence ≥ 0.85, GoalInterpreter MUST respect topology.
        
        Returns:
            {
                "classification": "single" | "multi",
                "confidence": 0.0-1.0,
                "reasoning": "...",
                "detection_method": "syntactic" | "llm"
            }
        """
        # Check syntactic patterns first (high confidence)
        if self._has_dependency_pattern(user_input):
            logging.info(f"QC: '{user_input[:40]}...' → multi (syntactic, conf=0.95)")
            return {
                "classification": "multi",
                "confidence": 0.95,
                "reasoning": "Syntactic dependency pattern detected",
                "detection_method": "syntactic"
            }
        
        if self._has_independent_multi_pattern(user_input):
            logging.info(f"QC: '{user_input[:40]}...' → multi (syntactic, conf=0.90)")
            return {
                "classification": "multi",
                "confidence": 0.90,
                "reasoning": "Independent multi-goal pattern detected",
                "detection_method": "syntactic"
            }
        
        # LLM fallback (lower confidence)
        classification = self.classify(user_input)
        logging.info(f"QC: '{user_input[:40]}...' → {classification} (llm, conf=0.75)")
        return {
            "classification": classification,
            "confidence": 0.75,
            "reasoning": "LLM semantic classification",
            "detection_method": "llm"
        }
    
    # Backward compat
    def classify_with_reasoning(self, user_input: str) -> Dict[str, Any]:
        """Deprecated: Use classify_with_confidence instead."""
        return self.classify_with_confidence(user_input)


# Backward compatibility alias
DecompositionGate = QueryClassifier
