import logging
import os
from redis import Redis
from rq import Worker, Connection

from repo_processor_service.core.config import settings

logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

listen_queues = [settings.REPO_PROCESSING_QUEUE]

if __name__ == '__main__':
    # Ensure CLONE_TEMP_DIR_BASE exists
    os.makedirs(settings.CLONE_TEMP_DIR_BASE, exist_ok=True)
    logger.info(f"Repo Processor Service: Temporary clone directory base is {settings.CLONE_TEMP_DIR_BASE}")

    try:
        redis_conn = Redis.from_url(str(settings.REDIS_URL))
        redis_conn.ping() # Test connection
        logger.info(f"Repo Processor Service: Connected to Redis at {settings.REDIS_URL}")
    except Exception as e:
        logger.critical(f"Repo Processor Service: Could not connect to Redis. Worker cannot start. Error: {e}", exc_info=True)
        exit(1)

    with Connection(redis_conn):
        worker = Worker(listen_queues)
        logger.info(f"Repo Processor Service: Worker starting, listening on queues: {', '.join(listen_queues)}")
        worker.work(with_scheduler=False) # Set with_scheduler=True if you use RQ Scheduler