from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, Enum as SAEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import datetime
import enum

# Added imports for Pydantic models
from pydantic import BaseModel
from typing import Optional, Dict, Any

Base = declarative_base()

class AnalysisStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING_REPO = "processing_repo"
    PROCESSING_AI = "processing_ai"
    COMPLETED = "completed"
    FAILED = "failed"

class AnalysisHistory(Base):
    __tablename__ = "analysis_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_github_id = Column(String, index=True, nullable=True) # Can be null for guest users
    repository_url = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    parameters_used = Column(JSON, nullable=False)
    summary_content = Column(Text, nullable=True)
    status = Column(SAEnum(AnalysisStatus), default=AnalysisStatus.QUEUED, nullable=False)
    error_message = Column(Text, nullable=True)

    def __repr__(self):
        # Improved __repr__ for better debugging
        status_value = self.status.value if self.status else None
        return f"<AnalysisHistory(id={self.id}, url='{self.repository_url}', status='{status_value}')>"

# --- Added Pydantic Models for API responses ---

class AnalysisHistoryItem(BaseModel):
    id: int
    repository_url: str
    timestamp: datetime.datetime # Explicitly use datetime.datetime
    status: AnalysisStatus
    parameters_used: Dict[str, Any]

    # Pydantic V2 configuration for ORM mode
    model_config = {
        "from_attributes": True
    }
    # For Pydantic V1, you would use:
    # class Config:
    #     orm_mode = True

class AnalysisHistoryDetail(BaseModel):
    id: int
    # user_github_id: Optional[str] = None # Decide if this should be exposed in the API
    repository_url: str
    timestamp: datetime.datetime # Explicitly use datetime.datetime
    updated_at: datetime.datetime # Explicitly use datetime.datetime
    parameters_used: Dict[str, Any]
    summary_content: Optional[str] = None
    status: AnalysisStatus
    error_message: Optional[str] = None

    # Pydantic V2 configuration for ORM mode
    model_config = {
        "from_attributes": True
    }
    # For Pydantic V1, you would use:
    # class Config:
    #     orm_mode = True