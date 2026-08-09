from app.services.cache_service import redis

RATE_LIMIT = 20
WINDOW_SECONDS = 60

async def increment_rate_limit(key: str) -> int:
    count = await redis.incr(key)
    await redis.expire(key, WINDOW_SECONDS)
    return count
