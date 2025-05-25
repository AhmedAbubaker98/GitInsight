import os
from pydantic_settings import BaseSettings
from typing import Optional, Any
from pydantic import PostgresDsn, RedisDsn, validator
import logging # Import logging

# It's better to use logging than print for production/containerized apps
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    SESSION_SECRET: str
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    MY_GOOGLE_API_KEY: Optional[str] = None

    # Database
    POSTGRES_USER: str = "gitinsight_user"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "gitinsight_db"
    DATABASE_HOST: str = "db"
    DATABASE_PORT: str = "5432"
    MY_DATABASE_URL: Optional[PostgresDsn] = None

    @validator("MY_DATABASE_URL", pre=True, always=True)
    def assemble_db_connection(cls, v: Optional[str], values: dict[str, Any]) -> Any:
        final_url_str: Optional[str] = None
        db_host_for_assembly: str = values.get("DATABASE_HOST", "db")

        if isinstance(v, str):
            final_url_str = v  # MY_DATABASE_URL was set in env
            logger.info(f"Database URL (MY_DATABASE_URL) is from environment: '{final_url_str}'")
        else:
            # MY_DATABASE_URL not set in env, assemble it
            logger.info(f"Assembling Database URL (MY_DATABASE_URL) using DATABASE_HOST: '{db_host_for_assembly}' and other POSTGRES_* variables.")
            try:
                built_url = PostgresDsn.build(
                    scheme="postgresql+asyncpg",
                    username=values.get("POSTGRES_USER"),
                    password=values.get("POSTGRES_PASSWORD"),
                    host=db_host_for_assembly,
                    port=str(values.get("DATABASE_PORT")),
                    path=f"/{values.get('POSTGRES_DB') or ''}",
                )
                final_url_str = str(built_url)
                logger.info(f"Assembled Database URL (MY_DATABASE_URL): '{final_url_str}'")
            except Exception as e:
                logger.error(f"Error assembling database URL: {e}", exc_info=True)
                raise ValueError(f"Could not assemble database URL: {e}") from e
        
        # Check for common misconfiguration when running in Docker
        if final_url_str and ("localhost" in final_url_str or "127.0.0.1" in final_url_str) and db_host_for_assembly == "db":
            logger.warning(
                f"WARNING: Constructed Database URL ('{final_url_str}') contains 'localhost' or '127.0.0.1', "
                f"but the configured DATABASE_HOST for assembly is '{db_host_for_assembly}'. "
                f"In a Docker environment, you should typically use the service name (e.g., 'db') as the host. "
                f"If MY_DATABASE_URL was provided via environment, ensure it uses the correct Docker service name."
            )
        
        if not final_url_str:
            logger.error("Failed to determine a valid database URL.")
            raise ValueError("Database URL could not be determined.")
            
        return final_url_str # Return as string, Pydantic will validate it against PostgresDsn type

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_URL: Optional[RedisDsn] = None

    @validator("REDIS_URL", pre=True, always=True)
    def assemble_redis_connection(cls, v: Optional[str], values: dict[str, Any]) -> Any:
        if isinstance(v, str):
            # logger.info(f"Redis URL is from environment: '{v}'") # Optional: log if needed
            return v
        
        redis_host_for_assembly = values.get("REDIS_HOST", "redis")
        redis_port_for_assembly = values.get("REDIS_PORT", 6379)
        # logger.info(f"Assembling Redis URL using REDIS_HOST: '{redis_host_for_assembly}', REDIS_PORT: {redis_port_for_assembly}") # Optional: log
        
        return RedisDsn.build(
            scheme="redis",
            host=redis_host_for_assembly,
            port=redis_port_for_assembly,
            path="/0"
        )

    LOG_LEVEL: str = "INFO"
    RATE_LIMIT_GUEST: str = "5/minute"
    RATE_LIMIT_USER: str = "30/minute"

    REPO_PROCESSING_QUEUE: str = "gitinsight_repo_processing"
    AI_ANALYSIS_QUEUE: str = "gitinsight_ai_analysis"
    RESULT_QUEUE: str = "gitinsight_results"

    class Config:
        env_file = ".env" # This line indicates Pydantic will try to load from .env
        env_file_encoding = 'utf-8'

settings = Settings()
# Log the effective database URL after settings object is initialized
# Note: Accessing settings.MY_DATABASE_URL here might re-trigger validation if not careful with Pydantic versions/models
# The logger inside the validator is usually sufficient for first-time load.
# Forcing a log here can be done, but ensure it's after full initialization.
# Example: In your main.py or lifespan, you can log settings.MY_DATABASE_URL.
# For immediate feedback after Settings() is instantiated:
logger.info(f"Effective Database URL in initialized settings: {settings.MY_DATABASE_URL}")
logger.info(f"Effective Redis URL in initialized settings: {settings.REDIS_URL}")
