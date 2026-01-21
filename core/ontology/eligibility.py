"""Eligibility Checker - Determines if a plan is eligible for execution

This module queries Neo4j for tool constraints and determines:
- Whether the plan can execute (no blocking constraints)
- What warnings to attach (soft constraints)

Principle: Eligibility is DERIVED, not stored.
           eligible = len(blocking_constraints) == 0
           
Planner does NOT resolve constraints - it only detects them.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from .neo4j_client import (
    query_tool_constraints,
    ToolConstraints,
    ConstraintInfo,
    Neo4jConnectionError,
    get_neo4j_client
)


@dataclass
class BlockingReason:
    """A reason why a tool is blocked"""
    tool: str
    constraint: str
    constraint_type: str
    resolvable: bool
    resolution_hint: str


@dataclass
class SoftWarning:
    """A soft warning for a tool (non-blocking)"""
    tool: str
    constraint: str
    constraint_type: str
    resolution_hint: str


@dataclass
class PlanEligibilityResult:
    """
    Result of plan eligibility check.
    
    Eligibility is DERIVED: eligible = len(blocking_reasons) == 0
    """
    eligible: bool  # DERIVED - True if no blocking constraints
    blocking_reasons: List[BlockingReason] = field(default_factory=list)
    warnings: List[SoftWarning] = field(default_factory=list)
    checked: bool = True  # Whether Neo4j was consulted
    error: Optional[str] = None  # Error message if check failed
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "eligible": self.eligible,
            "blocking_reasons": [
                {
                    "tool": r.tool,
                    "constraint": r.constraint,
                    "type": r.constraint_type,
                    "resolvable": r.resolvable,
                    "resolution_hint": r.resolution_hint
                }
                for r in self.blocking_reasons
            ],
            "warnings": [
                {
                    "tool": w.tool,
                    "constraint": w.constraint,
                    "type": w.constraint_type,
                    "resolution_hint": w.resolution_hint
                }
                for w in self.warnings
            ],
            "checked": self.checked,
            "error": self.error
        }


def check_plan_eligibility(plan_steps: List[Dict[str, Any]]) -> PlanEligibilityResult:
    """
    Check if a plan is eligible for execution.
    
    Queries Neo4j for constraints on each tool in the plan.
    
    Rules:
    - ANY blocking constraint = entire plan is ineligible
    - Soft constraints are collected as warnings
    - If Neo4j unavailable = FAIL CLOSED (ineligible)
    
    Args:
        plan_steps: List of step dicts with 'tool' and 'args' keys
                   NOTE: 'args' is NOT inspected for safety
                   
    Returns:
        PlanEligibilityResult with eligibility status
    """
    blocking_reasons: List[BlockingReason] = []
    warnings: List[SoftWarning] = []
    
    for step in plan_steps:
        tool_name = step.get("tool")
        if not tool_name:
            logging.warning("Plan step missing 'tool' key, skipping")
            continue
        
        # NOTE: We do NOT inspect step["args"] for safety
        # Planner is blind to arguments
        
        try:
            constraints = query_tool_constraints(tool_name)
            
            # Check if tool exists in Neo4j
            if not constraints.found:
                # Tool not in ontology - treat as blocking for safety
                logging.warning(f"Tool '{tool_name}' not in Neo4j ontology - blocking")
                blocking_reasons.append(BlockingReason(
                    tool=tool_name,
                    constraint="tool_not_in_ontology",
                    constraint_type="existence",
                    resolvable=False,
                    resolution_hint="Tool must be registered in safety ontology"
                ))
                continue
            
            # Collect blocking constraints
            for c in constraints.blocking_constraints:
                blocking_reasons.append(BlockingReason(
                    tool=tool_name,
                    constraint=c.name,
                    constraint_type=c.constraint_type,
                    resolvable=c.resolvable,
                    resolution_hint=c.resolution_hint
                ))
            
            # Collect soft constraints as warnings
            for c in constraints.soft_constraints:
                warnings.append(SoftWarning(
                    tool=tool_name,
                    constraint=c.name,
                    constraint_type=c.constraint_type,
                    resolution_hint=c.resolution_hint
                ))
                
        except Neo4jConnectionError as e:
            # FAIL CLOSED - Neo4j unavailable means refuse
            logging.error(f"Neo4j unavailable during eligibility check: {e}")
            return PlanEligibilityResult(
                eligible=False,
                blocking_reasons=[],
                warnings=[],
                checked=False,
                error=f"Safety system unavailable: {e}"
            )
    
    # Eligibility is DERIVED
    eligible = len(blocking_reasons) == 0
    
    if not eligible:
        logging.info(
            f"Plan ineligible: {len(blocking_reasons)} blocking constraint(s)"
        )
        for reason in blocking_reasons:
            logging.info(f"  - {reason.tool}: {reason.constraint} ({reason.constraint_type})")
    else:
        logging.debug(f"Plan eligible with {len(warnings)} warning(s)")
    
    return PlanEligibilityResult(
        eligible=eligible,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
        checked=True,
        error=None
    )


def get_tool_constraints(tool_name: str) -> Optional[ToolConstraints]:
    """
    Get constraints for a single tool.
    
    Convenience wrapper around query_tool_constraints.
    
    Args:
        tool_name: Tool name to query
        
    Returns:
        ToolConstraints or None if error
    """
    try:
        return query_tool_constraints(tool_name)
    except Neo4jConnectionError as e:
        logging.error(f"Failed to get constraints for '{tool_name}': {e}")
        return None


def verify_neo4j_connection() -> bool:
    """
    Verify Neo4j is available and responding.
    
    Returns:
        True if Neo4j is healthy
    """
    client = get_neo4j_client()
    health = client.health_check()
    return health.get("connected", False)
