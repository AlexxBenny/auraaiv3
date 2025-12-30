"""Google Gemini provider implementation"""

import requests
import logging
from typing import Dict, Any, Optional
from .base import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    """Google Gemini API provider"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash", **kwargs):
        super().__init__(api_key, **kwargs)
        self.model = model
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        
        if not self.api_key:
            raise ValueError("Gemini API key is required")
    
    def generate(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate response using Gemini API"""
        
        # Build system prompt with schema constraints
        full_prompt = self._build_system_prompt(prompt, schema)
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": full_prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.1 if schema else 0.3,
                "maxOutputTokens": 2000,
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
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
            
            # Extract text from response
            if "candidates" in response_data and len(response_data["candidates"]) > 0:
                raw_text = response_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                raise ValueError("No content in API response")
            
            # Parse and validate
            return self._parse_response(raw_text, schema)
            
        except requests.exceptions.HTTPError as e:
            logging.error(f"Gemini API error: {e}")
            if hasattr(e, 'response') and e.response:
                logging.error(f"Response: {e.response.text}")
            raise RuntimeError(f"Gemini API call failed: {e}")
        except Exception as e:
            logging.error(f"Gemini provider error: {e}")
            raise

