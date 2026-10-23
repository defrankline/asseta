"""Timeline worker loop: a batch without payloads (only errors/EOF) must not commit (fresh-broker crash loop)."""

import signal
from typing import Any

import pytest
from confluent_kafka import KafkaError, KafkaException

from asseta.workers import timeline_worker


class _ErrorMessage:
    def error(self) -> KafkaError:
        return KafkaError(KafkaError.UNKNOWN_TOPIC_OR_PART)


class _FakeConsumer:
    """Returns one batch holding only an 'unknown topic' error, then asks the loop to stop."""

    instance: "_FakeConsumer"

    def __init__(self, _config: dict[str, Any]) -> None:
        self.calls = 0
        self.closed = False
        _FakeConsumer.instance = self

    def subscribe(self, _topics: list[str]) -> None:
        pass

    def consume(self, num_messages: int, timeout: float) -> list[_ErrorMessage]:
        self.calls += 1
        if self.calls == 1:
            return [_ErrorMessage()]
        _handlers["stop"]()
        return []

    def commit(self, asynchronous: bool) -> None:
        raise KafkaException(KafkaError(KafkaError._NO_OFFSET))  # what librdkafka does with nothing stored

    def close(self) -> None:
        self.closed = True


_handlers: dict[str, Any] = {}


def test_batch_of_only_errors_is_not_committed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timeline_worker, "Consumer", _FakeConsumer)
    monkeypatch.setattr(timeline_worker, "configure_logging", lambda: None)
    monkeypatch.setattr(signal, "signal", lambda _sig, handler: _handlers.__setitem__("stop", handler))

    timeline_worker.run()  # raised KafkaException(_NO_OFFSET) before the fix

    assert _FakeConsumer.instance.calls == 2
    assert _FakeConsumer.instance.closed
