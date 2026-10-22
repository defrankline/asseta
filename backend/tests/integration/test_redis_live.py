"""Live Redis pub/sub fan-out for the WebSocket gateway: a message published by a worker process reaches a subscriber
(as on another API instance).

ASSETA_IT_REDIS_URL=redis://:<password>@localhost:6380/0 uv run pytest -m integration tests/integration/test_redis_live.py
"""

import asyncio
import os
import uuid

import pytest

from asseta.modules.notification.realtime import RedisBroker, user_channel

URL = os.environ.get("ASSETA_IT_REDIS_URL", "")
pytestmark = [pytest.mark.integration, pytest.mark.skipif(not URL, reason="ASSETA_IT_REDIS_URL not set")]


def test_publish_reaches_subscriber_on_another_connection() -> None:
    channel = user_channel(uuid.uuid4(), uuid.uuid4())
    subscriber_side, publisher_side = RedisBroker(URL), RedisBroker(URL)

    async def scenario() -> dict[str, object] | None:
        sub = await subscriber_side.subscribe([channel])
        try:
            await asyncio.sleep(0.2)
            await asyncio.to_thread(publisher_side.publish, channel, {"type": "notification", "payload": {"n": 1}})
            for _ in range(20):
                msg = await sub.get(timeout=0.5)
                if msg is not None:
                    return msg
            return None
        finally:
            await sub.close()

    assert asyncio.run(scenario()) == {"type": "notification", "payload": {"n": 1}}
