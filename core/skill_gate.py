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

