from typing import Literal, Optional

from pydantic import RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    Configuration settings for the AI Analyzer Service.

    This service supports multiple model providers. Required fields depend on
    AI_PROVIDER.
    """
    # Required for all providers
    REDIS_URL: RedisDsn

    LOG_LEVEL: str = "INFO"

    # Provider configuration
    AI_PROVIDER: Literal["gemini", "lmstudio"] = "gemini"
    AI_MODEL_NAME: str

    # Shared generation settings
    AI_REQUEST_TIMEOUT_SECONDS: int = 120
    AI_TEMPERATURE: float = 0.6
    AI_MAX_OUTPUT_TOKENS: Optional[int] = None

    # Gemini settings (required when AI_PROVIDER=gemini)
    AI_ANALYZER_MY_GOOGLE_API_KEY: Optional[str] = None

    # LM Studio settings (required when AI_PROVIDER=lmstudio)
    AI_LMSTUDIO_BASE_URL: Optional[str] = None
    AI_LMSTUDIO_API_KEY: Optional[str] = None
    AI_LMSTUDIO_CHAT_ENDPOINT: str = "/v1/chat/completions"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("AI_MAX_OUTPUT_TOKENS", mode="before")
    @classmethod
    def normalize_optional_int(cls, value):
        if value == "" or value is None:
            return None
        return value

    @model_validator(mode="after")
    def validate_provider_configuration(self):
        if not self.AI_MODEL_NAME or not self.AI_MODEL_NAME.strip():
            raise ValueError("AI_MODEL_NAME must be set.")

        if self.AI_PROVIDER == "gemini" and not self.AI_ANALYZER_MY_GOOGLE_API_KEY:
            raise ValueError(
                "AI_ANALYZER_MY_GOOGLE_API_KEY is required when AI_PROVIDER=gemini."
            )

        if self.AI_PROVIDER == "lmstudio" and not self.AI_LMSTUDIO_BASE_URL:
            raise ValueError(
                "AI_LMSTUDIO_BASE_URL is required when AI_PROVIDER=lmstudio."
            )

        if not 0 <= self.AI_TEMPERATURE <= 2:
            raise ValueError("AI_TEMPERATURE must be between 0 and 2.")

        if self.AI_MAX_OUTPUT_TOKENS is not None and self.AI_MAX_OUTPUT_TOKENS <= 0:
            raise ValueError("AI_MAX_OUTPUT_TOKENS must be a positive integer when set.")

        return self

settings = Settings()  # pyright: ignore[reportCallIssue]