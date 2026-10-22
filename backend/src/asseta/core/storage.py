"""Evidence object storage port + S3/MinIO adapter.

Objects are immutable and content-addressed (SHA-256) under tenant-prefixed keys. Clients never receive bucket
credentials or permanent URLs — only short-lived presigned GET URLs issued after an authorization check.
"""

import hashlib
from dataclasses import dataclass
from typing import Protocol

from asseta.core.errors import BusinessRuleViolation, DependencyUnavailable

IMAGE_SIGNATURES = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG\r\n\x1a\n": "image/png"}


@dataclass(frozen=True)
class StoredObject:
    key: str
    sha256: str
    size_bytes: int
    content_type: str


class ObjectStore(Protocol):
    def put_immutable(self, key: str, data: bytes, content_type: str, sha256: str) -> None: ...

    def presigned_get(self, key: str, ttl_seconds: int) -> str: ...


class ObjectReader(Protocol):
    """Server-side read of a stored object (model artifacts); never used to serve evidence to clients."""

    def get_bytes(self, key: str) -> bytes: ...


def sniff_image(data: bytes) -> str:
    """Validate by magic bytes, never by the client-declared content type."""
    for signature, content_type in IMAGE_SIGNATURES.items():
        if data.startswith(signature):
            return content_type
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise BusinessRuleViolation("File is not a supported image (JPEG, PNG, WebP)", code="UNSUPPORTED_MEDIA")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class S3ObjectStore:
    def __init__(
        self, endpoint: str, public_endpoint: str | None, bucket: str, access_key: str, secret_key: str, timeout: float
    ):
        import boto3
        from botocore.config import Config

        cfg = Config(
            connect_timeout=timeout,
            read_timeout=timeout,
            retries={"max_attempts": 3, "mode": "standard"},
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        )
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=cfg,
            region_name="us-east-1",
        )
        # Presigned URLs must be signed for the host the *browser/phone* will use.
        self._signer = boto3.client(
            "s3",
            endpoint_url=public_endpoint or endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=cfg,
            region_name="us-east-1",
        )

    def ensure_bucket(self) -> None:
        from botocore.exceptions import ClientError

        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self._bucket)

    def put_immutable(self, key: str, data: bytes, content_type: str, sha256: str) -> None:
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                Metadata={"sha256": sha256},
                IfNoneMatch="*",
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("PreconditionFailed", "412"):
                return  # identical content-addressed object already stored
            raise DependencyUnavailable("Object storage write failed") from exc
        except BotoCoreError as exc:
            raise DependencyUnavailable("Object storage unavailable") from exc

    def get_bytes(self, key: str) -> bytes:
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            body = self._client.get_object(Bucket=self._bucket, Key=key)["Body"]
            data: bytes = body.read()
            return data
        except (BotoCoreError, ClientError) as exc:
            raise DependencyUnavailable("Object storage read failed") from exc

    def presigned_get(self, key: str, ttl_seconds: int) -> str:
        url: str = self._signer.generate_presigned_url(
            "get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=ttl_seconds
        )
        return url
