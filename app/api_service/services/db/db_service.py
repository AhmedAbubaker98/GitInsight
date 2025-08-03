import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from sqlalchemy import desc, update
from typing import List, Optional, Dict, Any, AsyncGenerator
from datetime import datetime, timezone

from api_service.services.db.db_models import Base, AnalysisHistory, AnalysisStatus
from api_service.core.config import settings

logger = logging.getLogger(__name__)

engine = None
AsyncSessionLocal = None

if settings.MY_DATABASE_URL:
    try:
        engine = create_async_engine(
            str(settings.MY_DATABASE_URL), # Ensure it's a string
            echo=(settings.LOG_LEVEL.upper() == "DEBUG"),
        )
        AsyncSessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
            class_=AsyncSession
        )
        logger.info("API Service: Database engine configured successfully.")
    except Exception as e:
        logger.critical(f"API Service: Error configuring database engine: {e}", exc_info=True)
        engine = None
        AsyncSessionLocal = None
else:
    logger.warning("API Service: MY_DATABASE_URL not set. Database features will be disabled.")


async def init_db():
    if not engine:
        logger.warning("API Service: Database engine not initialized. Skipping DB table creation.")
        return
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("API Service: Database tables created/verified successfully.")
    except Exception as e:
        logger.error(f"API Service: Error during database initialization (init_db): {e}", exc_info=True)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    if not AsyncSessionLocal:
        logger.warning("API Service: Attempted to get DB session, but AsyncSessionLocal is not configured.")
        yield None # Must yield something for FastAPI dependency, route must handle None
        return

    session: AsyncSession = AsyncSessionLocal()
    try:
        yield session
    except Exception as e:
        logger.error(f"API Service: Error in DB session: {e}", exc_info=True)
        await session.rollback()
        raise
    finally:
        await session.close()

async def create_analysis_history(
    db: AsyncSession,
    repository_url: str,
    parameters_used: Dict[str, Any],
    user_github_id: Optional[str] = None,
) -> Optional[AnalysisHistory]:
    if not db:
        logger.warning(f"DB session not available, skipping history creation for repo: {repository_url}.")
        return None

    new_analysis = AnalysisHistory(
        user_github_id=user_github_id,
        repository_url=repository_url,
        parameters_used=parameters_used,
        status=AnalysisStatus.QUEUED,
        timestamp=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    try:
        db.add(new_analysis)
        await db.commit()
        await db.refresh(new_analysis)
        logger.info(f"Created analysis history: ID '{new_analysis.id}', Repo '{repository_url}', Status '{new_analysis.status}'")
        return new_analysis
    except Exception as e:
        logger.error(f"Error creating analysis history for repo '{repository_url}': {e}", exc_info=True)
        await db.rollback()
        return None

async def update_analysis_status(
    db: AsyncSession,
    analysis_id: int,
    status: AnalysisStatus,
    summary_content: Optional[str] = None,
    error_message: Optional[str] = None,
) -> Optional[AnalysisHistory]:
    if not db:
        logger.warning(f"DB session not available, skipping status update for analysis_id: {analysis_id}.")
        return None
    try:
        stmt = (
            update(AnalysisHistory)
            .where(AnalysisHistory.id == analysis_id)
            .values(
                status=status,
                summary_content=summary_content if status == AnalysisStatus.COMPLETED else AnalysisHistory.summary_content,
                error_message=error_message if status == AnalysisStatus.FAILED else None, # Clear error if not failed
                updated_at=datetime.now(timezone.utc)
            )
            .returning(AnalysisHistory) # To get the updated row
        )
        result = await db.execute(stmt)
        await db.commit()
        updated_analysis = result.scalar_one_or_none()

        if updated_analysis:
            logger.info(f"Updated analysis ID {analysis_id} to status {status}.")
        else:
            logger.warning(f"Attempted to update analysis ID {analysis_id}, but no record found.")
        return updated_analysis
    except Exception as e:
        logger.error(f"Error updating analysis ID {analysis_id} status: {e}", exc_info=True)
        await db.rollback()
        return None

async def get_analysis_by_id_for_user(
    db: AsyncSession,
    analysis_id: int,
    user_github_id: Optional[str] = None # User ID for ownership check if logged in
) -> Optional[AnalysisHistory]:
    if not db:
        return None
    stmt = select(AnalysisHistory).where(AnalysisHistory.id == analysis_id)
    # If user_github_id is provided (logged-in user), ensure they own the record.
    # Guests can only poll for analyses they initiated if we store a session-based guest_id,
    # or if analysis_id is considered "public knowledge" for a short time.
    # For simplicity, if user_github_id is None (guest), we don't restrict by user.
    # This means a guest would need to know the analysis_id.
    if user_github_id:
         stmt = stmt.where(AnalysisHistory.user_github_id == user_github_id)
    
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_analysis_history_for_user(db: AsyncSession, user_github_id: str) -> List[AnalysisHistory]:
    if not db:
        return []
    stmt = (
        select(AnalysisHistory)
        .where(AnalysisHistory.user_github_id == user_github_id)
        .order_by(desc(AnalysisHistory.timestamp))
        .limit(50)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
