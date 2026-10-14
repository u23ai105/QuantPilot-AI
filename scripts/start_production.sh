#!/usr/bin/env bash
set -e

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Export RUN_WORKER so FastAPI lifespan starts the Celery worker in an embedded thread.
# This keeps the entire system in a single Python process (~210MB RAM), safely under
# Render's 512MB free tier memory limit with zero risk of OOM kills.
export RUN_WORKER=true

# Start FastAPI web server on the assigned Render PORT
echo "Starting Uvicorn web server on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"


