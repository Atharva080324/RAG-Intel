#!/usr/bin/env sh
set -e

echo "==> Running database migrations (alembic upgrade head)"
alembic upgrade head

# Use $PORT if set (Railway / Render), otherwise default to 7860 (HF Spaces).
PORT="${PORT:-7860}"
export PORT

# When a dedicated worker service exists (default on Railway/Render), only run
# the API here. Supervisord (uvicorn + Celery in one container) is used only
# when RUN_WORKER=1 (e.g. a single Hugging Face Space instance).
if [ "${RUN_WORKER:-0}" = "1" ]; then
  echo "==> Starting FastAPI (port $PORT) and Celery worker via supervisor"
  exec supervisord -c supervisord.conf
fi

echo "==> Starting FastAPI on port $PORT"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"