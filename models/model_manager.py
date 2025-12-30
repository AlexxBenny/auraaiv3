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
        required_roles = ["intent", "planner", "critic"]
        missing_roles = []
        
        for role in required_roles:
            if role not in self.config:
                missing_roles.append(role)
        
        if missing_roles:
            raise ValueError(
                f"Missing required roles in {self.config_path}: {', '.join(missing_roles)}\n"
                f"Required roles: {', '.join(required_roles)}"
            )
    
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
    
    def get_intent_model(self) -> BaseLLMProvider:
        """Get model for intent classification (cheap, fast)"""
        config = self.config.get("intent", {})
        provider_name = config.get("provider", "ollama")
        return self._get_provider(provider_name, config)
    
    def get_planner_model(self) -> BaseLLMProvider:
        """Get model for planning (reasoning, task decomposition)"""
        config = self.config.get("planner", {})
        provider_name = config.get("provider", "openrouter")
        return self._get_provider(provider_name, config)
    
    def get_critic_model(self) -> BaseLLMProvider:
        """Get model for criticism/evaluation (post-execution analysis)"""
        config = self.config.get("critic", {})
        provider_name = config.get("provider", "ollama")
        return self._get_provider(provider_name, config)
    
    def get_custom_model(self, role: str) -> BaseLLMProvider:
        """Get a custom model by role name"""
        config = self.config.get(role, {})
        if not config:
            raise ValueError(f"No configuration found for role: {role}")
        provider_name = config.get("provider")
        if not provider_name:
            raise ValueError(f"Provider not specified for role: {role}")
        return self._get_provider(provider_name, config)


# Global instance
_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Get global ModelManager instance"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager

