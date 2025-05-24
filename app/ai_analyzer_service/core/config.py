
from pydantic_settings import BaseSettings
from typing import Optional, Any
from pydantic import RedisDsn, validator

class Settings(BaseSettings):
    MY_GOOGLE_API_KEY: str # Required for AI analysis

    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379  # Changed from str to int, and default value to int
    REDIS_URL: Optional[RedisDsn] = None

    @validator("REDIS_URL", pre=True, always=True)
    def assemble_redis_connection(cls, v: Optional[str], values: dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return RedisDsn.build(
            scheme="redis",
            host=values.get("REDIS_HOST"),
            port=values.get("REDIS_PORT"), # This will now be an integer
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
    
**Key change:** - `REDIS_PORT: str = "6379"` changed to `REDIS_PORT: int = 6379`. #### 3. Modify `app/repo_processor_service/core/config.py` html
File: app/repo_processor_service/core/config.py


from pydantic_settings import BaseSettings
from typing import Optional, Any
from pydantic import RedisDsn, validator

class Settings(BaseSettings):
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379  # Changed from str to int, and default value to int
    REDIS_URL: Optional[RedisDsn] = None

    @validator("REDIS_URL", pre=True, always=True)
    def assemble_redis_connection(cls, v: Optional[str], values: dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return RedisDsn.build(
            scheme="redis",
            host=values.get("REDIS_HOST"),
            port=values.get("REDIS_PORT"), # This will now be an integer
            path="/0"
        )

    LOG_LEVEL: str = "INFO"
    # Queue names (though primarily consuming one, good to have for consistency if sending)
    REPO_PROCESSING_QUEUE: str = "gitinsight_repo_processing"
    AI_ANALYSIS_QUEUE: str = "gitinsight_ai_analysis"
    RESULT_QUEUE: str = "gitinsight_results"

    # Temp directory for cloning, ensure this path is writable by the container/worker
    CLONE_TEMP_DIR_BASE: str = "/tmp/gitinsight_clones"


    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()