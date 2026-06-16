"""Configuration loader — reads .env and provides typed Settings."""

import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel


def _find_env() -> Path | None:
    """Walk up from cwd to find .env file."""
    current = Path.cwd()
    for _ in range(5):
        env_file = current / ".env"
        if env_file.exists():
            return env_file
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


_env_path = _find_env()
if _env_path:
    load_dotenv(_env_path)


class Settings(BaseModel):
    """Typed settings loaded from environment variables."""

    # LLM
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Provider routing
    simple_llm_provider: str = os.getenv("SIMPLE_LLM_PROVIDER", "deepseek")
    complex_llm_provider: str = os.getenv("COMPLEX_LLM_PROVIDER", "deepseek")

    # Search
    serper_api_key: str = os.getenv("SERPER_API_KEY", "")

    # Paths
    tmp_repos_dir: Path = Path(os.getenv("TMP_REPOS_DIR", Path.cwd() / "tmp_repos"))
    chroma_dir: Path = Path(os.getenv("CHROMA_DIR", Path.cwd() / "chroma_db"))

    @property
    def has_llm(self) -> bool:
        return bool(self.deepseek_api_key or self.openai_api_key or self.anthropic_api_key)


settings = Settings()
