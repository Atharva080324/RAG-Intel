"""Shared object storage for uploaded documents.

Uploaded files must be visible to *both* the FastAPI service that accepts them
and the Celery worker that ingests them. Render services have isolated,
ephemeral filesystems, so a file written to local disk on the API service is
never visible to the worker.

The default backend stores the raw bytes as `bytea` blobs in the shared
PostgreSQL database: the API and worker already connect to the same database,
so no external object store, persistent disk, or billing setup is required.
Cloudflare R2 can be enabled later as an optional S3-compatible upgrade without
changing the upload or worker code paths.
"""

from pathlib import Path
from typing import Protocol

from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import async_session, worker_session
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.stored_file import StoredFile


class ObjectStorageError(RuntimeError):
    """Raised when an object storage operation cannot be completed."""


class ObjectStorage(Protocol):
    async def upload(self, key: str, content: bytes) -> None: ...
    async def download(self, key: str, session: AsyncSession | None = None) -> bytes: ...
    async def delete(self, key: str, session: AsyncSession | None = None) -> None: ...


class PostgresStorage:
    """Default backend: store uploaded bytes as bytea blobs in PostgreSQL.

    Both the API (which accepts the upload) and the separately-deployed worker
    (which ingests it) connect to the same database, so this provides shared
    durable storage for free, with no billing or extra service required.
    """

    async def upload(self, key: str, content: bytes) -> None:
        async with worker_session() as db:
            existing = (
                await db.execute(select(StoredFile).where(StoredFile.key == key))
            ).scalar_one_or_none()
            if existing is not None:
                existing.content = content
            else:
                db.add(StoredFile(key=key, content=content))
            await db.commit()

    async def download(self, key: str, session: AsyncSession | None = None) -> bytes:
        if session is not None:
            row = (
                await session.execute(select(StoredFile).where(StoredFile.key == key))
            ).scalar_one_or_none()
            if row is None:
                raise ObjectStorageError(f"Stored object not found: {key}")
            return row.content

        async with worker_session() as db:
            row = (
                await db.execute(select(StoredFile).where(StoredFile.key == key))
            ).scalar_one_or_none()
            if row is None:
                raise ObjectStorageError(f"Stored object not found: {key}")
            return row.content

    async def delete(self, key: str, session: AsyncSession | None = None) -> None:
        if session is not None:
            await session.execute(delete(StoredFile).where(StoredFile.key == key))
            await session.commit()
            return

        async with worker_session() as db:
            await db.execute(delete(StoredFile).where(StoredFile.key == key))
            await db.commit()


class R2Storage:
    """Optional Cloudflare R2 (S3-compatible) backend used when configured."""

    def __init__(self) -> None:
        if not settings.r2_configured:
            raise ObjectStorageError(
                "R2 is not configured. Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, "
                "R2_SECRET_ACCESS_KEY, and R2_BUCKET_NAME."
            )
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # pragma: no cover - defensive
            raise ObjectStorageError("boto3 is required for R2 storage") from exc

        endpoint_url = f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )
        self._bucket = settings.r2_bucket_name

    async def upload(self, key: str, content: bytes) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=content)

    async def download(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()

    async def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)


class LocalStorage:
    """Development-only fallback writing to `uploads/` on local disk."""

    def __init__(self, root: str = "uploads") -> None:
        self._root = Path(root)

    def _path(self, key: str) -> Path:
        root = self._root.resolve()
        path = (root / key).resolve()
        if path != root and root not in path.parents:
            raise ObjectStorageError("Storage key escapes the uploads directory")
        return path

    async def upload(self, key: str, content: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    async def download(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    async def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


def document_key(user_id: int, filename: str, unique_id: str) -> str:
    """Build a namespaced storage key for a submitted document.

    The key doubles as `Document.source_path` so the worker can fetch the exact
    same object regardless of which storage backend is active.
    """
    suffix = Path(filename or "").suffix.lower()
    return f"documents/{user_id}/{unique_id}{suffix}"


_storage: ObjectStorage | None = None


def get_storage() -> ObjectStorage:
    """Return the process-wide storage backend.

    `STORAGE_BACKEND` may be "auto" (default), "r2", "postgres", or "local".

    - auto: use R2 when configured, otherwise PostgreSQL bytea blobs.
    - r2: require Cloudflare R2.
    - postgres: always use PostgreSQL bytea blobs (zero-billing default).
    - local: write to the local uploads/ directory (development only).
    """
    global _storage
    if _storage is not None:
        return _storage

    backend = (settings.storage_backend or "auto").strip().lower()
    if backend == "r2" or (backend == "auto" and settings.r2_configured):
        _storage = R2Storage()
    elif backend == "local":
        _storage = LocalStorage()
    else:
        _storage = PostgresStorage()
    return _storage
