"""Real-time fan-out port. Workers publish; every API instance's WebSocket gateway subscribes, so a message reaches
the user whichever instance holds the socket (Redis pub/sub). Delivery is best effort: the inbox is the durable
record and clients re-read it on (re)connect."""

import asyncio
import json
import threading
import uuid
from typing import Any, Protocol

import redis
import redis.asyncio as aioredis
import structlog

log = structlog.get_logger()
PREFIX = "asseta:rt"


def user_channel(user_id: uuid.UUID | str, tenant_id: uuid.UUID | str | None) -> str:
    return f"{PREFIX}:user:{user_id}:{tenant_id or 'platform'}"


def entity_channel(tenant_id: uuid.UUID | str | None) -> str:
    return f"{PREFIX}:entity:{tenant_id or 'platform'}"


class RealtimePublisher(Protocol):
    def publish(self, channel: str, message: dict[str, Any]) -> None: ...


class Subscription(Protocol):
    async def get(self, timeout: float) -> dict[str, Any] | None: ...

    async def close(self) -> None: ...


class RealtimeBroker(Protocol):
    def publish(self, channel: str, message: dict[str, Any]) -> None: ...

    async def subscribe(self, channels: list[str]) -> Subscription: ...


class _RedisSubscription:
    def __init__(self, client: aioredis.Redis, pubsub: Any):
        self._client, self._pubsub = client, pubsub

    async def get(self, timeout: float) -> dict[str, Any] | None:
        msg = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=timeout)
        if msg is None or msg.get("type") != "message":
            return None
        data = msg["data"]
        decoded: dict[str, Any] = json.loads(data.decode() if isinstance(data, bytes) else data)
        return decoded

    async def close(self) -> None:
        await self._pubsub.aclose()
        await self._client.aclose()


class RedisBroker:
    """Connections are created lazily: an API that never pushes or accepts sockets never touches Redis."""

    def __init__(self, url: str):
        self._url = url
        self._sync: redis.Redis | None = None
        self._lock = threading.Lock()

    def publish(self, channel: str, message: dict[str, Any]) -> None:
        with self._lock:
            if self._sync is None:
                self._sync = redis.Redis.from_url(self._url, socket_timeout=2.0, socket_connect_timeout=2.0)
        self._sync.publish(channel, json.dumps(message, default=str, separators=(",", ":")))

    async def subscribe(self, channels: list[str]) -> Subscription:
        client = aioredis.Redis.from_url(self._url)
        pubsub = client.pubsub()
        await pubsub.subscribe(*channels)
        return _RedisSubscription(client, pubsub)


class _MemorySubscription:
    def __init__(self, broker: "InMemoryBroker", channels: list[str], queue: "asyncio.Queue[dict[str, Any]]"):
        self._broker, self._channels, self._queue = broker, channels, queue

    async def get(self, timeout: float) -> dict[str, Any] | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout)
        except TimeoutError:
            return None

    async def close(self) -> None:
        self._broker.unsubscribe(self._channels, self._queue)


class InMemoryBroker:
    """Single-process broker (tests/dev): thread-safe publish into the subscribers' event loops."""

    def __init__(self) -> None:
        self._subs: dict[str, list[tuple[asyncio.AbstractEventLoop, asyncio.Queue[dict[str, Any]]]]] = {}
        self._lock = threading.Lock()
        self.published: list[tuple[str, dict[str, Any]]] = []

    def publish(self, channel: str, message: dict[str, Any]) -> None:
        payload = json.loads(json.dumps(message, default=str))
        with self._lock:
            self.published.append((channel, payload))
            targets = list(self._subs.get(channel, []))
        for loop, queue in targets:
            loop.call_soon_threadsafe(queue.put_nowait, payload)

    def subscribers(self, channel: str) -> int:
        with self._lock:
            return len(self._subs.get(channel, []))

    async def subscribe(self, channels: list[str]) -> Subscription:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        with self._lock:
            for c in channels:
                self._subs.setdefault(c, []).append((loop, queue))
        return _MemorySubscription(self, channels, queue)

    def unsubscribe(self, channels: list[str], queue: "asyncio.Queue[dict[str, Any]]") -> None:
        with self._lock:
            for c in channels:
                self._subs[c] = [(lp, q) for lp, q in self._subs.get(c, []) if q is not queue]


class SafePublisher:
    """Wraps a broker so a Redis outage never fails the caller (inbox remains the source of truth)."""

    def __init__(self, broker: RealtimeBroker | None):
        self._broker = broker

    def publish(self, channel: str, message: dict[str, Any]) -> None:
        if self._broker is None:
            return
        try:
            self._broker.publish(channel, message)
        except Exception as exc:  # degrade to inbox-only
            log.warning("realtime_publish_failed", channel=channel.split(":")[2], error=type(exc).__name__)
