import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    SESSION_SECRET: str
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    MY_GOOGLE_API_KEY: str
    MY_DATABASE_URL: Optional[str] = None
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()