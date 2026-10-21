"""Live MinIO: immutable content-addressed put, presigned GET works, then expires (storage URL access, §10 #11).

ASSETA_IT_S3=http://localhost:9100 ASSETA_IT_S3_KEY=... ASSETA_IT_S3_SECRET=... uv run pytest -m integration
"""

import os
import time
import uuid

import httpx
import pytest

from asseta.core.storage import S3ObjectStore, sha256_hex

S3 = os.environ.get("ASSETA_IT_S3", "")
pytestmark = [pytest.mark.integration, pytest.mark.skipif(not S3, reason="ASSETA_IT_S3 not set")]


def test_presigned_url_works_then_expires() -> None:
    store = S3ObjectStore(S3, None, "asseta-it", os.environ["ASSETA_IT_S3_KEY"], os.environ["ASSETA_IT_S3_SECRET"], 5)
    store.ensure_bucket()
    data = b"\xff\xd8\xff" + uuid.uuid4().bytes
    key = f"tenants/{uuid.uuid4()}/machines/{uuid.uuid4()}/photos/{sha256_hex(data)}"
    store.put_immutable(key, data, "image/jpeg", sha256_hex(data))
    store.put_immutable(key, b"\xff\xd8\xff different", "image/jpeg", "x")  # no overwrite of evidence
    url = store.presigned_get(key, ttl_seconds=2)
    first = httpx.get(url)
    assert first.status_code == 200 and first.content == data
    time.sleep(3)
    assert httpx.get(url).status_code == 403
    assert httpx.get(url.split("?")[0]).status_code == 403  # no anonymous access without a signature
