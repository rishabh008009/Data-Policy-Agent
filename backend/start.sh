#!/bin/sh
echo "Running database migrations..."
alembic upgrade head || echo "Migration warning (may already be up to date)"
echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
