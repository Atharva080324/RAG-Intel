from redis import asyncio as aioredis
from app.core.config import settings

redis = aioredis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)

async def get_cache(key: str):
    return await redis.get(key)

async def set_cache(key: str, value: str, expire: int = 300):
    await redis.set(key, value, ex=expire)

async def delete_cache(key: str):
    await redis.delete(key)
