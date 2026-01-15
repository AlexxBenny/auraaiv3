# AURA Controlled Self-Evolution Plan

## Executive Summary

**What we're building:**
- Explicit limitation detection
- Skill (tool) proposal system
- Procedural memory for learned capabilities
- Validation and policy gates
- Safe evolution without code execution

**What we're NOT doing:**
- ❌ AI-generated executable code
- ❌ Automatic file mutation
- ❌ Unbounded self-learning
- ❌ `exec(generated_code)`

**This is how modern agentic systems evolve safely.**

---

## Architecture Overview

```
User Input
  ↓
Intent Agent
  ↓
Planner Agent
  ↓
┌───────────────┐
│ Tool Exists?  │──Yes──▶ Tool Executor
└──────┬────────┘
       No
       ↓
Limitation Analysis Agent
       ↓
Skill / Tool Proposal
       ↓
Validation & Policy Gate
       ↓
Procedural Memory (Store)
       ↓
[Manual Review] → Tool Registration
```

---

## Phase 3.1: Limitation Detection (Planner Upgrade)

### Goal
Make Planner explicitly aware of what it cannot do.

### Changes to `agents/planner_agent.py`

**Update PLAN_SCHEMA:**

```python
PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "goal": {"type": "string"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tool": {"type": "string"},
                    "args": {"type": "object"}
                },
                "required": ["tool", "args"]
            }
        },
        "requires_new_skill": {
            "type": "boolean",
            "default": false
        },
        "missing_capability": {
            "type": "string",
            "description": "What capability is missing"
        },
        "reason": {
            "type": "string",
            "description": "Why existing tools cannot accomplish this"
        }
    },
    "required": ["goal"]
}
```

**Update `plan()` method:**

```python
def plan(self, user_input: str, intent: str) -> Dict[str, Any]:
    # ... existing code ...
    
    # After getting plan from LLM, validate:
    if result.get("requires_new_skill", False):
        # Validate that steps are empty or minimal
        if result.get("steps"):
            logging.warning("Plan has steps but also requires_new_skill - clearing steps")
            result["steps"] = []
        
        # Ensure required fields
        if not result.get("missing_capability"):
            result["missing_capability"] = "Unknown capability"
        if not result.get("reason"):
            result["reason"] = "No suitable tool found"
    
    return result
```

**Hard Rules:**
1. Planner must never invent tools
2. Planner must only reference ToolRegistry
3. Planner must stop planning when tool is missing
4. `requires_new_skill=true` → `steps` must be empty

---

## Phase 3.2: Limitation Analysis Agent (NEW)

### File: `agents/limitation_agent.py`

```python
"""Limitation Analysis Agent - Converts limitations into skill proposals"""

import logging
from typing import Dict, Any
from models.model_manager import get_model_manager


class LimitationAnalysisAgent:
    """Analyzes limitations and proposes new skills/tools"""
    
    PROPOSAL_SCHEMA = {
        "type": "object",
        "properties": {
            "proposed_tool": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "pattern": "^[a-z][a-z0-9_]*$",
                        "description": "Tool name (snake_case, no spaces)"
                    },
                    "description": {
                        "type": "string",
                        "minLength": 10,
                        "description": "Clear description of what tool does"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["system", "file", "network", "application", "other"],
                        "default": "other"
                    },
                    "inputs": {
                        "type": "object",
                        "description": "JSON Schema for tool inputs",
                        "additionalProperties": True
                    },
                    "side_effects": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "What side effects this tool has"
                    },
                    "risk_level": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "default": "medium"
                    },
                    "os_permissions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Required OS permissions (e.g., 'admin', 'registry_write')"
                    }
                },
                "required": ["name", "description", "inputs"]
            },
            "rationale": {
                "type": "string",
                "description": "Why this tool is needed"
            },
            "alternative_approaches": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Alternative ways to accomplish the goal"
            }
        },
        "required": ["proposed_tool", "rationale"]
    }
    
    def __init__(self):
        self.model = get_model_manager().get_planner_model()  # Use reasoning model
        logging.info("LimitationAnalysisAgent initialized")
    
    def analyze(self, goal: str, missing_capability: str, reason: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze limitation and propose new skill
        
        Args:
            goal: Original user goal
            missing_capability: What capability is missing
            reason: Why existing tools can't do this
            context: Additional context
            
        Returns:
            Tool proposal with schema
        """
        available_tools = self._get_available_tools_summary()
        
        prompt = f"""You are a capability analyst. A user wants to accomplish this goal but the system lacks the required capability.

Goal: {goal}
Missing Capability: {missing_capability}
Reason: {reason}

Available Tools: {available_tools}

Your task: Propose a NEW tool that would enable this goal.

CRITICAL RULES:
1. NEVER propose executable code
2. ONLY propose tool metadata (name, description, inputs schema)
3. Tool name must be snake_case, no spaces
4. Inputs must be valid JSON Schema
5. Be specific about side effects and risks
6. Consider OS permissions required

Respond with JSON containing:
- proposed_tool: Complete tool specification
- rationale: Why this tool solves the problem
- alternative_approaches: Other ways to accomplish goal (if any)
"""
        
        try:
            result = self.model.generate(prompt, schema=self.PROPOSAL_SCHEMA)
            
            # Validate tool name format
            tool_name = result.get("proposed_tool", {}).get("name", "")
            if not tool_name or not tool_name.replace("_", "").isalnum():
                raise ValueError(f"Invalid tool name format: {tool_name}")
            
            logging.info(f"Tool proposal generated: {tool_name}")
            return result
            
        except Exception as e:
            logging.error(f"Limitation analysis failed: {e}")
            return {
                "proposed_tool": {
                    "name": "unknown_tool",
                    "description": f"Failed to analyze: {str(e)}",
                    "category": "other",
                    "inputs": {},
                    "side_effects": [],
                    "risk_level": "high"
                },
                "rationale": f"Analysis failed: {str(e)}",
                "alternative_approaches": []
            }
    
    def _get_available_tools_summary(self) -> str:
        """Get summary of available tools for context"""
        from tools.registry import get_registry
        registry = get_registry()
        tools = registry.list_all()
        
        if not tools:
            return "No tools available"
        
        return ", ".join([tool["name"] for tool in tools.values()])
```

---

## Phase 3.3: Tool Proposal Validation Layer

### File: `core/skill_gate.py`

```python
"""Skill Gate - Validates and controls tool proposals"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
import json


class SkillGate:
    """Validates tool proposals and enforces safety policy"""
    
    AUTONOMY_MODES = {
        "manual": "Proposal saved only, requires manual review",
        "assisted": "Proposal + scaffold generated, requires implementation",
        "sandboxed": "Auto-test in sandbox (future)",
        "autonomous": "Auto-register after validation (advanced, not recommended)"
    }
    
    def __init__(self, autonomy_mode: str = "manual", config_path: Optional[Path] = None):
        if autonomy_mode not in self.AUTONOMY_MODES:
            raise ValueError(f"Invalid autonomy mode: {autonomy_mode}")
        
        self.autonomy_mode = autonomy_mode
        
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "settings.yaml"
        self.config_path = config_path
        
        # Load safety policy
        self.safety_policy = self._load_safety_policy()
        
        logging.info(f"SkillGate initialized with mode: {autonomy_mode}")
    
    def _load_safety_policy(self) -> Dict[str, Any]:
        """Load safety policy from config"""
        # Default policy
        return {
            "forbidden_categories": ["system_destruction", "network_exploit"],
            "max_risk_level": "medium" if self.autonomy_mode == "manual" else "high",
            "require_os_permissions": True,
            "require_description_min_length": 10
        }
    
    def validate_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a tool proposal
        
        Returns:
            {
                "valid": bool,
                "errors": [str],
                "warnings": [str],
                "action": "approve" | "reject" | "manual_review"
            }
        """
        errors = []
        warnings = []
        
        proposed_tool = proposal.get("proposed_tool", {})
        
        # Check required fields
        if not proposed_tool.get("name"):
            errors.append("Tool name is required")
        
        if not proposed_tool.get("description"):
            errors.append("Tool description is required")
        elif len(proposed_tool.get("description", "")) < self.safety_policy.get("require_description_min_length", 10):
            errors.append(f"Description too short (min {self.safety_policy['require_description_min_length']} chars)")
        
        # Validate tool name format
        tool_name = proposed_tool.get("name", "")
        if tool_name and not self._validate_tool_name(tool_name):
            errors.append(f"Invalid tool name format: {tool_name} (must be snake_case)")
        
        # Check for name conflicts
        if self._tool_name_exists(tool_name):
            errors.append(f"Tool name '{tool_name}' already exists")
        
        # Validate inputs schema
        inputs = proposed_tool.get("inputs", {})
        if not isinstance(inputs, dict):
            errors.append("Inputs must be a valid JSON Schema object")
        elif not inputs.get("type") == "object":
            warnings.append("Inputs schema should have type='object'")
        
        # Check risk level
        risk_level = proposed_tool.get("risk_level", "medium")
        max_risk = self.safety_policy.get("max_risk_level", "medium")
        if self._risk_level_higher(risk_level, max_risk):
            warnings.append(f"Risk level '{risk_level}' exceeds policy max '{max_risk}'")
        
        # Check category
        category = proposed_tool.get("category", "other")
        forbidden = self.safety_policy.get("forbidden_categories", [])
        if category in forbidden:
            errors.append(f"Category '{category}' is forbidden")
        
        # Determine action
        if errors:
            action = "reject"
        elif warnings and self.autonomy_mode == "manual":
            action = "manual_review"
        elif self.autonomy_mode == "autonomous" and risk_level == "low":
            action = "approve"
        else:
            action = "manual_review"
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "action": action
        }
    
    def _validate_tool_name(self, name: str) -> bool:
        """Validate tool name format (snake_case)"""
        if not name:
            return False
        if not name[0].isalpha():
            return False
        if not all(c.isalnum() or c == "_" for c in name):
            return False
        return True
    
    def _tool_name_exists(self, name: str) -> bool:
        """Check if tool name already exists"""
        from tools.registry import get_registry
        registry = get_registry()
        return registry.has(name)
    
    def _risk_level_higher(self, level: str, max_level: str) -> bool:
        """Check if risk level exceeds maximum"""
        levels = {"low": 1, "medium": 2, "high": 3}
        return levels.get(level, 2) > levels.get(max_level, 2)
    
    def get_autonomy_mode(self) -> str:
        """Get current autonomy mode"""
        return self.autonomy_mode
    
    def set_autonomy_mode(self, mode: str):
        """Change autonomy mode (with validation)"""
        if mode not in self.AUTONOMY_MODES:
            raise ValueError(f"Invalid autonomy mode: {mode}")
        self.autonomy_mode = mode
        logging.info(f"Autonomy mode changed to: {mode}")
```

---

## Phase 3.4: Procedural Memory (Skill Memory)

### File: `memory/procedural.py`

```python
"""Procedural Memory - Stores tool proposals and learned skills"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class ProceduralMemory:
    """Stores tool proposals, approved tools, and skill metadata"""
    
    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            storage_path = Path.home() / ".aura" / "procedural_memory.json"
        
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing memory
        self.memory = self._load_memory()
        
        logging.info(f"ProceduralMemory initialized: {len(self.memory.get('tools', []))} tools stored")
    
    def _load_memory(self) -> Dict[str, Any]:
        """Load procedural memory from disk"""
        if not self.storage_path.exists():
            return {
                "tools": [],
                "proposals": [],
                "rejected": [],
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "version": "1.0"
                }
            }
        
        try:
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading procedural memory: {e}")
            return {
                "tools": [],
                "proposals": [],
                "rejected": [],
                "metadata": {}
            }
    
    def _save_memory(self):
        """Save procedural memory to disk"""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.memory, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving procedural memory: {e}")
    
    def store_proposal(self, proposal: Dict[str, Any], goal: str, validation_result: Dict[str, Any]) -> str:
        """Store a tool proposal
        
        Args:
            proposal: Tool proposal from LimitationAnalysisAgent
            goal: Original user goal
            validation_result: Validation result from SkillGate
            
        Returns:
            Proposal ID
        """
        proposal_id = f"proposal_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        record = {
            "id": proposal_id,
            "status": "proposed",
            "proposed_tool": proposal.get("proposed_tool", {}),
            "rationale": proposal.get("rationale", ""),
            "alternative_approaches": proposal.get("alternative_approaches", []),
            "created_from_goal": goal,
            "created_at": datetime.now().isoformat(),
            "validation": validation_result,
            "approved": False,
            "implemented": False
        }
        
        self.memory["proposals"].append(record)
        self._save_memory()
        
        logging.info(f"Proposal stored: {proposal_id} - {proposal.get('proposed_tool', {}).get('name', 'unknown')}")
        return proposal_id
    
    def approve_proposal(self, proposal_id: str, implementation_path: Optional[str] = None):
        """Mark a proposal as approved and implemented"""
        for proposal in self.memory["proposals"]:
            if proposal["id"] == proposal_id:
                proposal["approved"] = True
                proposal["implemented"] = True
                proposal["implementation_path"] = implementation_path
                proposal["approved_at"] = datetime.now().isoformat()
                
                # Move to tools list
                tool_record = {
                    "name": proposal["proposed_tool"]["name"],
                    "description": proposal["proposed_tool"]["description"],
                    "category": proposal["proposed_tool"].get("category", "other"),
                    "created_from_proposal": proposal_id,
                    "registered_at": datetime.now().isoformat()
                }
                self.memory["tools"].append(tool_record)
                
                self._save_memory()
                logging.info(f"Proposal approved: {proposal_id}")
                return
        
        raise ValueError(f"Proposal not found: {proposal_id}")
    
    def reject_proposal(self, proposal_id: str, reason: str):
        """Mark a proposal as rejected"""
        for proposal in self.memory["proposals"]:
            if proposal["id"] == proposal_id:
                proposal["status"] = "rejected"
                proposal["rejection_reason"] = reason
                proposal["rejected_at"] = datetime.now().isoformat()
                
                # Move to rejected list
                self.memory["rejected"].append(proposal)
                self.memory["proposals"].remove(proposal)
                
                self._save_memory()
                logging.info(f"Proposal rejected: {proposal_id} - {reason}")
                return
        
        raise ValueError(f"Proposal not found: {proposal_id}")
    
    def get_pending_proposals(self) -> List[Dict[str, Any]]:
        """Get all pending proposals"""
        return [
            p for p in self.memory["proposals"]
            if p["status"] == "proposed" and not p["approved"]
        ]
    
    def get_approved_tools(self) -> List[Dict[str, Any]]:
        """Get all approved/implemented tools"""
        return self.memory.get("tools", [])
    
    def find_similar_proposal(self, goal: str) -> Optional[Dict[str, Any]]:
        """Find similar proposals for a goal"""
        # Simple similarity check (can be enhanced)
        goal_lower = goal.lower()
        for proposal in self.memory["proposals"]:
            proposal_goal = proposal.get("created_from_goal", "").lower()
            if goal_lower in proposal_goal or proposal_goal in goal_lower:
                return proposal
        return None
```

---

## Phase 3.5: Tool Scaffolding Generator (Optional)

### File: `core/tool_scaffold.py`

```python
"""Tool Scaffold Generator - Creates template files for new tools"""

import logging
from pathlib import Path
from typing import Dict, Any


class ToolScaffoldGenerator:
    """Generates tool template files (NOT executable code)"""
    
    def __init__(self, tools_dir: Path = None):
        if tools_dir is None:
            tools_dir = Path(__file__).parent.parent / "tools" / "system"
        self.tools_dir = tools_dir
        self.tools_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_scaffold(self, proposal: Dict[str, Any]) -> Path:
        """Generate a tool scaffold file
        
        Args:
            proposal: Tool proposal from LimitationAnalysisAgent
            
        Returns:
            Path to generated scaffold file
        """
        proposed_tool = proposal.get("proposed_tool", {})
        tool_name = proposed_tool.get("name", "unknown_tool")
        description = proposed_tool.get("description", "")
        category = proposed_tool.get("category", "other")
        inputs_schema = proposed_tool.get("inputs", {})
        
        # Generate Python template
        template = f'''"""Tool: {tool_name}

{description}

Category: {category}
Risk Level: {proposed_tool.get("risk_level", "medium")}
Side Effects: {", ".join(proposed_tool.get("side_effects", []))}
OS Permissions: {", ".join(proposed_tool.get("os_permissions", []))}
"""

from typing import Dict, Any
from ..base import Tool


class {self._to_class_name(tool_name)}(Tool):
    """{description}"""
    
    @property
    def name(self) -> str:
        return "{tool_name}"
    
    @property
    def description(self) -> str:
        return "{description}"
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {self._format_schema(inputs_schema)}
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool
        
        TODO: Implement this method
        - Validate args match schema
        - Perform the actual operation
        - Return structured result with 'status' key
        
        Returns:
            {{"status": "success" | "error", ...}}
        """
        if not self.validate_args(args):
            return {{
                "status": "error",
                "error": "Invalid arguments"
            }}
        
        # TODO: Implement tool logic here
        # This is deterministic Python only - NO AI
        
        raise NotImplementedError("Tool not implemented yet")
        
        # Example return:
        # return {{
        #     "status": "success",
        #     "result": "..."
        # }}
'''
        
        # Write scaffold file
        scaffold_path = self.tools_dir / f"{tool_name}.py"
        with open(scaffold_path, 'w') as f:
            f.write(template)
        
        logging.info(f"Tool scaffold generated: {scaffold_path}")
        return scaffold_path
    
    def _to_class_name(self, tool_name: str) -> str:
        """Convert snake_case to PascalCase"""
        return ''.join(word.capitalize() for word in tool_name.split('_'))
    
    def _format_schema(self, schema: Dict[str, Any]) -> str:
        """Format JSON schema as Python dict string"""
        import json
        return json.dumps(schema, indent=8)
```

---

## Phase 3.6: Integration into Agent Loop

### Update `core/agent_loop.py`

Add limitation handling:

```python
# Add imports
from agents.limitation_agent import LimitationAnalysisAgent
from core.skill_gate import SkillGate
from memory.procedural import ProceduralMemory
from core.tool_scaffold import ToolScaffoldGenerator

class AgentLoop:
    def __init__(self):
        # ... existing initialization ...
        
        # Add new components
        self.limitation_agent = LimitationAnalysisAgent()
        self.skill_gate = SkillGate(autonomy_mode="manual")
        self.procedural_memory = ProceduralMemory()
        self.scaffold_generator = ToolScaffoldGenerator()
    
    def process(self, user_input: str) -> Dict[str, Any]:
        # ... existing intent and planning ...
        
        plan = self.planner_agent.plan(user_input, intent)
        
        # NEW: Handle missing skills
        if plan.get("requires_new_skill", False):
            return self._handle_missing_skill(user_input, plan)
        
        # ... rest of existing flow ...
    
    def _handle_missing_skill(self, user_input: str, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Handle missing skill scenario"""
        goal = plan.get("goal", user_input)
        missing_capability = plan.get("missing_capability", "Unknown")
        reason = plan.get("reason", "No suitable tool")
        
        # Step 1: Analyze limitation
        proposal = self.limitation_agent.analyze(
            goal, missing_capability, reason
        )
        
        # Step 2: Validate proposal
        validation = self.skill_gate.validate_proposal(proposal)
        
        # Step 3: Store in procedural memory
        proposal_id = self.procedural_memory.store_proposal(
            proposal, goal, validation
        )
        
        # Step 4: Generate scaffold (if assisted mode)
        scaffold_path = None
        if self.skill_gate.get_autonomy_mode() in ["assisted", "sandboxed"]:
            scaffold_path = self.scaffold_generator.generate_scaffold(proposal)
        
        return {
            "intent": {"intent": "unknown", "confidence": 0.0},
            "plan": plan,
            "execution": None,
            "evaluation": None,
            "final_status": "requires_new_skill",
            "proposal": proposal,
            "validation": validation,
            "proposal_id": proposal_id,
            "scaffold_path": str(scaffold_path) if scaffold_path else None,
            "message": self._format_skill_message(validation, proposal)
        }
    
    def _format_skill_message(self, validation: Dict[str, Any], proposal: Dict[str, Any]) -> str:
        """Format message for user about skill proposal"""
        tool_name = proposal.get("proposed_tool", {}).get("name", "unknown")
        
        if not validation["valid"]:
            return f"Skill proposal rejected: {', '.join(validation['errors'])}"
        
        if validation["action"] == "manual_review":
            return f"New skill '{tool_name}' proposed. Requires manual review."
        
        return f"New skill '{tool_name}' proposed and validated."
```

---

## Phase 3.7: Feedback Loop (Critic Enhancement)

### Update `agents/critic_agent.py`

Add tool effectiveness evaluation:

```python
# Add to CRITIC_SCHEMA
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

# Add method
def evaluate_tool_effectiveness(self, tool_name: str, result: Dict[str, Any], goal: str) -> Dict[str, Any]:
    """Evaluate how well a tool performed"""
    # ... implementation ...
```

---

## Phase 4: Safety & Production Controls

### Mandatory Safeguards

1. **No AI writes executable code** - Enforced in all agents
2. **No automatic file writes** - Only in `tools/` directory, only scaffolds
3. **Full logging** - All proposals logged
4. **Validation required** - All proposals must pass SkillGate

### Configuration: `config/settings.yaml`

```yaml
evolution:
  autonomy_mode: manual  # manual | assisted | sandboxed | autonomous
  max_risk_level: medium
  forbidden_categories:
    - system_destruction
    - network_exploit
  require_manual_approval: true
  auto_generate_scaffolds: false

logging:
  log_proposals: true
  log_validations: true
  log_registrations: true
```

---

## Implementation Checklist

### Phase 3.1: Planner Upgrade
- [ ] Update `PLAN_SCHEMA` with `requires_new_skill` fields
- [ ] Update `plan()` method to detect limitations
- [ ] Add validation logic

### Phase 3.2: Limitation Analysis Agent
- [ ] Create `agents/limitation_agent.py`
- [ ] Implement `PROPOSAL_SCHEMA`
- [ ] Implement `analyze()` method

### Phase 3.3: Skill Gate
- [ ] Create `core/skill_gate.py`
- [ ] Implement validation logic
- [ ] Add autonomy mode support

### Phase 3.4: Procedural Memory
- [ ] Create `memory/procedural.py`
- [ ] Implement storage/retrieval
- [ ] Add proposal management

### Phase 3.5: Tool Scaffold Generator
- [ ] Create `core/tool_scaffold.py`
- [ ] Implement template generation
- [ ] Test scaffold output

### Phase 3.6: Integration
- [ ] Update `core/agent_loop.py`
- [ ] Wire limitation handling
- [ ] Test end-to-end flow

### Phase 3.7: Feedback Loop
- [ ] Enhance `CriticAgent`
- [ ] Add tool effectiveness evaluation
- [ ] Connect to procedural memory

### Phase 4: Safety
- [ ] Create `config/settings.yaml`
- [ ] Add comprehensive logging
- [ ] Document safety policies

---

## Testing Plan

1. **Test limitation detection:**
   - Command: "Schedule a daily task"
   - Expected: Planner detects missing skill

2. **Test proposal generation:**
   - Expected: LimitationAgent creates proposal

3. **Test validation:**
   - Expected: SkillGate validates proposal

4. **Test storage:**
   - Expected: ProceduralMemory stores proposal

5. **Test scaffold generation:**
   - Expected: Template file created

---

## Success Criteria

✅ System detects when it cannot accomplish a goal
✅ System proposes structured tool specifications
✅ Proposals are validated before storage
✅ Proposals are stored in procedural memory
✅ Scaffolds can be generated (optional)
✅ No executable code generated by AI
✅ All actions logged and auditable

---

*This plan maintains safety while enabling controlled evolution.*

