"""Ollama provider implementation (local models) - HTTP ONLY

Uses raw HTTP requests to /api/chat endpoint.
NO import ollama - pure HTTP client.
"""

import requests
import logging
from typing import Dict, Any, Optional
from .base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """Ollama local model provider (FREE, runs locally) - HTTP only"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "phi-3-mini", base_url: str = "http://localhost:11434", **kwargs):
        super().__init__(api_key, **kwargs)
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/api/chat"
    
    def generate(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate response using Ollama /api/chat endpoint (HTTP only)"""
        
        # Build system prompt
        system_prompt = self._build_system_prompt(prompt, schema)
        
        # Ollama /api/chat format
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Respond ONLY with valid JSON. Never generate executable code."
                },
                {
                    "role": "user",
                    "content": system_prompt
                }
            ],
            "stream": False,
            "options": {
                "temperature": 0.1 if schema else 0.3,
                "num_predict": 2000
            }
        }
        
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=120  # 120s timeout as specified
            )
            
            response.raise_for_status()
            response_data = response.json()
            
            # Extract text from response (Ollama chat format)
            if "message" in response_data:
                raw_text = response_data["message"].get("content", "").strip()
            elif "response" in response_data:
                raw_text = response_data["response"].strip()
            else:
                raise ValueError("No response in API data")
            
            if not raw_text:
                raise ValueError("Empty response from Ollama")
            
            # Parse and validate
            return self._parse_response(raw_text, schema)
            
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f"Cannot connect to Ollama at {self.base_url}. Is Ollama running?")
        except requests.exceptions.HTTPError as e:
            logging.error(f"Ollama API error: {e}")
            if hasattr(e, 'response') and e.response:
                logging.error(f"Response: {e.response.text}")
            raise RuntimeError(f"Ollama API call failed: {e}")
        except Exception as e:
            logging.error(f"Ollama provider error: {e}")
            raise
    
    def check_available(self) -> bool:
        """Check if Ollama is available and model exists (HTTP only)"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                return self.model in model_names
            return False
        except:
            return False

