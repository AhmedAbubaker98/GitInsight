import logging
from redis import Redis
from rq import Worker

from ai_analyzer_service.core.config import settings

logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

listen_queues = [settings.AI_ANALYSIS_QUEUE]

if __name__ == '__main__':
    try:
        redis_conn = Redis.from_url(str(settings.REDIS_URL))
        redis_conn.ping()
        logger.info(f"AI Analyzer Service: Connected to Redis at {settings.REDIS_URL}")
    except Exception as e:
        logger.critical(f"AI Analyzer Service: Could not connect to Redis. Worker cannot start. Error: {e}", exc_info=True)
        exit(1)
    
    if not settings.AI_ANALYZER_MY_GOOGLE_API_KEY:
        logger.critical("AI Analyzer Service: AI_ANALYZER_MY_GOOGLE_API_KEY is not set. AI tasks will fail.")
        exit(1)

    # Create worker without deprecated Connection context manager
    worker = Worker(listen_queues, connection=redis_conn)
    logger.info(f"AI Analyzer Service: Worker starting, listening on queues: {', '.join(listen_queues)}")
    worker.work(with_scheduler=False)