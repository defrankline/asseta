"""Injectable clock so billing/entitlement dates are deterministic in tests and replays."""

from collections.abc import Callable
from datetime import UTC, date, datetime

from fastapi import Request

Clock = Callable[[], datetime]


def system_clock() -> datetime:
    return datetime.now(UTC)


def get_today(request: Request) -> date:
    clock: Clock = getattr(request.app.state, "clock", system_clock)
    return clock().date()


def get_now(request: Request) -> datetime:
    clock: Clock = getattr(request.app.state, "clock", system_clock)
    return clock()
