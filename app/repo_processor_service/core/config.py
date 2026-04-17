from pydantic_settings import BaseSettings
from pydantic import RedisDsn

class Settings(BaseSettings):
    """
    Configuration settings for the repository processor service.
    
    Redis URL must be provided as a complete connection string
    (e.g., redis://localhost:6379/0).
    """
    REDIS_URL: RedisDsn

    LOG_LEVEL: str = "INFO"
    CLONE_TEMP_DIR_BASE: str = "/tmp/gitinsight_clones"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()