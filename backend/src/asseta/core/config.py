"""Typed settings loaded from environment (see repo `.env.example`). No business rules live here."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASSETA_", env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+psycopg://asseta_app:asseta_app@localhost:5433/asseta"
    migration_database_url: str = "postgresql+psycopg://asseta_owner:asseta_owner@localhost:5433/asseta"
    redis_url: str = "redis://localhost:6379/0"
    kafka_bootstrap: str = "localhost:9092"
    s3_endpoint: str = "http://localhost:9000"
    s3_public_endpoint: str | None = None  # host used in presigned URLs (defaults to s3_endpoint)
    s3_bucket: str = "asseta-evidence"
    presigned_url_ttl_seconds: int = Field(default=300, ge=30, le=3600)
    max_image_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    s3_access_key: SecretStr = SecretStr("")
    s3_secret_key: SecretStr = SecretStr("")

    keycloak_url: str = "http://localhost:8080"  # internal address for JWKS + Admin REST
    keycloak_public_url: str | None = None  # issuer base seen by browsers/phones (defaults to keycloak_url)
    keycloak_realm: str = "asseta"
    keycloak_api_client_id: str = "asseta-api"
    keycloak_api_client_secret: SecretStr = SecretStr("")
    keycloak_audience: str = "asseta-api"
    jwks_cache_seconds: int = Field(default=300, ge=30)
    keycloak_sync_on_startup: bool = True

    billing_scheduler_interval_seconds: int = Field(default=3600, ge=60)

    # Gate 6 ML (ADR-007). Unset tracking URI -> training runs are recorded only in Asseta's governance tables
    # (`model_version.tracking_note` says so); the MLflow server keeps its artifacts in its own MinIO bucket.
    mlflow_tracking_uri: str | None = None
    mlflow_artifact_bucket: str = "asseta-mlflow"

    cors_origins: list[str] = ["http://localhost:5173"]
    http_timeout_seconds: float = Field(default=5.0, gt=0)

    @property
    def issuer(self) -> str:
        return f"{self.keycloak_public_url or self.keycloak_url}/realms/{self.keycloak_realm}"

    @property
    def jwks_url(self) -> str:
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}/protocol/openid-connect/certs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
