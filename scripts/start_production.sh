#!/usr/bin/env bash
set -e

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Start background Celery worker with solo pool (single process, low memory footprint for 512MB RAM)
echo "Starting Celery worker in background (pool=solo)..."
celery -A app.workers.celery_app worker --loglevel=info --pool=solo --queues=celery,backtest,embedding &
WORKER_PID=$!

cleanup() {
    echo "Stopping Celery worker (PID $WORKER_PID)..."
    kill -TERM "$WORKER_PID" 2>/dev/null || true
    wait "$WORKER_PID" 2>/dev/null || true
}
trap cleanup EXIT SIGINT SIGTERM

# Start FastAPI web server on the assigned Render PORT
echo "Starting Uvicorn web server on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
