from pydantic_settings import BaseSettings
from typing import Optional, Any
from pydantic import RedisDsn, validator

class Settings(BaseSettings):
    MY_GOOGLE_API_KEY: str # Required for AI analysis

    REDIS_HOST: str = "redis"
    REDIS_PORT: str = "6379"
    REDIS_URL: Optional[RedisDsn] = None

    @validator("REDIS_URL", pre=True, always=True)
    def assemble_redis_connection(cls, v: Optional[str], values: dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return RedisDsn.build(
            scheme="redis",
            host=values.get("REDIS_HOST"),
            port=values.get("REDIS_PORT"),
            path="/0"
        )

    LOG_LEVEL: str = "INFO"
    AI_ANALYSIS_QUEUE: str = "gitinsight_ai_analysis"
    RESULT_QUEUE: str = "gitinsight_results"

    # AI Model specific settings (can be moved from analyzer.py if needed)
    AI_MODEL_NAME: str = "gemini-1.5-flash-latest" # Adjusted to a common valid model name
    AI_TOKENIZER_MODEL: str = "gemini-1.5-flash-latest" # Match model for tokenizer


    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()