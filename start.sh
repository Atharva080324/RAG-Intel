#!/usr/bin/env sh
set -e

echo "==> Running database migrations (alembic upgrade head)"
alembic upgrade head

# Use $PORT if set (Railway / Render), otherwise default to 7860 (HF Spaces).
PORT="${PORT:-7860}"
echo "==> Starting FastAPI (port $PORT) and Celery worker via supervisor"
export PORT
exec supervisord -c supervisord.conf