"""R1-B registry (categories, areas, machines w/ optimistic concurrency, staff, effective-dated assignments) and a
privilege audit guarding against migrations silently re-granting what earlier revisions revoked."""

from datetime import timedelta

import pytest
from sqlalchemy import create_engine, text

from asseta.core.config import get_settings
from tests.support.api import Api

# (table, privilege) pairs the application role must never hold.
FORBIDDEN = [
    (t, "UPDATE")
    for t in (
        "audit_event",
        "platform_invoice_line",
        "subscription_rate_version",
        "credit_adjustment",
        "machine_position_event",
        "policy_version",
    )
] + [
    (t, "DELETE")
    for t in (
        "audit_event",
        "platform_invoice",
        "platform_invoice_line",
        "platform_payment",
        "tenant_subscription",
        "machine",
        "tenant",
        "machine_position_event",
        "tracker",
        "tracking_alert",
        "policy_version",
    )
]


@pytest.mark.parametrize(("table", "privilege"), FORBIDDEN)
def test_app_role_lacks_forbidden_privileges(table: str, privilege: str) -> None:
    engine = create_engine(get_settings().migration_database_url)
    with engine.connect() as conn:
        held = conn.execute(
            text("SELECT has_table_privilege('asseta_app', :t, :p)"), {"t": table, "p": privilege}
        ).scalar_one()
    engine.dispose()
    assert held is False, f"asseta_app must not have {privilege} on {table}"


def test_machine_registry_and_assignments(api: Api) -> None:
    t = api.onboard("Registry Co", price="1")
    o = t["owner"]
    cat = o.post("/api/v1/tenant/machine-categories", {"name": "Excavators"}).json()
    area = o.post("/api/v1/tenant/operating-areas", {"code": "DSM", "name": "Dar es Salaam"}).json()
    m = o.post(
        "/api/v1/tenant/machines",
        {
            "asset_code": "EX-01",
            "name": "CAT 320",
            "category_id": cat["id"],
            "operating_area_id": area["id"],
            "manufacturer": "Caterpillar",
            "capacity_value": "1.200",
            "capacity_unit": "m3",
            "meter_decimal_places": 1,
        },
    ).json()
    upd = {
        k: m[k]
        for k in (
            "name",
            "category_id",
            "operating_area_id",
            "manufacturer",
            "model",
            "serial_number",
            "year_of_manufacture",
            "capacity_value",
            "capacity_unit",
            "meter_decimal_places",
            "ownership",
        )
    }
    first = api.client.put(
        f"/api/v1/tenant/machines/{m['id']}",
        headers=o.headers(False, None),
        json={**upd, "status": "ACTIVE", "version": 1, "serial_number": "SN-1"},
    )
    assert first.status_code == 200 and first.json()["version"] == 2
    stale = api.client.put(
        f"/api/v1/tenant/machines/{m['id']}",
        headers=o.headers(False, None),
        json={**upd, "status": "ACTIVE", "version": 1},
    )
    assert stale.json()["error"]["code"] == "STALE_VERSION"  # lost-update protection

    sup = o.post("/api/v1/tenant/staff", {"full_name": "Asha Supervisor", "kind": "SUPERVISOR"}).json()
    sup2 = o.post("/api/v1/tenant/staff", {"full_name": "Juma Supervisor", "kind": "SUPERVISOR"}).json()
    op = o.post("/api/v1/tenant/staff", {"full_name": "Peter Operator", "kind": "OPERATOR"}).json()
    now = api.clock.now
    wrong = o.post(
        f"/api/v1/tenant/machines/{m['id']}/assignments",
        {"staff_member_id": op["id"], "role": "SUPERVISOR", "effective_from": now.isoformat()},
    )
    assert wrong.json()["error"]["code"] == "ASSIGNMENT_ROLE_MISMATCH"
    o.post(
        f"/api/v1/tenant/machines/{m['id']}/assignments",
        {"staff_member_id": sup["id"], "role": "SUPERVISOR", "effective_from": now.isoformat()},
    )
    o.post(
        f"/api/v1/tenant/machines/{m['id']}/assignments",
        {"staff_member_id": sup2["id"], "role": "SUPERVISOR", "effective_from": (now + timedelta(days=1)).isoformat()},
    )
    hist = o.get(f"/api/v1/tenant/machines/{m['id']}/assignments").json()
    assert [(h["staff_member_id"], h["effective_to"] is None) for h in hist] == [(sup2["id"], True), (sup["id"], False)]
    other = api.onboard("Registry Other", price="1")["owner"]
    assert other.get(f"/api/v1/tenant/machines/{m['id']}").status_code == 404
