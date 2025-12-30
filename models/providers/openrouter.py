"""OpenRouter provider implementation"""

import requests
import logging
from typing import Dict, Any, Optional
from .base import BaseLLMProvider


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter API provider"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "mistralai/mistral-7b-instruct", **kwargs):
        super().__init__(api_key, **kwargs)
        self.model = model
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        
        if not self.api_key:
            raise ValueError("OpenRouter API key is required")
    
    def generate(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate response using OpenRouter API"""
        
        # Build system prompt
        system_prompt = self._build_system_prompt("", schema)
        user_prompt = prompt
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            "temperature": 0.1 if schema else 0.3,
            "max_tokens": 2000
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            response_data = response.json()
            
            # Extract content from response
            if "choices" in response_data and len(response_data["choices"]) > 0:
                raw_text = response_data["choices"][0]["message"]["content"].strip()
            else:
                raise ValueError("No content in API response")
            
            # Parse and validate
            return self._parse_response(raw_text, schema)
            
        except requests.exceptions.HTTPError as e:
            logging.error(f"OpenRouter API error: {e}")
            if hasattr(e, 'response') and e.response:
                logging.error(f"Response: {e.response.text}")
            raise RuntimeError(f"OpenRouter API call failed: {e}")
        except Exception as e:
            logging.error(f"OpenRouter provider error: {e}")
            raise

