from pydantic_settings import BaseSettings
from pydantic import RedisDsn

class Settings(BaseSettings):
    """
    Configuration settings for the AI Analyzer Service.
    This class handles all configuration parameters required for the AI analysis service,
    including API keys, Redis connection settings, queue configurations, and AI model settings.
    Uses Pydantic BaseSettings for environment variable loading and validation.
    Attributes:
        AI_ANALYZER_MY_GOOGLE_API_KEY (str): Required Google API key for AI analysis services.
        REDIS_URL (RedisDsn): Complete Redis connection URL. Required.
        LOG_LEVEL (str): Application logging level. Defaults to "INFO".
        AI_ANALYSIS_QUEUE (str): Queue name for AI analysis tasks. Defaults to "gitinsight_ai_analysis".
        RESULT_QUEUE (str): Queue name for analysis results. Defaults to "gitinsight_results".
        AI_MODEL_NAME (str): Name of the AI model to use. Defaults to "gemini-2.5-pro-preview-05-06".
        AI_TOKENIZER_MODEL (str): Name of the tokenizer model. Defaults to "gemini-1.5-flash-latest".
    Note:
        Configuration values are loaded from environment variables or .env file.
        Redis URL must be provided as a complete connection string.
    """
    # Required for AI analysis
    AI_ANALYZER_MY_GOOGLE_API_KEY: str
    REDIS_URL: RedisDsn

    LOG_LEVEL: str = "INFO"
    AI_ANALYSIS_QUEUE: str = "gitinsight_ai_analysis"
    RESULT_QUEUE: str = "gitinsight_results"    
    # AI_MODEL_NAME: str = "gemini-1.5-flash-latest" # Use the latest flash model for production
    AI_MODEL_NAME: str = "gemini-2.5-pro-preview-05-06" #preview models are NOT production ready
    AI_TOKENIZER_MODEL: str = "gemini-1.5-flash-latest"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()