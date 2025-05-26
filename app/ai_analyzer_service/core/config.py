from pydantic_settings import BaseSettings
from typing import Optional, Any
from pydantic import RedisDsn, field_validator, ValidationInfo

class Settings(BaseSettings):
    """
    Configuration settings for the AI Analyzer Service.
    This class handles all configuration parameters required for the AI analysis service,
    including API keys, Redis connection settings, queue configurations, and AI model settings.
    Uses Pydantic BaseSettings for environment variable loading and validation.
    Attributes:
        AI_ANALYZER_MY_GOOGLE_API_KEY (str): Required Google API key for AI analysis services.
        REDIS_HOST (str): Redis server hostname. Defaults to "redis".
        REDIS_PORT (int): Redis server port number. Defaults to 6379.
        REDIS_URL (Optional[RedisDsn]): Complete Redis connection URL. Auto-assembled if not provided.
        LOG_LEVEL (str): Application logging level. Defaults to "INFO".
        AI_ANALYSIS_QUEUE (str): Queue name for AI analysis tasks. Defaults to "gitinsight_ai_analysis".
        RESULT_QUEUE (str): Queue name for analysis results. Defaults to "gitinsight_results".
        AI_MODEL_NAME (str): Name of the AI model to use. Defaults to "gemini-1.5-flash-latest".
        AI_TOKENIZER_MODEL (str): Name of the tokenizer model. Defaults to "gemini-1.5-flash-latest".
    Note:
        Configuration values are loaded from environment variables or .env file.
        Redis URL is automatically constructed from host and port if not explicitly provided.
    """
    # Required for AI analysis
    AI_ANALYZER_MY_GOOGLE_API_KEY: str
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_URL: Optional[RedisDsn] = None

    @field_validator("REDIS_URL", mode='before')
    @classmethod
    def assemble_redis_connection(cls, v: Optional[str], info: ValidationInfo) -> Any:
        """
    Validates and assembles a Redis connection URL from component parts.
    This field validator can handle both direct REDIS_URL strings and component-based
    construction from REDIS_HOST and REDIS_PORT values.
    Args:
        v (Optional[str]): The direct REDIS_URL value if provided, or None if it should
        be constructed from components.
        info (ValidationInfo): Pydantic validation info containing other field values.
    Returns:
        Any: A valid Redis DSN URL string, or None if required components are missing.
        When v is a string, returns it directly. When v is None, attempts to build
        a Redis URL from REDIS_HOST and REDIS_PORT using database 0.
    Note:
        If REDIS_HOST or REDIS_PORT are missing and no direct REDIS_URL is provided,
        returns None. The constructed URL uses Redis database 0 by default.
    """
        values = info.data
        if isinstance(v, str):
            return v
        
        # Ensure values are present before trying to use them
        host = values.get("REDIS_HOST")
        port = values.get("REDIS_PORT")

        if host is None or port is None:
            if v is None: # Only try to build if v is None (meaning REDIS_URL was not directly provided)
                if host is None or port is None:
                    return None # Or raise ValueError("Cannot assemble REDIS_URL: HOST or PORT missing")

        return RedisDsn.build(
            scheme="redis",
            host=str(host), # cast to string
            port=int(port), # port is already int, but explicit cast for safety
            path="/0"
        )

    LOG_LEVEL: str = "INFO"
    AI_ANALYSIS_QUEUE: str = "gitinsight_ai_analysis"
    RESULT_QUEUE: str = "gitinsight_results"    
    AI_MODEL_NAME: str = "gemini-1.5-flash-latest"
    AI_TOKENIZER_MODEL: str = "gemini-1.5-flash-latest"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()