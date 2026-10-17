from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings


def _build_engine_url() -> tuple[str, dict]:
    """Process the async database URL for SQLAlchemy's async engine.

    SQLAlchemy's asyncpg dialect forwards URL query parameters as **string**
    keyword arguments to ``asyncpg.connect()``. Asyncpg expects
    ``statement_cache_size`` to be an integer, so we strip it from the URL
    and re-pass it via ``connect_args`` as a proper ``int``.

    This keeps the Neon-recommended ``statement_cache_size=0`` (disable
    statement caching to avoid pooler routing issues) while avoiding a
    ``TypeError`` crash on every real DB connection.
    """
    raw_url = str(settings.database_url)
    parsed = urlsplit(raw_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))

    connect_args: dict = {}
    if "statement_cache_size" in query:
        connect_args["statement_cache_size"] = int(query.pop("statement_cache_size"))

    clean_url = urlunsplit(parsed._replace(query=urlencode(query)))
    return clean_url, connect_args


_engine_url, _connect_args = _build_engine_url()
engine: AsyncEngine = create_async_engine(
    _engine_url,
    future=True,
    echo=False,
    connect_args=_connect_args,
    # Verify each pooled connection is alive before reuse. Neon (and other
    # managed Postgres) close idle connections after ~5 min; without this,
    # a request can receive a pooled-but-closed asyncpg connection and fail
    # with ``InterfaceError: connection is closed``.
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

from sqlalchemy.pool import NullPool

# NullPool sessionmaker for Celery worker processes where tasks invoke separate asyncio.run() calls.
# NullPool ensures asyncpg connections are never pooled across closed event loops.
worker_engine = create_async_engine(
    _engine_url,
    future=True,
    echo=False,
    connect_args=_connect_args,
    poolclass=NullPool,
)
worker_session = sessionmaker(worker_engine, class_=AsyncSession, expire_on_commit=False)

async def get_async_session() -> AsyncSession:
    async with async_session() as session:
        yield session
