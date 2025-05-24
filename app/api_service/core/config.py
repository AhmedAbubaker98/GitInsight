import os
from pydantic_settings import BaseSettings
from typing import Optional, Any
from pydantic import PostgresDsn, RedisDsn, validator

class Settings(BaseSettings):
    SESSION_SECRET: str
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    MY_GOOGLE_API_KEY: Optional[str] = None # API service itself doesn't use it directly, but good to have if it did.

    # Database
    POSTGRES_USER: str = "gitinsight_user"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "gitinsight_db"
    DATABASE_HOST: str = "db"
    DATABASE_PORT: str = "5432" # Keep as string if PostgresDsn.build handles it, but int is safer for Pydantic fields
    MY_DATABASE_URL: Optional[PostgresDsn] = None

    @validator("MY_DATABASE_URL", pre=True, always=True)
    def assemble_db_connection(cls, v: Optional[str], values: dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("DATABASE_HOST"),
            port=str(values.get("DATABASE_PORT")), # Ensure port is string for PostgresDsn.build if it expects string
            path=f"/{values.get('POSTGRES_DB') or ''}",
        )

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379  # Changed from str to int, and default value to int
    REDIS_URL: Optional[RedisDsn] = None

    @validator("REDIS_URL", pre=True, always=True)
    def assemble_redis_connection(cls, v: Optional[str], values: dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        # Pydantic will have already ensured REDIS_PORT is an int if loaded from env var
        # or it's already an int from the default value.
        return RedisDsn.build(
            scheme="redis",
            host=values.get("REDIS_HOST"),
            port=values.get("REDIS_PORT"), # This will now be an integer
            path="/0" # Default Redis DB
        )

    LOG_LEVEL: str = "INFO"
    # Rate Limiting (example, you'd integrate a library like slowapi)
    RATE_LIMIT_GUEST: str = "5/minute"
    RATE_LIMIT_USER: str = "30/minute"

    # Queue names
    REPO_PROCESSING_QUEUE: str = "gitinsight_repo_processing"
    AI_ANALYSIS_QUEUE: str = "gitinsight_ai_analysis"
    RESULT_QUEUE: str = "gitinsight_results"


    class Config:
        # env_file = ".env"
        env_file_encoding = 'utf-8'
        # For Docker, env vars might be passed directly, not from .env file
        # So ensure your Docker setup passes these vars or mounts the .env

settings = Settings()