import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="ping_task")
def ping_task(message: str = "ping"):
    logger.info("Executing ping_task", message=message)
    return {"status": "pong", "message": message}
