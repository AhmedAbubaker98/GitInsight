"""
Shared configuration for GitInsight microservices.

This module centralizes queue names and Redis configuration to ensure
consistency across all services.
"""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional


class SharedConfig(BaseSettings):
    """Shared configuration for all GitInsight services."""
    
    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Queue Names - Centralized definition
    REPO_PROCESSING_QUEUE: str = "gitinsight_repo_processing"
    AI_ANALYSIS_QUEUE: str = "gitinsight_ai_analysis" 
    RESULT_QUEUE: str = "gitinsight_results"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    @field_validator('LOG_LEVEL')
    @classmethod
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'LOG_LEVEL must be one of {valid_levels}')
        return v.upper()

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables


# Global instance
shared_settings = SharedConfig()
