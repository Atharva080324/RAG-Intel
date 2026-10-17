"""Rate-limiting helpers backed by Redis.

Two kinds of caps are enforced:
- Per-IP burst limiter (unchanged): 20 POST requests per 60 s window, applied by
  ``RateLimitMiddleware``.
- Per-user daily caps on uploads and questions: ``check_daily_cap`` increments a
  Redis counter keyed by ``(user_id, action)`` with a 24-hour TTL and raises
  ``TooManyRequestsError`` when the configured limit is exceeded.  A limit of 0
  means disabled.
"""
from app.services.cache_service import redis

RATE_LIMIT = 20
WINDOW_SECONDS = 60

# 24-hour window in seconds
DAILY_WINDOW_SECONDS = 86_400


class TooManyRequestsError(Exception):
    """Raised when a per-user daily cap is exceeded."""

    def __init__(self, message: str, retry_after: int = DAILY_WINDOW_SECONDS) -> None:
        super().__init__(message)
        self.retry_after = retry_after


async def increment_rate_limit(key: str) -> int:
    try:
        count = await redis.incr(key)
        await redis.expire(key, WINDOW_SECONDS)
        return count
    except Exception:
        # If Redis is temporarily unreachable (e.g. during cold start, failover, or offline test), fail open
        return 1


async def check_daily_cap(user_id: int, action: str, limit: int) -> None:
    """Increment the daily counter for *action* and raise if the cap is reached.

    Args:
        user_id: The authenticated user's database id.
        action:  A short label such as ``"upload"`` or ``"question"``.
        limit:   Maximum allowed per day.  0 means no cap.

    Raises:
        TooManyRequestsError: when the counter already equals *limit*.
    """
    if limit <= 0:
        return
    key = f"daily:{action}:{user_id}"
    count = await redis.incr(key)
    if count == 1:
        # First increment today — start the 24-hour window.
        await redis.expire(key, DAILY_WINDOW_SECONDS)
    if count > limit:
        ttl = await redis.ttl(key)
        retry_after = ttl if ttl and ttl > 0 else DAILY_WINDOW_SECONDS
        raise TooManyRequestsError(
            f"Daily {action} limit of {limit} reached. "
            f"Resets in {retry_after // 3600}h {(retry_after % 3600) // 60}m.",
            retry_after=retry_after,
        )
