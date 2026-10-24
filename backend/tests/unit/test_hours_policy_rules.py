"""Customer hours: the platform default is a valid, replaceable policy; inconsistent tenant values are refused; the
notification rules render neutral text for every hours event."""

import uuid
from decimal import Decimal
from typing import Any, cast

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from asseta.modules.hours.ledger import floor_to
from asseta.modules.notification.rules import RULES, DomainEvent
from asseta.modules.notification.types import TYPES
from asseta.modules.policy.schemas import SEED_DEFAULTS, BillingMode, CustomerHoursPolicy, PolicyType


def _policy(**kw: Any) -> CustomerHoursPolicy:
    return CustomerHoursPolicy.model_validate({**SEED_DEFAULTS[PolicyType.CUSTOMER_HOURS], **kw})


def test_platform_default_keeps_the_invoice_flow_and_never_expires() -> None:
    p = _policy()
    assert p.default_billing_mode is BillingMode.INVOICE and p.expiry_days is None
    assert p.transfer_requires_approval and p.cancellation_requires_approval and p.discount_requires_approval


@pytest.mark.parametrize(
    "values",
    [
        {"billing_modes": ["INVOICE"], "default_billing_mode": "PREPAID_HOURS"},
        {"billing_modes": ["INVOICE", "INVOICE"]},
        {"activation_basis": []},
        {"hours_increment": "0"},
        {"expiry_days": 0},
        {"unknown_switch": True},
    ],
)
def test_inconsistent_tenant_values_are_refused(values: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _policy(**values)


def test_activation_rounds_down_to_the_policy_step() -> None:
    assert floor_to(Decimal("3.0117"), Decimal("0.01")) == Decimal("3.01")
    assert floor_to(Decimal("3.99"), Decimal("0.5")) == Decimal("3.50")
    assert floor_to(Decimal("-1"), Decimal("0.01")) == 0


@pytest.mark.parametrize(
    ("event_type", "payload"),
    [
        (
            "HoursApprovalRequested",
            {
                "kind": "TRANSFER",
                "entity_id": "e1",
                "audience_permission": "tenant.hours.transfer_approve",
                "summary": "x",
            },
        ),
        (
            "HoursApprovalDecided",
            {"kind": "CREDIT", "entity_id": "e1", "user_id": str(uuid.uuid4()), "outcome": "APPROVED"},
        ),
        (
            "CustomerHoursOverrun",
            {
                "exception_id": "e1",
                "job_id": "j",
                "job_number": "J-1",
                "machine_id": "n/a",
                "billable_hours": "10",
                "excess_hours": "3",
            },
        ),
        ("CustomerHoursExpired", {"purchase_id": "p", "purchase_number": "HP-2026-00001", "hours": "2"}),
    ],
)
def test_hours_rules_render_known_types_without_accusation(event_type: str, payload: dict[str, Any]) -> None:
    intents = RULES[event_type](cast(Session, None), DomainEvent(uuid.uuid4(), event_type, uuid.uuid4(), payload))
    assert intents and all(i.type in TYPES for i in intents)
    assert all("fraud" not in (i.title + i.body).lower() for i in intents)
