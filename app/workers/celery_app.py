import platform

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "rag_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

# Celery's default ``prefork`` pool relies on POSIX shared-memory primitives
# (billiard / multiprocessing semaphores) that fail with
# ``PermissionError: [WinError 5] Access is denied`` on Windows.  The
# ``solo`` pool runs tasks in the main process and avoids the issue entirely.
# On Linux (Railway, Docker) the default ``prefork`` pool is left untouched.
if platform.system() == "Windows":
    celery_app.conf.worker_pool = "solo"
    celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_default_queue = "celery"
celery_app.conf.task_routes = {
    "app.workers.tasks.*": {"queue": "celery"}
}
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.task_track_started = True
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.broker_connection_retry_on_startup = True

# Import task modules after creating the app so decorators register tasks for
# both Celery workers and processes that enqueue jobs.
import app.workers.tasks  # noqa: E402,F401
