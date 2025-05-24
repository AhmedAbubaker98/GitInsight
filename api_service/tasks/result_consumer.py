import logging
from sqlalchemy.ext.asyncio import AsyncSession
from api_service.services.db.db_service import update_analysis_status, AsyncSessionLocal
from api_service.services.db.db_models import AnalysisStatus

logger = logging.getLogger(__name__)

async def process_analysis_result(payload: dict):
    """
    Processes results/status updates from the gitinsight_results queue.
    Payload can be:
    - {'analysis_id': int, 'status': 'processing_repo' | 'processing_ai'}
    - {'analysis_id': int, 'status': 'completed', 'summary_content': str}
    - {'analysis_id': int, 'status': 'failed', 'error_message': str}
    """
    analysis_id = payload.get("analysis_id")
    status_str = payload.get("status")
    summary_content = payload.get("summary_content")
    error_message = payload.get("error_message")

    if not analysis_id or not status_str:
        logger.error(f"Invalid payload received in result_consumer: {payload}")
        return

    try:
        status = AnalysisStatus(status_str) # Validate status string
    except ValueError:
        logger.error(f"Invalid status '{status_str}' in payload for analysis_id {analysis_id}")
        return

    logger.info(f"Result consumer: Processing analysis_id {analysis_id}, status {status}")

    if not AsyncSessionLocal:
        logger.error("Result consumer: Database not configured. Cannot process result.")
        # This task would ideally be re-queued or sent to a dead-letter queue.
        # For RQ, if this function raises an exception, RQ might retry it.
        raise ConnectionError("Database not configured for result consumer.")

    async with AsyncSessionLocal() as db_session:
        try:
            await update_analysis_status(
                db=db_session,
                analysis_id=analysis_id,
                status=status,
                summary_content=summary_content,
                error_message=error_message
            )
            logger.info(f"Result consumer: Successfully updated DB for analysis_id {analysis_id} with status {status}")
        except Exception as e:
            logger.error(f"Result consumer: DB update failed for analysis_id {analysis_id}: {e}", exc_info=True)
            # Re-raise to let RQ handle retry/failure
            raise