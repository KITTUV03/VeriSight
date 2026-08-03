"""
Base Agent for VeriSight.

Abstract base class providing LLM interface abstraction, structured
prompt construction, JSON output parsing with Pydantic validation,
retry logic, and tracing. Supports Gemini, OpenAI, and Anthropic
via adapter pattern.
"""

import json
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from verisight.config import get_config
from verisight.utils.logger import get_logger

logger = get_logger("base_agent")
T = TypeVar("T", bound=BaseModel)


class LLMAdapter:
    """Adapter for LLM API calls. Supports Gemini (default)."""

    def __init__(self):
        config = get_config()
        self.provider = config.llm.provider
        self.api_key = config.llm.api_key
        self.model_name = config.llm.model_name
        self.temperature = config.llm.temperature
        self.max_output_tokens = config.llm.max_output_tokens
        self._model = None

    def _init_gemini(self):
        """Initialize Gemini model."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel(self.model_name)
            logger.info(f"Gemini model initialized: {self.model_name}")
        except ImportError:
            raise RuntimeError(
                "google-generativeai not installed. "
                "Install with: pip install google-generativeai"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Gemini: {e}")

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """
        Generate a response from the LLM.

        Args:
            prompt: User prompt.
            system_prompt: System prompt with agent role/instructions.

        Returns:
            Raw text response from the LLM.
        """
        # Fail fast if no API key is configured
        if not self.api_key:
            raise RuntimeError(
                "No LLM API key configured. Set GEMINI_API_KEY or use --api-key. "
                "Pipeline will use deterministic fallback."
            )

        if self.provider == "gemini":
            return self._generate_gemini(prompt, system_prompt)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _generate_gemini(self, prompt: str, system_prompt: str = "") -> str:
        """Generate using Gemini API."""
        if self._model is None:
            self._init_gemini()

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        try:
            import google.generativeai as genai
            response = self._model.generate_content(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_output_tokens,
                )
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise


class BaseAgent(ABC):
    """
    Abstract base agent with LLM reasoning capabilities.

    All VeriSight agents inherit from this class, gaining:
    - Structured prompt construction
    - JSON output parsing with Pydantic validation
    - Retry logic for malformed LLM responses
    - Logging and tracing
    """

    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(f"agent.{name}")
        self._llm = None

    @property
    def llm(self) -> LLMAdapter:
        """Lazy-initialize LLM adapter."""
        if self._llm is None:
            self._llm = LLMAdapter()
        return self._llm

    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """Execute the agent's primary task."""
        pass

    def reason(
        self,
        prompt: str,
        system_prompt: str = "",
        output_model: Optional[Type[T]] = None,
        max_retries: int = 3,
    ) -> Any:
        """
        Use LLM reasoning with structured output.

        Args:
            prompt: The reasoning prompt.
            system_prompt: System-level instructions.
            output_model: Optional Pydantic model for output validation.
            max_retries: Max retry attempts for malformed responses.

        Returns:
            Pydantic model instance if output_model specified, else raw text.
        """
        config = get_config()
        retries = max_retries if max_retries else config.llm.max_retries

        for attempt in range(retries):
            try:
                self.logger.info(
                    f"LLM reasoning attempt {attempt + 1}/{retries}"
                )
                response = self.llm.generate(prompt, system_prompt)

                if output_model:
                    return self._parse_json_response(response, output_model)
                return response

            except ValidationError as e:
                self.logger.warning(
                    f"Response validation failed (attempt {attempt + 1}): {e}"
                )
                if attempt < retries - 1:
                    # Add error feedback to prompt for retry
                    prompt = (
                        f"{prompt}\n\n"
                        f"PREVIOUS RESPONSE FAILED VALIDATION:\n{e}\n"
                        f"Please fix the JSON output and try again."
                    )
                    time.sleep(1)
                else:
                    raise

            except Exception as e:
                self.logger.error(
                    f"LLM call failed (attempt {attempt + 1}): {e}"
                )
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise

    def _parse_json_response(
        self, response: str, model_class: Type[T]
    ) -> T:
        """
        Parse JSON from LLM response and validate with Pydantic.

        Handles common LLM output issues like markdown code fences,
        extra text before/after JSON, etc.
        """
        # Try to extract JSON from the response
        json_str = self._extract_json(response)

        if json_str is None:
            raise ValidationError.from_exception_data(
                title=model_class.__name__,
                line_errors=[],
            )

        try:
            data = json.loads(json_str)
            return model_class.model_validate(data)
        except json.JSONDecodeError as e:
            self.logger.warning(f"JSON decode error: {e}")
            # Try to fix common JSON issues
            fixed = self._fix_json(json_str)
            data = json.loads(fixed)
            return model_class.model_validate(data)

    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON object from LLM response text."""
        # Try markdown code block first
        json_match = re.search(
            r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text
        )
        if json_match:
            return json_match.group(1).strip()

        # Try to find raw JSON object
        # Find the first { and last }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return text[first_brace:last_brace + 1]

        # Try to find JSON array
        first_bracket = text.find("[")
        last_bracket = text.rfind("]")
        if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
            return text[first_bracket:last_bracket + 1]

        return None

    def _fix_json(self, json_str: str) -> str:
        """Attempt to fix common JSON formatting issues."""
        # Remove trailing commas before } or ]
        fixed = re.sub(r",\s*([}\]])", r"\1", json_str)
        # Replace single quotes with double quotes
        fixed = fixed.replace("'", '"')
        # Remove comments
        fixed = re.sub(r"//.*?\n", "\n", fixed)
        return fixed

    def build_prompt(
        self,
        template: str,
        context: Dict[str, str],
        output_schema: Optional[Type[BaseModel]] = None,
    ) -> str:
        """
        Build a structured prompt from a template and context.

        Args:
            template: Prompt template with {placeholder} markers.
            context: Dict of placeholder values.
            output_schema: Optional Pydantic model to include schema in prompt.

        Returns:
            Formatted prompt string.
        """
        # Only run format() when there are actual placeholders to fill;
        # avoids crashing on literal curly braces in embedded code.
        prompt = template.format(**context) if context else template

        if output_schema:
            schema = output_schema.model_json_schema()
            prompt += (
                f"\n\nRespond with a valid JSON object matching this schema:\n"
                f"```json\n{json.dumps(schema, indent=2)}\n```\n"
                f"Return ONLY the JSON object, no additional text."
            )

        return prompt
