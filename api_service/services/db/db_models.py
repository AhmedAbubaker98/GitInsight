from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, Enum as SAEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import datetime
import enum

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
        return f""