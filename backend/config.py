"""
config.py — Centralized configuration via Pydantic Settings.

All environment variables are validated here at startup.
Import `settings` everywhere instead of using os.getenv().
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from pydantic import field_validator


class Settings(BaseSettings):
    # ── Supabase ─────────────────────────────────────────────────────────────
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str = ""   # Optional — needed for bypassing RLS

    # ── Authentication ───────────────────────────────────────────────────────
    # Project JWT secret (Supabase → Settings → API → JWT Secret). When set,
    # tokens are verified locally with no network call. When blank, auth.py
    # falls back to the Supabase Auth API, which is slower but always correct.
    supabase_jwt_secret: str = ""

    # Master switch for request authentication. Never disable outside local
    # development — auth.get_principal refuses to honour it when app_env is
    # "production".
    auth_enabled: bool = True

    # Organization used for the synthetic principal when auth_enabled is false.
    dev_org_id: str = ""

    # Forward the caller's JWT to PostgREST so the RLS policies in
    # 006_audit_and_security.sql enforce tenant isolation at the database
    # layer. Requires migration 020 (which populates app_metadata with
    # organization_id) AND users to have re-authenticated since it ran —
    # otherwise current_user_org_id() returns NULL and every policy denies.
    # Application-layer checks in auth.Principal.assert_org apply either way.
    db_forward_user_jwt: bool = False

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

    # ── WHO ICD API ───────────────────────────────────────────────────────────
    who_icd_client_id: str = ""
    who_icd_client_secret: str = ""
    who_icd_token_endpoint: str = "https://icdaccessmanagement.who.int/connect/token"
    who_icd_api_base: str = "https://id.who.int"
    who_icd_default_version: str = "ICD-11"       # "ICD-11" | "ICD-10"
    who_icd_11_release: str = "2026-01"            # Latest ICD-11 release (YYYY-MM format)
    who_icd_10_release: str = "2019"               # ICD-10 release used

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"

    @field_validator("supabase_url", "groq_api_key")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty.")
        return value


@lru_cache()
def get_settings() -> Settings:
    """Returns cached Settings instance. Import this everywhere."""
    return Settings()


# Module-level convenience alias
settings = get_settings()
