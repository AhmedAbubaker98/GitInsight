from pydantic_settings import BaseSettings
from typing import Optional, Any
from pydantic import RedisDsn, validator # Or field_validator if using Pydantic v2

class Settings(BaseSettings):
    AI_ANALYZER_MY_GOOGLE_API_KEY: str # Required for AI analysis

    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_URL: Optional[RedisDsn] = None

    # If using Pydantic v2, use @field_validator and @classmethod
    # from pydantic import field_validator, ValidationInfo
    # @field_validator("REDIS_URL", mode='before')
    # @classmethod
    # def assemble_redis_connection(cls, v: Optional[str], info: ValidationInfo) -> Any:
    #     if isinstance(v, str):
    #         return v
    #     # Access data from info.data for Pydantic v2
    #     host = info.data.get("REDIS_HOST")
    #     port = info.data.get("REDIS_PORT")
    #     if host and port is not None: # Ensure port is not None, 0 is a valid port for some contexts
    #         return RedisDsn.build(
    #             scheme="redis",
    #             host=str(host),
    #             port=int(port),
    #             path="/0"
    #         )
    #     return v # Or raise an error if construction is mandatory and data is missing

    # Pydantic v1 style validator
    @validator("REDIS_URL", pre=True, always=True)
    @classmethod # Add classmethod decorator
    def assemble_redis_connection(cls, v: Optional[str], values: dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        
        # Ensure values are present before trying to use them
        host = values.get("REDIS_HOST")
        port = values.get("REDIS_PORT")

        if host is None or port is None:
            # This might happen if REDIS_URL is set to None and defaults for HOST/PORT are not sufficient
            # or if this validator runs before HOST/PORT are fully processed.
            # Depending on Pydantic version and how BaseSettings works, this might need careful handling.
            # For Pydantic V1 with 'always=True', 'values' should contain already processed fields.
            # However, if REDIS_URL is None, this validator still runs.
            # It's good practice to ensure the values exist.
            # If they are guaranteed by BaseSettings defaults, this check might be redundant,
            # but it's safer.
            # If REDIS_URL could be None and that's acceptable, return v (which would be None).
            # If REDIS_URL *must* be built, then raise an error here if host/port are missing.
            if v is None: # Only try to build if v is None (meaning REDIS_URL was not directly provided)
                if host is None or port is None:
                    # This indicates a configuration issue if REDIS_URL must be built.
                    # If REDIS_URL is Optional and can be None, then this is fine, return None.
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

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()