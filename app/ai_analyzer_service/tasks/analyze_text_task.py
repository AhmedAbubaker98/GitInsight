import logging
from redis import Redis
from rq import Queue

from ai_analyzer_service.core.config import settings
from ai_analyzer_service.services.analyzer import generate_summary, AISummaryError, AIInitializationError

logger = logging.getLogger(__name__)

async def analyze_text_task_async_wrapper(task_payload: dict):
    """
    Async wrapper to call the actual async AI generation logic.
    RQ itself doesn't directly support async task functions in all configurations easily,
    so this synchronous task function will run an async sub-process or use asyncio.run.
    However, for RQ, the task function itself must be synchronous.
    We will make generate_summary callable from a sync context.
    For this example, assuming the RQ worker can run asyncio.run or similar.
    A common pattern is to have a sync task that calls asyncio.run(async_logic()).
    Let's assume the worker setup handles asyncio if needed, or we use a sync wrapper.
    
    Actually, RQ tasks are typically synchronous. We'll need to run the async `generate_summary`
    using `asyncio.run()` or ensure the worker is async-capable.
    If worker is standard sync RQ worker:
    """
    import asyncio

    analysis_id = task_payload.get("analysis_id")
    extracted_text = task_payload.get("extracted_text")
    analysis_params = task_payload.get("analysis_parameters")
    result_queue_name = task_payload.get("result_queue_name")

    if not all([analysis_id, extracted_text, analysis_params, result_queue_name]):
        logger.error(f"AI Analyzer: Invalid task payload: {task_payload}")
        return 

    logger.info(f"AI Analyzer: Starting AI analysis for analysis_id: {analysis_id}")

    redis_conn = None
    try:
        redis_conn = Redis.from_url(str(settings.REDIS_URL))
        result_q = Queue(result_queue_name, connection=redis_conn)

        # Notify API service that AI processing has started
        result_q.enqueue(
            "api_service.tasks.result_consumer.process_analysis_result",
            {"analysis_id": analysis_id, "status": "PROCESSING"}
        )
        logger.info(f"AI Analyzer: Sent 'PROCESSING' status for analysis_id: {analysis_id}")

        summary_content = await generate_summary(
            text=extracted_text,
            lang=analysis_params.get("lang", "en"),
            size=analysis_params.get("size", "medium"),
            technicality=analysis_params.get("technicality", "technical")
        )
        
        logger.info(f"AI Analyzer: Successfully generated summary for analysis_id: {analysis_id}")
        result_q.enqueue(
            "api_service.tasks.result_consumer.process_analysis_result",
            {"analysis_id": analysis_id, "status": "COMPLETED", "summary_content": summary_content}
        )

    except (AISummaryError, ValueError, AIInitializationError) as e: # Known, somewhat expected errors
        logger.error(f"AI Analyzer: Error during AI analysis for analysis_id {analysis_id}: {e}", exc_info=True)
        if redis_conn and result_queue_name:
            result_q = Queue(result_queue_name, connection=redis_conn)
            result_q.enqueue(
                "api_service.tasks.result_consumer.process_analysis_result",
                {"analysis_id": analysis_id, "status": "FAILED", "error_message": str(e)}
            )
    except Exception as e:
        logger.critical(f"AI Analyzer: Unexpected critical error for analysis_id {analysis_id}: {e}", exc_info=True)
        if redis_conn and result_queue_name:
            result_q = Queue(result_queue_name, connection=redis_conn)
            result_q.enqueue(
                "api_service.tasks.result_consumer.process_analysis_result",
                {"analysis_id": analysis_id, "status": "FAILED", "error_message": f"Unexpected error in AI analysis: {type(e).__name__}"}
            )
        raise # Re-raise for RQ to mark as failed
    finally:
        if redis_conn:
            redis_conn.close()

def analyze_text_task(task_payload: dict):
    """
    Synchronous RQ task entry point for text analysis.

    This function serves as a wrapper that allows asynchronous text analysis code to be
    executed within Redis Queue (RQ) workers, which operate in a synchronous context.
    It uses asyncio.run() to bridge the sync/async gap.

    Args:
        task_payload (dict): Dictionary containing task parameters including:
            - analysis_id: Unique identifier for the analysis task
            - Additional parameters required for text analysis

    Raises:
        Exception: Re-raises any exceptions that occur during task execution to
                  ensure RQ properly marks the job as failed. Logs critical errors
                  before re-raising.

    Note:
        This is a common pattern for running async code from sync RQ tasks in Python 3.7+.
        Robust production systems should implement dead-letter queues or more
        sophisticated error reporting mechanisms for handling connection errors.
    """
    import asyncio
    # This is a common way to run async code from a sync RQ task
    # Python 3.7+
    try:
        asyncio.run(analyze_text_task_async_wrapper(task_payload))
    except Exception as e:
        # Log again here if asyncio.run itself fails or if error wasn't caught inside
        logger.critical(f"AI Analyzer: Top-level task failure for {task_payload.get('analysis_id')}: {e}", exc_info=True)
        # If this was a connection error to Redis *before* sending results, the task will fail without DB update.
        # Robust systems need dead-letter queues or more sophisticated error reporting.
        raise # Ensure RQ marks the job as failed