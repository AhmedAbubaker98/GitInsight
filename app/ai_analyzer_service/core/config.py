from pydantic_settings import BaseSettings
from typing import Optional, Any
from pydantic import RedisDsn, field_validator, ValidationInfo

class Settings(BaseSettings):
    # Required for AI analysis
    AI_ANALYZER_MY_GOOGLE_API_KEY: str
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_URL: Optional[RedisDsn] = None

    @field_validator("REDIS_URL", mode='before')
    @classmethod
    def assemble_redis_connection(cls, v: Optional[str], info: ValidationInfo) -> Any:
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