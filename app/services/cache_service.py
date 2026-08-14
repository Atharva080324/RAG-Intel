from redis import asyncio as aioredis
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from app.core.config import settings


def _async_redis_url(url: str) -> str:
    """Adapt Celery's TLS URL spelling to the spelling redis-py accepts.

    Celery requires values such as ``CERT_REQUIRED`` in a ``rediss://`` URL,
    while redis-py's asyncio client accepts ``required``. Both clients share
    ``REDIS_URL``, so normalize only the URL used to construct this client.
    """
    parsed = urlsplit(url)
    ssl_values = {
        "CERT_REQUIRED": "required",
        "CERT_OPTIONAL": "optional",
        "CERT_NONE": "none",
    }
    query = [
        (key, ssl_values.get(value.upper(), value) if key == "ssl_cert_reqs" else value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    return urlunsplit(parsed._replace(query=urlencode(query)))


redis = aioredis.from_url(_async_redis_url(settings.redis_url), encoding="utf-8", decode_responses=True)

async def get_cache(key: str):
    return await redis.get(key)

async def set_cache(key: str, value: str, expire: int = 300):
    await redis.set(key, value, ex=expire)

async def delete_cache(key: str):
    await redis.delete(key)
