from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'finn.db').as_posix()}"
    frontend_origin: str = "http://localhost:3000"
    job_token: str = "change-me"

    llm_provider: str = "gemini"  # gemini | groq | openai | anthropic | none
    llm_api_key: str = ""
    llm_fast_model: str = ""
    llm_smart_model: str = ""
    llm_daily_budget_usd: float = 0.50

    websearch_provider: str = "none"  # none | tavily | brave
    websearch_api_key: str = ""

    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:finn@example.com"

    data_dir: Path = BACKEND_DIR / "data"
    replay_default: bool = False
    run_jobs_on_start: bool = False

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider != "none" and bool(self.llm_api_key)


DEFAULT_MODELS = {
    # VERIFY against the provider's current model list; override with LLM_FAST_MODEL / LLM_SMART_MODEL.
    "gemini": ("gemini-2.5-flash-lite", "gemini-2.5-flash"),
    "groq": ("llama-3.1-8b-instant", "llama-3.3-70b-versatile"),
    "openai": ("gpt-4.1-mini", "gpt-4.1"),
    "anthropic": ("claude-haiku-4-5-20251001", "claude-sonnet-5"),
}


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    return s
