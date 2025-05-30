from pydantic_settings import BaseSettings
from typing import Optional, Any
from pydantic import RedisDsn, field_validator, ValidationInfo

class Settings(BaseSettings):
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_URL: Optional[RedisDsn] = None

    @field_validator("REDIS_URL", mode='before')
    @classmethod
    def assemble_redis_connection(cls, v: Optional[str], info: ValidationInfo) -> Any:
        values = info.data
        if isinstance(v, str):
            return v
        return RedisDsn.build(
            scheme="redis",
            host=values.get("REDIS_HOST"),
            port=values.get("REDIS_PORT"),
            path="/0"
        )

    LOG_LEVEL: str = "INFO"
    # Queue names (though primarily consuming one, good to have for consistency if sending)
    REPO_PROCESSING_QUEUE: str = "gitinsight_repo_processing"
    AI_ANALYSIS_QUEUE: str = "gitinsight_ai_analysis"
    RESULT_QUEUE: str = "gitinsight_results"    # Temp directory for cloning, ensure this path is writable by the container/worker
    CLONE_TEMP_DIR_BASE: str = "/tmp/gitinsight_clones"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()