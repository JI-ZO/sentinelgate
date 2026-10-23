"""Configuration management using Pydantic Settings."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """SentinelGate application settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_prefix="SENTINEL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server details
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    environment: str = "production"

    # Upstream LLM Provider
    upstream_provider: Literal["mock", "openai"] = "mock"
    upstream_base_url: str = "https://api.openai.com/v1"
    upstream_api_key: str = ""
    upstream_timeout_seconds: float = 30.0

    # Guardrails: Prompt Injection
    guardrail_enable_injection_defense: bool = True
    guardrail_injection_threshold: float = 0.65

    # Guardrails: PII Redaction / Masking
    guardrail_enable_pii_masking: bool = True
    guardrail_pii_action: Literal["mask", "block"] = "mask"

    # Guardrails: Groundedness & Hallucination
    guardrail_enable_hallucination_eval: bool = True
    guardrail_hallucination_threshold: float = 0.40

    # Semantic Caching
    cache_enabled: bool = True
    cache_backend: Literal["memory", "redis"] = "memory"
    cache_similarity_threshold: float = 0.92
    cache_ttl_seconds: int = 3600
    redis_url: str = "redis://localhost:6379/0"

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60
    rate_limit_tokens_per_minute: int = 100000


# Singleton instance
settings = Settings()
