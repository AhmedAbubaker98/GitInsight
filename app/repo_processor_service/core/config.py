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
    # Queue names 
    REPO_PROCESSING_QUEUE: str = "gitinsight_repo_processing"
    AI_ANALYSIS_QUEUE: str = "gitinsight_ai_analysis"
    RESULT_QUEUE: str = "gitinsight_results"    
    CLONE_TEMP_DIR_BASE: str = "/tmp/gitinsight_clones"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()