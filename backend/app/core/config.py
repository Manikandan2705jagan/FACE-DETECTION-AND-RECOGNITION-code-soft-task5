"""Application-wide configuration loaded from the environment.

Every setting has a safe, development-friendly default so the app boots even
without a fully populated ``.env``. Production deployments MUST override secrets.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # ---- General -----------------------------------------------------------
    app_name: str = "JARVAS"
    env: str = Field(default="development", alias="JARVAS_ENV")
    log_level: str = Field(default="INFO", alias="JARVAS_LOG_LEVEL")
    api_v1_prefix: str = "/api/v1"

    # ---- Database ----------------------------------------------------------
    database_url: str = Field(default="", alias="DATABASE_URL")
    postgres_user: str = "jarvas"
    postgres_password: str = "jarvas"
    postgres_db: str = "jarvas"

    # ---- Redis -------------------------------------------------------------
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")
    celery_broker_url: str = Field(default="redis://redis:6379/1", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://redis:6379/2", alias="CELERY_RESULT_BACKEND")

    # ---- Auth --------------------------------------------------------------
    jwt_secret: str = Field(
        default="dev-insecure-secret-change-me-please-0123456789abcdef",
        alias="JWT_SECRET",
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    oidc_issuer: str = Field(default="", alias="OIDC_ISSUER")
    oidc_client_id: str = Field(default="", alias="OIDC_CLIENT_ID")
    oidc_client_secret: str = Field(default="", alias="OIDC_CLIENT_SECRET")
    oidc_redirect_uri: str = Field(
        default="http://localhost:3000/api/auth/callback", alias="OIDC_REDIRECT_URI"
    )

    bootstrap_admin_email: str = Field(default="admin@jarvas.dev", alias="BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_admin_password: str = Field(default="admin-change-me", alias="BOOTSTRAP_ADMIN_PASSWORD")
    bootstrap_tenant_name: str = Field(default="JARVAS Demo Tenant", alias="BOOTSTRAP_TENANT_NAME")

    # ---- Biometric encryption ---------------------------------------------
    biometric_encryption_key: str = Field(default="", alias="BIOMETRIC_ENCRYPTION_KEY")

    # ---- Storage -----------------------------------------------------------
    storage_backend: str = Field(default="s3", alias="STORAGE_BACKEND")  # s3 | local
    s3_endpoint_url: str = Field(default="http://minio:9000", alias="S3_ENDPOINT_URL")
    s3_public_endpoint_url: str = Field(default="http://localhost:9000", alias="S3_PUBLIC_ENDPOINT_URL")
    s3_access_key: str = Field(default="jarvas", alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field(default="jarvas", alias="S3_SECRET_KEY")
    s3_bucket_uploads: str = Field(default="jarvas-uploads", alias="S3_BUCKET_UPLOADS")
    s3_bucket_results: str = Field(default="jarvas-results", alias="S3_BUCKET_RESULTS")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")
    s3_force_path_style: bool = Field(default=True, alias="S3_FORCE_PATH_STYLE")

    # ---- AI ----------------------------------------------------------------
    face_detection_model: str = Field(default="buffalo_sc", alias="FACE_DETECTION_MODEL")
    face_recognition_model: str = Field(default="buffalo_sc", alias="FACE_RECOGNITION_MODEL")
    face_providers: str = Field(default="CPUExecutionProvider", alias="FACE_PROVIDERS")
    face_det_size: int = Field(default=640, alias="FACE_DET_SIZE")
    face_embedding_dim: int = Field(default=512, alias="FACE_EMBEDDING_DIM")
    model_dir: str = Field(default="/models", alias="MODEL_DIR")
    allow_mock_face_engine: bool = Field(default=True, alias="ALLOW_MOCK_FACE_ENGINE")
    default_similarity_threshold: float = Field(default=0.38, alias="DEFAULT_SIMILARITY_THRESHOLD")
    min_face_size: int = Field(default=80, alias="MIN_FACE_SIZE")
    recognition_enabled: bool = Field(default=True, alias="RECOGNITION_ENABLED")

    # ---- Video -------------------------------------------------------------
    video_max_duration_seconds: int = Field(default=600, alias="VIDEO_MAX_DURATION_SECONDS")
    video_max_upload_mb: int = Field(default=512, alias="VIDEO_MAX_UPLOAD_MB")
    video_default_sample_fps: float = Field(default=1.0, alias="VIDEO_DEFAULT_SAMPLE_FPS")

    # ---- Retention / limits ------------------------------------------------
    default_retention_days: int = Field(default=180, alias="DEFAULT_RETENTION_DAYS")
    max_upload_mb: int = Field(default=25, alias="MAX_UPLOAD_MB")
    allowed_image_types: str = Field(
        default="image/jpeg,image/png,image/webp", alias="ALLOWED_IMAGE_TYPES"
    )
    allowed_video_types: str = Field(
        default="video/mp4,video/quicktime,video/webm", alias="ALLOWED_VIDEO_TYPES"
    )

    # ---- CORS --------------------------------------------------------------
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    @field_validator("env")
    @classmethod
    def _normalise_env(cls, v: str) -> str:
        return v.lower()

    @property
    def is_production(self) -> bool:
        return self.env in {"production", "prod"}

    @property
    def image_types(self) -> List[str]:
        return [t.strip() for t in self.allowed_image_types.split(",") if t.strip()]

    @property
    def video_types(self) -> List[str]:
        return [t.strip() for t in self.allowed_video_types.split(",") if t.strip()]

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def provider_list(self) -> List[str]:
        return [p.strip() for p in self.face_providers.split(",") if p.strip()]

    @property
    def resolved_database_url(self) -> str:
        """Return the configured DB URL or a local SQLite fallback for dev."""
        if self.database_url:
            return self.database_url
        return "sqlite+pysqlite:///./data/jarvas.sqlite3"

    @property
    def use_sqlite(self) -> bool:
        return self.resolved_database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
