"""LiteLLM wrapper — unified LLM access with cost tracking."""

from functools import wraps
from typing import Callable

from litellm import completion
from crewai import LLM as CrewLLM

from repoinsight.config import settings


class TokenCounter:
    """Thread-safe token usage tracker."""

    def __init__(self) -> None:
        self._prompt_tokens = 0
        self._completion_tokens = 0

    def add(self, prompt: int, completion: int) -> None:
        self._prompt_tokens += prompt
        self._completion_tokens += completion

    @property
    def total(self) -> int:
        return self._prompt_tokens + self._completion_tokens

    def summary(self) -> str:
        return (
            f"Tokens — prompt: {self._prompt_tokens}, "
            f"completion: {self._completion_tokens}, "
            f"total: {self.total}"
        )


# Global counter instance
token_counter = TokenCounter()


def get_llm(task_type: str = "simple") -> CrewLLM:
    """Get a CrewAI-compatible LLM instance.

    Routes to different providers based on task complexity:
    - simple (Crawler, Doc): DeepSeek (cheap)
    - complex (Reviewer, Auditor): DeepSeek or Claude (configurable)
    """
    provider = settings.complex_llm_provider if task_type == "complex" else settings.simple_llm_provider

    if provider == "openai" and settings.openai_api_key:
        return CrewLLM(
            model=f"openai/{settings.openai_model}",
            api_key=settings.openai_api_key,
            temperature=0.3,
        )
    elif provider == "anthropic" and settings.anthropic_api_key:
        return CrewLLM(
            model="anthropic/claude-sonnet-4-6",
            api_key=settings.anthropic_api_key,
            temperature=0.3,
        )
    else:
        # Default: DeepSeek
        return CrewLLM(
            model=f"openai/{settings.deepseek_model}",
            base_url="https://api.deepseek.com/v1",
            api_key=settings.deepseek_api_key,
            temperature=0.3,
        )


def count_tokens(llm_call: Callable) -> Callable:
    """Decorator to track token usage for LLM calls."""

    @wraps(llm_call)
    def wrapper(*args, **kwargs):
        result = llm_call(*args, **kwargs)
        # LiteLLM sets usage info on the response object
        if hasattr(result, "usage"):
            token_counter.add(
                getattr(result.usage, "prompt_tokens", 0),
                getattr(result.usage, "completion_tokens", 0),
            )
        return result

    return wrapper
