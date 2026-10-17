"""Global pytest fixtures and environment setup.

Ensures settings loads dummy values in test runs without requiring a live .env file.
"""
import os
import pytest

# Set default test environment variables before any application imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/testdb")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-chars-long-abcdef")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("DEMO_USER_EMAIL", "demo@test.internal")
