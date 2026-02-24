"""
config.py — Centralized configuration via Pydantic Settings.

All environment variables are validated here at startup.
Import `settings` everywhere instead of using os.getenv().
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Supabase ─────────────────────────────────────────────────────────────
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str = ""   # Optional — needed for bypassing RLS

    # ── Groq LLM ─────────────────────────────────────────────────────────────
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    groq_model_version: str = "2024-12"
    groq_timeout_seconds: int = 15
    groq_max_retries: int = 1
    groq_max_tokens: int = 2048

    # ── Medical Standard Versions ─────────────────────────────────────────────
    icd_version: str = "ICD-10-CM-2024"
    snomed_version: str = "SNOMED-CT-2024"
    loinc_version: str = "LOINC-2.77"

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Returns cached Settings instance. Import this everywhere."""
    return Settings()


# Module-level convenience alias
settings = get_settings()
