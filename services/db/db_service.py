import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from sqlalchemy import desc
from typing import List, Optional, Dict, Any, AsyncGenerator
from datetime import datetime, timezone

from services.db.db_models import Base, AnalysisHistory
from core.config import settings # Import centralized settings

logger = logging.getLogger(__name__)

engine = None
AsyncSessionLocal = None

logger.info(f"Database URL from settings: {'*****' if settings.MY_DATABASE_URL else 'Not set'}") # Avoid logging full URL with creds

if settings.MY_DATABASE_URL:
    try:
        engine = create_async_engine(
            settings.MY_DATABASE_URL,
            echo=settings.LOG_LEVEL.upper() == "DEBUG", # Log SQL queries only if LOG_LEVEL is DEBUG
        )
        AsyncSessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
            class_=AsyncSession
        )
        logger.info("Database engine configured successfully.")
    except Exception as e:
        logger.critical(f"Error configuring database engine: {e}", exc_info=True)
        # Effectively disable DB features if config fails by not setting AsyncSessionLocal
        engine = None 
        AsyncSessionLocal = None
else:
    logger.warning("MY_DATABASE_URL environment variable not set. Database features (history) will be disabled.")


async def init_db():
    if not engine:
        logger.warning("Database engine not initialized. Skipping DB table creation.")
        return
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created/verified successfully.")
    except Exception as e:
        logger.error(f"Error during database initialization (init_db): {e}", exc_info=True)
        # Consider if this should prevent app startup or just disable DB features

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides an asynchronous database session generator.

    Yields:
        AsyncSession: An instance of the database session.
    """
    if not AsyncSessionLocal:
        logger.warning("Attempted to get DB session, but AsyncSessionLocal is not configured (MY_DATABASE_URL likely not set or invalid).")
        # This will cause FastAPI's dependency injection to fail if the route expects a session.
        # Routes should handle the `db` argument being None or raise HTTPException if DB is required.
        # For a generator dependency, it must yield. If it doesn't yield, FastAPI raises an error.
        # To indicate no session is available, it's better that routes check settings.MY_DATABASE_URL
        # or handle the `db` parameter being None.
        # If we must yield something, it would be None, but that's not an AsyncSession.
        # Let's rely on routes checking `settings.MY_DATABASE_URL` or handling `db` being None.
        # The type hint `Optional[AsyncSession]` for `db` in routes is key.
        # The current structure in main.py seems to handle this.
        # If this function is called and AsyncSessionLocal is None, the `async with AsyncSessionLocal() as session:`
        # line below will raise an error.
        # The routes using this dependency should check if settings.MY_DATABASE_URL is set.
        return # This will make FastAPI treat it as if no value was provided.

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Error in DB session: {e}", exc_info=True)
            await session.rollback() # Rollback on error within session usage
            raise # Re-raise the exception to be handled by the caller or FastAPI error handlers
        finally:
            await session.close()


async def log_analysis_request(
    db: AsyncSession,
    user_github_id: Optional[str],
    repository_url: str,
    parameters_used: Dict[str, Any],
    summary_content: Optional[str]
) -> Optional[AnalysisHistory]:
    if not db: # Check if session is None (e.g., if DB not configured)
        logger.warning("DB session not available, skipping history log for repo: {repository_url}.")
        return None
    # No need to check settings.MY_DATABASE_URL here, as `db` being available implies it was.

    new_log = AnalysisHistory(
        user_github_id=user_github_id,
        repository_url=repository_url,
        parameters_used=parameters_used,
        summary_content=summary_content,
        timestamp=datetime.now(timezone.utc) # Ensure timezone aware datetime
    )
    try:
        db.add(new_log)
        await db.commit()
        await db.refresh(new_log)
        logger.info(f"Logged analysis to history: User '{user_github_id}', Repo '{repository_url}', Log ID '{new_log.id}'")
        return new_log
    except Exception as e:
        logger.error(f"Error logging analysis request to database for repo '{repository_url}': {e}", exc_info=True)
        await db.rollback()
        return None

async def get_analysis_history(db: AsyncSession, user_github_id: str) -> List[AnalysisHistory]:
    if not db:
        logger.warning(f"DB session not available, skipping history retrieval for user: {user_github_id}.")
        return []
    try:
        stmt = (
            select(AnalysisHistory)
            .where(AnalysisHistory.user_github_id == user_github_id)
            .order_by(AnalysisHistory.timestamp.desc())
            .limit(50) # Keep reasonable limit
        )
        result = await db.execute(stmt)
        history_items = result.scalars().all()
        logger.debug(f"Retrieved {len(history_items)} history items for user '{user_github_id}'")
        return history_items
    except Exception as e:
        logger.error(f"Error retrieving analysis history from database for user '{user_github_id}': {e}", exc_info=True)
        return []

async def get_analysis_by_id(db: AsyncSession, history_id: int, user_github_id: str) -> Optional[AnalysisHistory]:
    if not db:
        logger.warning(f"DB session not available, skipping retrieval of history item ID {history_id} for user: {user_github_id}.")
        return None
    try:
        stmt = select(AnalysisHistory).where(
            AnalysisHistory.id == history_id,
            AnalysisHistory.user_github_id == user_github_id # Ensure user owns the record
        )
        result = await db.execute(stmt)
        history_item = result.scalars().first()
        if history_item:
            logger.debug(f"Retrieved history item ID {history_id} for user '{user_github_id}'")
        else:
            logger.debug(f"History item ID {history_id} not found or access denied for user '{user_github_id}'")
        return history_item
    except Exception as e:
        logger.error(f"Error retrieving specific analysis history item (ID: {history_id}) for user '{user_github_id}': {e}", exc_info=True)
        return None