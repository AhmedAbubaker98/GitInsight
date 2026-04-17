from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import PostgresDsn, RedisDsn
import logging

# Set up logging
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    SESSION_SECRET: str
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    
    # Database - full URL required
    MY_DATABASE_URL: PostgresDsn

    # Redis configuration
    REDIS_URL: RedisDsn

    # Logging configuration
    LOG_LEVEL: str = "INFO"

    # AI provider configuration (used for health diagnostics endpoint)
    AI_PROVIDER: str = "gemini"
    AI_MODEL_NAME: Optional[str] = None
    AI_REQUEST_TIMEOUT_SECONDS: int = 120
    AI_ANALYZER_MY_GOOGLE_API_KEY: Optional[str] = None
    AI_LMSTUDIO_BASE_URL: Optional[str] = None
    AI_LMSTUDIO_CHAT_ENDPOINT: str = "/v1/chat/completions"
    AI_LMSTUDIO_API_KEY: Optional[str] = None
    
    # Rate limiting
    RATE_LIMIT_GUEST: str = "1/minute"
    RATE_LIMIT_USER: str = "30/minute"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()

logger.info("Effective Database URL in initialized settings: %s", settings.MY_DATABASE_URL)
logger.info("Effective Redis URL in initialized settings: %s", settings.REDIS_URL)
