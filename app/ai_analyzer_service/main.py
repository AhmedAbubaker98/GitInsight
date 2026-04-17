import logging
from redis import Redis
from rq import Worker
from shared_config import shared_settings

from ai_analyzer_service.core.config import settings

logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

listen_queues = [shared_settings.AI_ANALYSIS_QUEUE]

if __name__ == '__main__':
    try:
        redis_conn = Redis.from_url(str(settings.REDIS_URL))
        redis_conn.ping()
        logger.info(f"AI Analyzer Service: Connected to Redis at {settings.REDIS_URL}")
    except Exception as e:
        logger.critical(f"AI Analyzer Service: Could not connect to Redis. Worker cannot start. Error: {e}", exc_info=True)
        exit(1)
    
    logger.info(
        "AI Analyzer Service: Using provider '%s' with model '%s'.",
        settings.AI_PROVIDER,
        settings.AI_MODEL_NAME,
    )

    # Create worker without deprecated Connection context manager
    worker = Worker(listen_queues, connection=redis_conn)
    logger.info(f"AI Analyzer Service: Worker starting, listening on queues: {', '.join(listen_queues)}")
    worker.work(with_scheduler=False)