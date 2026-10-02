import app.workers.backtest_task  # noqa: F401
from app.workers.celery_app import celery_app
from app.workers.tasks import ping_task


def test_ping_task():
    result = ping_task("test_ping")
    assert result == {"status": "pong", "message": "test_ping"}


def test_backtest_task_registered():
    assert "tasks.run_backtest" in celery_app.tasks


def test_task_events_enabled_for_flower():
    """Flower shows an empty task list without these, and nothing else would catch that.

    `worker_send_task_events` is the worker side (started/succeeded/failed); `task_send_sent_event`
    is the publisher side, which is what makes a task queued to a queue nobody consumes visible.
    """
    assert celery_app.conf.worker_send_task_events is True
    assert celery_app.conf.task_send_sent_event is True
