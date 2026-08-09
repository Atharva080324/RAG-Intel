from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: AnyUrl
    redis_url: str
    secret_key: str
    access_token_expire_minutes: int
    algorithm: str = "HS256"
    pgvector_extension: str = "vector"
    max_upload_size_bytes: int = Field(10 * 1024 * 1024, ge=1, le=100 * 1024 * 1024)
    allowed_upload_extensions: str = "pdf,txt,md"
    environment: str = "development"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = Field(384, ge=1)
    embedding_batch_size: int = Field(32, ge=1, le=128)
    hf_token: str | None = None
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://127.0.0.1:8000/auth/google/callback"
    retrieval_top_k: int = Field(8, ge=1, le=20)
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    reranker_candidate_limit: int = Field(32, ge=4, le=100)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
