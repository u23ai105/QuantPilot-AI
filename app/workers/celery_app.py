import ssl

from celery import Celery

from app.core.config import settings

broker_url = settings.celery_broker_url or settings.redis_url
backend_url = settings.celery_result_backend or settings.redis_url

# If broker is localhost but redis_url is a remote URL, prioritize redis_url
if "localhost" in broker_url and "localhost" not in settings.redis_url:
    broker_url = settings.redis_url
if "localhost" in backend_url and "localhost" not in settings.redis_url:
    backend_url = settings.redis_url

celery_app = Celery(
    "worker",
    broker=broker_url,
    backend=backend_url,
    include=[
        "app.workers.tasks",
        "app.workers.backtest_task",
        "app.workers.embedding_task",
    ],
)

conf_updates = {
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    "task_routes": {
        "tasks.run_backtest": {"queue": "backtest"},
        "app.workers.embedding_task.embed_document": {"queue": "embedding"},
    },
    # Task events, which is what Flower reads (see the `flower` service in docker-compose.yml).
    # Without these the dashboard still lists workers and queues but shows no tasks at all, since
    # Celery emits nothing by default. `worker_send_task_events` covers started/succeeded/failed;
    # `task_send_sent_event` is emitted by the *publisher*, so a task that is queued but never
    # picked up — a worker started without `--queues=backtest`, say — is visible as sent-but-not-
    # received instead of vanishing.
    "worker_send_task_events": True,
    "task_send_sent_event": True,
}

if broker_url.startswith("rediss://") or backend_url.startswith("rediss://"):
    ssl_opts = {"ssl_cert_reqs": ssl.CERT_NONE}
    conf_updates["broker_use_ssl"] = ssl_opts
    conf_updates["redis_backend_use_ssl"] = ssl_opts

celery_app.conf.update(**conf_updates)
