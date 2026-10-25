"""Names-next-to-ids convention (G2), capability-gated menus (G1) and exact-record notification data (G5)."""

import uuid

from asseta.modules.accountability.names import _rule, _spec
from asseta.modules.finance.custody_dto import CashTransferDto
from asseta.modules.identity.catalog import CATALOG
from asseta.modules.notification.rules import record_data, record_link
from asseta.modules.policy.capabilities import CAPABILITIES


def test_name_field_convention() -> None:
    assert _rule("proposed_by") == ("user", {"name": "proposed_by_name"})
    assert _rule("from_staff_id") == ("staff", {"name": "from_staff_name"})
    assert _rule("staff_member_id") == ("staff", {"name": "staff_member_name"})
    assert _rule("to_machine_id") == ("machine", {"name": "to_machine_name", "code": "to_machine_code"})
    assert _rule("job_site_id") == ("site", {"name": "job_site_name"})
    assert _rule("job_id") == ("job", {"number": "job_number"})
    assert _rule("reason_id") is None and _rule("amount") is None
    fields = {f for f, _, _ in _spec(CashTransferDto)}
    assert {"from_staff_id", "to_staff_id", "recorded_by", "acknowledged_by"} <= fields


def test_every_gated_menu_names_a_known_capability() -> None:
    assert CATALOG.capabilities() <= set(CAPABILITIES)
    assert CATALOG.menu_capabilities("tenant.hours.purchases") == {"CUSTOMER_HOURS"}
    assert CATALOG.menu_capabilities("tenant.field.hours") == {"CUSTOMER_HOURS"}
    assert CATALOG.menu_capabilities("tenant.cash_custody") == frozenset()


def test_accountability_records_have_exact_links_and_kinds() -> None:
    rid = uuid.uuid4()
    assert record_link("cash_retention", rid, "/x") == f"/tenant/finance/cash/retentions/{rid}"
    assert record_data("cash_retention", rid) == {"kind": "CASH_RETENTION", "record_id": str(rid)}
    assert record_link("machine", rid, "/fallback") == "/fallback" and record_data("machine", rid) == {}
