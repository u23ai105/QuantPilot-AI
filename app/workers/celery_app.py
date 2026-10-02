from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.tasks",
        "app.workers.backtest_task",
        "app.workers.embedding_task",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "tasks.run_backtest": {"queue": "backtest"},
        "app.workers.embedding_task.embed_document": {"queue": "embedding"},
    },
    # Task events, which is what Flower reads (see the `flower` service in docker-compose.yml).
    # Without these the dashboard still lists workers and queues but shows no tasks at all, since
    # Celery emits nothing by default. `worker_send_task_events` covers started/succeeded/failed;
    # `task_send_sent_event` is emitted by the *publisher*, so a task that is queued but never
    # picked up — a worker started without `--queues=backtest`, say — is visible as sent-but-not-
    # received instead of vanishing.
    worker_send_task_events=True,
    task_send_sent_event=True,
)
