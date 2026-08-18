import app.workers.backtest_task  # noqa: F401
from app.workers.celery_app import celery_app
from app.workers.tasks import ping_task


def test_ping_task():
    result = ping_task("test_ping")
    assert result == {"status": "pong", "message": "test_ping"}


def test_backtest_task_registered():
    assert "tasks.run_backtest" in celery_app.tasks
