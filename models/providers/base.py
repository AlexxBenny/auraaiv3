"""Base LLM provider interface - ALL providers must implement this"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers
    
    CRITICAL RULES:
    1. Always return JSON (never executable code)
    2. Schema validation required
    3. No code generation allowed
    """
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        self.api_key = api_key
        self.config = kwargs
    
    @abstractmethod
    def generate(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate a response from the LLM
        
        Args:
            prompt: The input prompt
            schema: Optional JSON schema for structured output
            
        Returns:
            Dict containing the response. Must be valid JSON.
            
        Raises:
            ValueError: If response is not valid JSON
            RuntimeError: If API call fails
        """
        raise NotImplementedError
    
    def _validate_schema(self, response: Dict[str, Any], schema: Optional[Dict[str, Any]]) -> bool:
        """Validate response against schema if provided"""
        if schema is None:
            return True
        
        # Basic schema validation (can be enhanced with jsonschema library)
        # For now, just check that required keys exist
        required = schema.get("required", [])
        for key in required:
            if key not in response:
                return False
        return True
    
    def _parse_response(self, raw_response: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Parse and validate LLM response.
        
        SAFETY: Rejects multi-JSON responses (LLM tried to return multiple tools).
        """
        try:
            # Try to extract JSON from markdown code blocks
            if "```json" in raw_response:
                json_str = raw_response.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_response:
                json_str = raw_response.split("```")[1].split("```")[0].strip()
            elif "{" in raw_response and "}" in raw_response:
                # Extract FIRST JSON object only
                start = raw_response.find("{")
                # Find matching closing brace (handle nested objects)
                depth = 0
                end = start
                for i, char in enumerate(raw_response[start:], start):
                    if char == "{":
                        depth += 1
                    elif char == "}":
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
                json_str = raw_response[start:end]
                
                # SAFETY: Check for multi-JSON (trailing content after first object)
                remaining = raw_response[end:].strip()
                if remaining and remaining.startswith("{"):
                    raise ValueError(
                        "Multi-JSON detected: LLM returned multiple tool objects. "
                        "This request requires goal-path routing, not single-tool resolution."
                    )
            else:
                json_str = raw_response.strip()
            
            # Parse JSON
            response = json.loads(json_str)
            
            # Validate schema
            if not self._validate_schema(response, schema):
                raise ValueError(f"Response does not match schema: {schema}")
            
            return response
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response: {e}\nRaw response: {raw_response[:200]}")
    
    def _build_system_prompt(self, user_prompt: str, schema: Optional[Dict[str, Any]] = None) -> str:
        """Build system prompt with schema constraints"""
        base_prompt = f"""You are a helpful assistant. Respond ONLY with valid JSON.

CRITICAL RULES:
1. NEVER generate executable code
2. NEVER return Python code blocks
3. ALWAYS return valid JSON only
4. Follow the provided schema exactly

"""
        
        if schema:
            base_prompt += f"\nRequired JSON Schema:\n{json.dumps(schema, indent=2)}\n"
        
        base_prompt += f"\nUser Request: {user_prompt}\n\nRespond with JSON only:"
        
        return base_prompt

