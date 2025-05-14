from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func 
import datetime 

Base = declarative_base()

class AnalysisHistory(Base):
    __tablename__ = "analysis_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_github_id = Column(String, index=True, nullable=True)
    repository_url = Column(String, nullable=False)
    # CORRECTED LINE: Added parentheses to func.now()
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    parameters_used = Column(JSON, nullable=False)
    summary_content = Column(Text, nullable=True)
    # status = Column(String, default="completed", nullable=False)
    # error_message = Column(Text, nullable=True)

    def __repr__(self):
        return f"<AnalysisHistory(id={self.id}, user_github_id='{self.user_github_id}', repo='{self.repository_url}')>"