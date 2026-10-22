"""Typed settings loaded from environment (see repo `.env.example`). No business rules live here."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASSETA_", env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+psycopg://asseta_app:asseta_app@localhost:5433/asseta"
    migration_database_url: str = "postgresql+psycopg://asseta_owner:asseta_owner@localhost:5433/asseta"
    # Safety valves for the API/worker role (Gate 7E load drill): a request waiting on a row lock fails fast
    # (503 DATABASE_BUSY, clients/Traccar retry) instead of pinning a pool connection and a worker thread forever,
    # and a transaction left idle (e.g. its thread starved) is ended by the server. A runaway statement is
    # cancelled after db_statement_timeout_ms (503 QUERY_TIMEOUT; F-7). Workers get a longer budget in compose.yaml
    # and code paths with their own budget (ML CLI, inference) override it with SET LOCAL. 0 disables any of them.
    db_lock_timeout_ms: int = Field(default=5000, ge=0)
    db_idle_in_transaction_timeout_ms: int = Field(default=60000, ge=0)
    db_statement_timeout_ms: int = Field(default=30000, ge=0)
    redis_url: str = "redis://localhost:6379/0"
    kafka_bootstrap: str = "localhost:9092"
    s3_endpoint: str = "http://localhost:9000"
    s3_public_endpoint: str | None = None  # host used in presigned URLs (defaults to s3_endpoint)
    s3_bucket: str = "asseta-evidence"
    presigned_url_ttl_seconds: int = Field(default=300, ge=30, le=3600)
    max_image_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    # Whole-request body cap (F-6), enforced before any handler buffers or spools the body: the largest image plus
    # multipart overhead. Keep it in step with `client_max_body_size` in web/nginx.conf. 0 disables.
    max_request_bytes: int = Field(default=11 * 1024 * 1024, ge=0)
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
