"""Model Manager - SINGLE SOURCE OF TRUTH for all model routing

This is the ONLY place that decides which model to use for what.
All agents must go through this manager.

Runtime-based configuration:
- Loads runtime mode from core.runtime
- Loads appropriate config from config/models/{mode}.yaml
- Validates required roles: intent, planner, critic
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from .providers.base import BaseLLMProvider
from .providers.gemini import GeminiProvider
from .providers.openrouter import OpenRouterProvider
from .providers.ollama import OllamaProvider
from .providers.hybrid import HybridProvider


class ModelManager:
    """Centralized model management and routing"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize ModelManager with runtime-based configuration"""
        # Get runtime mode
        from core.runtime import get_runtime_mode
        self.runtime_mode = get_runtime_mode()
        
        # Determine config path based on runtime mode
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "models" / f"{self.runtime_mode}.yaml"
        
        self.config_path = config_path
        self.config = self._load_config()
        self._validate_config()
        self._providers: Dict[str, BaseLLMProvider] = {}
        
        logging.info(f"ModelManager initialized - Runtime: {self.runtime_mode}, Config: {config_path}")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load model configuration from runtime-specific YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Model config not found: {self.config_path}\n"
                f"Runtime mode '{self.runtime_mode}' requires config/models/{self.runtime_mode}.yaml"
            )
        
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
            
            # Check if config is empty (stub)
            if not config or config == {}:
                if self.runtime_mode in ["hosted", "hybrid"]:
                    raise NotImplementedError(
                        f"Runtime mode '{self.runtime_mode}' is not yet implemented. "
                        f"Please use 'local' mode or implement config/models/{self.runtime_mode}.yaml"
                    )
                else:
                    raise ValueError(f"Empty configuration file: {self.config_path}")
            
            return config
        except (FileNotFoundError, NotImplementedError, ValueError):
            raise
        except Exception as e:
            raise RuntimeError(f"Error loading config from {self.config_path}: {e}")
    
    def _validate_config(self):
        """Validate that required roles are present in config"""
        # All roles that agents depend on (config is single source of truth)
        required_roles = [
            "intent",           # IntentAgent
            "classifier",       # QueryClassifier
            "goal_interpreter", # GoalInterpreter
            "coordinator",      # ExecutionCoordinator
            "planner",          # PlannerAgent
            "tool_resolver",    # ToolResolver
            "response",         # Orchestrator
            "critic",           # Validation (future)
            "tda",              # TaskDecompositionAgent
        ]
        missing_roles = []
        
        for role in required_roles:
            if role not in self.config:
                missing_roles.append(role)
        
        if missing_roles:
            raise ValueError(
                f"Missing required roles in {self.config_path}: {', '.join(missing_roles)}\n"
                f"Required roles: {', '.join(required_roles)}"
            )
        
        # Validate hybrid config structure
        if self.runtime_mode == "hybrid":
            self._validate_hybrid_config()
        else:
            # Ensure no hybrid configs in non-hybrid modes
            for role, role_config in self.config.items():
                if isinstance(role_config, dict) and "primary" in role_config:
                    raise ValueError(
                        f"Hybrid config (primary/fallback) found in '{self.runtime_mode}' mode for role '{role}'.\n"
                        f"HybridProvider may only exist in runtime.mode == 'hybrid'."
                    )
    
    def _validate_hybrid_config(self):
        """Validate hybrid mode configuration structure.
        
        INVARIANT: Every role with primary/fallback must have complete configs.
        """
        for role, role_config in self.config.items():
            if not isinstance(role_config, dict):
                continue
            
            if "primary" in role_config:
                # Validate primary
                primary = role_config.get("primary", {})
                if not primary.get("provider"):
                    raise ValueError(f"Hybrid role '{role}' missing primary.provider")
                if not primary.get("model"):
                    raise ValueError(f"Hybrid role '{role}' missing primary.model")
                
                # Validate fallback if present
                if "fallback" in role_config:
                    fallback = role_config.get("fallback", {})
                    if not fallback.get("provider"):
                        raise ValueError(f"Hybrid role '{role}' has fallback but missing fallback.provider")
                    if not fallback.get("model"):
                        raise ValueError(f"Hybrid role '{role}' has fallback but missing fallback.model")
    
    def _get_provider(self, provider_name: str, config: Dict[str, Any]) -> BaseLLMProvider:
        """Get or create a provider instance"""
        cache_key = f"{provider_name}:{config.get('model', 'default')}"
        
        if cache_key in self._providers:
            return self._providers[cache_key]
        
        # Get API key from environment
        api_key = os.getenv(f"{provider_name.upper()}_API_KEY") or os.getenv("GEMINI_API_KEY")
        
        # Create provider based on type
        if provider_name == "gemini":
            provider = GeminiProvider(api_key=api_key, model=config.get("model", "gemini-2.5-flash"))
        elif provider_name == "openrouter":
            provider = OpenRouterProvider(api_key=api_key, model=config.get("model"))
        elif provider_name == "ollama":
            provider = OllamaProvider(
                api_key=None,  # Ollama doesn't need API key
                model=config.get("model"),
                base_url=config.get("base_url", "http://localhost:11434")
            )
        else:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        self._providers[cache_key] = provider
        return provider
    
    def _get_provider_for_role(self, role: str, role_config: Dict[str, Any]) -> BaseLLMProvider:
        """Get provider for a role, handling hybrid mode.
        
        For hybrid mode with primary/fallback, returns HybridProvider wrapper.
        For local/hosted mode, returns direct provider.
        """
        # Check for hybrid config structure
        if "primary" in role_config and self.runtime_mode == "hybrid":
            primary_config = role_config["primary"]
            fallback_config = role_config.get("fallback")
            
            primary_provider = self._get_provider(
                primary_config.get("provider"),
                primary_config
            )
            
            if fallback_config:
                fallback_provider = self._get_provider(
                    fallback_config.get("provider"),
                    fallback_config
                )
                return HybridProvider(
                    primary=primary_provider,
                    fallback=fallback_provider,
                    role=role
                )
            else:
                # No fallback configured, just use primary
                return primary_provider
        
        # Standard config (local or hosted mode)
        provider_name = role_config.get("provider", "ollama")
        return self._get_provider(provider_name, role_config)
    
    # =========================================================================
    # CANONICAL API: Role-based model access
    # =========================================================================
    
    def get(self, role: str) -> BaseLLMProvider:
        """Get model for a specific role. THE canonical access method.
        
        INVARIANT: One role → one model instance per process.
        Instances are cached on first access.
        
        Args:
            role: Role name (must exist in YAML config)
            
        Returns:
            BaseLLMProvider instance for the role
            
        Raises:
            ValueError: If role not found in config
        """
        # Check cache first (role-based caching)
        cache_key = f"role:{role}"
        if cache_key in self._providers:
            return self._providers[cache_key]
        
        # Get config for role
        config = self.config.get(role)
        if not config:
            available_roles = [k for k in self.config.keys() if isinstance(self.config[k], dict)]
            raise ValueError(
                f"No configuration for role '{role}' in {self.config_path}. "
                f"Available roles: {available_roles}"
            )
        
        # Create and cache instance
        provider = self._get_provider_for_role(role, config)
        self._providers[cache_key] = provider
        logging.info(f"ModelManager: created instance for role '{role}'")
        return provider
    
    # =========================================================================
    # DEPRECATED METHODS - Use get(role) instead
    # =========================================================================
    
    def get_intent_model(self) -> BaseLLMProvider:
        """DEPRECATED: Use get('intent') instead."""
        import warnings
        warnings.warn(
            "get_intent_model() is deprecated. Use get('intent') instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.get("intent")
    
    def get_planner_model(self) -> BaseLLMProvider:
        """DEPRECATED: Use get('planner') instead."""
        import warnings
        warnings.warn(
            "get_planner_model() is deprecated. Use get('planner') instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.get("planner")
    
    def get_critic_model(self) -> BaseLLMProvider:
        """DEPRECATED: Use get('critic') instead."""
        import warnings
        warnings.warn(
            "get_critic_model() is deprecated. Use get('critic') instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.get("critic")
    
    def get_custom_model(self, role: str) -> BaseLLMProvider:
        """DEPRECATED: Use get(role) instead."""
        import warnings
        warnings.warn(
            f"get_custom_model('{role}') is deprecated. Use get('{role}') instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.get(role)
    



# Global instance
_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Get global ModelManager instance"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager

