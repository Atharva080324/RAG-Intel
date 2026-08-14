from pydantic import AnyUrl, Field, model_validator
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
    # Public base URL of the Streamlit frontend; used for OAuth redirect targets.
    streamlit_frontend_url: str = "http://127.0.0.1:8501"
    # Comma-separated list of allowed CORS origins, e.g. "https://app.onrender.com".
    cors_origins: str = ""
    # Cloudflare R2 object storage for uploaded documents (optional; the default
    # "auto"/"postgres" backend stores files as bytea blobs in PostgreSQL).
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket_name: str | None = None
    # Storage backend: "auto" (R2 if configured, else Postgres), "r2", "postgres", or "local".
    storage_backend: str = "auto"
    retrieval_top_k: int = Field(8, ge=1, le=20)
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    reranker_candidate_limit: int = Field(32, ge=4, le=100)
    min_grounding_score: float = Field(0.15, ge=0.0, le=1.0)

    @property
    def r2_configured(self) -> bool:
        """Whether R2 object storage is fully configured."""
        return bool(
            self.r2_account_id
            and self.r2_access_key_id
            and self.r2_secret_access_key
            and self.r2_bucket_name
        )

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse the comma-separated CORS origin string into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def redirect_base_url(self) -> str:
        """Trim any trailing slash from the Streamlit frontend base URL."""
        return self.streamlit_frontend_url.rstrip("/")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_production_settings(self):
        """Fail fast for unsafe or incomplete production configuration.

        Development keeps its flexible local setup, while a deployed service
        must not start with placeholder secrets or a partially configured
        provider integration.
        """
        if self.environment.lower() != "production":
            return self

        placeholders = ("", "change-me")
        if len(self.secret_key) < 32 or self.secret_key.lower() in placeholders or self.secret_key.startswith("<"):
            raise ValueError("SECRET_KEY must be a strong value of at least 32 characters in production")

        for key, value in {
            "HF_TOKEN": self.hf_token,
            "GROQ_API_KEY": self.groq_api_key,
        }.items():
            if not value or value.startswith("<"):
                raise ValueError(f"{key} must be configured in production")

        if (self.storage_backend or "").strip().lower() == "r2" and not self.r2_configured:
            raise ValueError(
                "R2 storage is selected (STORAGE_BACKEND=r2) but R2 credentials are incomplete. "
                "Set all R2_ACCOUNT_ID/R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY/R2_BUCKET_NAME, "
                "or switch STORAGE_BACKEND back to auto/postgres (PostgreSQL bytea blobs, no billing)."
            )

        google_values = (self.google_client_id, self.google_client_secret)
        if any(google_values) and not all(google_values):
            raise ValueError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be configured together")
        if all(google_values) and not self.google_redirect_uri.startswith("https://"):
            raise ValueError("GOOGLE_REDIRECT_URI must use HTTPS in production")

        return self

settings = Settings()
