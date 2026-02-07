"""Semantic Resolver - Single authority for semantic token resolution

Mirrors PathResolver pattern. Resolves symbolic tokens (like "default") to concrete values.

INVARIANT: All semantic tokens resolved BEFORE planning.
NO magic strings in planner. NO conditional logic in validate_params().

This is the ONLY place where semantic tokens become concrete values.
Planners, executors, and tools must NEVER resolve semantic tokens.

Priority Order:
1. Explicit user intent (e.g., "platform": "youtube")
2. Semantic token ("platform": "default") → resolved from config
3. Planner default (applied if param missing)
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.goal_interpreter import Goal

from core.settings_config import SettingsConfig


class SemanticResolver:
    """Single authority for semantic token resolution.
    
    RESPONSIBILITY:
    - Convert semantic tokens → concrete values
    - Ensure deterministic resolution based on config
    
    DOES NOT:
    - Execute anything
    - Validate values (planner's job)
    - Apply defaults for missing params (planner's job)
    """
    
    @staticmethod
    def resolve_goal(goal: "Goal") -> "Goal":
        """Resolve semantic tokens in goal params.
        
        CRITICAL: Only acts when LLM explicitly emits "default" as a token.
        If param is missing, does NOTHING (planner will apply default).
        
        Priority:
        - Explicit value (e.g., "youtube") → preserved
        - "default" token → resolved from config
        - Missing param → planner applies default
        
        Args:
            goal: Goal with potentially unresolved semantic tokens
            
        Returns:
            New Goal with resolved tokens (or original if no tokens found)
        """
        from agents.goal_interpreter import Goal
        
        # Only resolve browser.search.platform for now
        if goal.domain == "browser" and goal.verb == "search":
            platform = goal.params.get("platform")
            
            logging.debug(
                f"SemanticResolver: Checking {goal.domain}.{goal.verb} "
                f"with platform={platform}"
            )
            
            # CRITICAL: Only act if LLM explicitly emitted "default"
            if platform == "default":
                settings = SettingsConfig.get()
                default_platform = settings.get_semantic_default(
                    "browser", "search", "platform"
                )
                
                if default_platform:
                    logging.info(
                        f"SemanticResolver: Resolved 'default' → '{default_platform}' "
                        f"for {goal.domain}.{goal.verb}"
                    )
                    
                    # Create new goal with resolved param (Goal is frozen)
                    updated_params = dict(goal.params)
                    updated_params["platform"] = default_platform
                    
                    return Goal(
                        domain=goal.domain,
                        verb=goal.verb,
                        object=goal.object,
                        params=updated_params,
                        goal_id=goal.goal_id,
                        scope=goal.scope,
                        base_anchor=goal.base_anchor,
                        resolved_path=goal.resolved_path
                    )
                else:
                    logging.warning(
                        f"SemanticResolver: 'default' token found but no config value "
                        f"for {goal.domain}.{goal.verb}.platform"
                    )
        
        # No semantic tokens found, return original goal
        return goal

