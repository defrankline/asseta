"""TRACKING.field_fleet_scope: people without fleet oversight (supervisors) see only their own machines on the fleet
map, machine status and history, tracking alerts and the fleet reports, unless the tenant opens the whole fleet."""

from datetime import timedelta
from typing import Any

from tests.support.api import Actor, Api
from tests.support.finance import role, setup_finance

T = "/api/v1/tenant"


def _map_ids(actor: Actor) -> set[str]:
    r = actor.get(f"{T}/fleet/map")
    assert r.status_code == 200, r.text
    return {m["machine_id"] for m in r.json()}


def _history(actor: Actor, machine_id: str, now: Any) -> int:
    window = {"from": (now - timedelta(hours=2)).isoformat(), "to": now.isoformat()}
    return int(actor.get(f"{T}/fleet/machines/{machine_id}/history", **window).status_code)


def test_supervisors_see_their_own_machines_unless_the_tenant_opens_the_whole_fleet(api: Api) -> None:
    f = setup_finance(api, "Scope Co", "SCOPE-1")
    mine = f.c.t.machine_id
    [other] = api.add_machines(f.owner, 1, prefix="OTH")
    unlinked = role(api, f.tid, "supervisor", "sup-scope-unlinked")
    now = api.clock.now

    # Default ASSIGNED: the supervisor sees the machine assigned to them (and on their job) only.
    assert _map_ids(f.owner) >= {mine, other}
    assert _map_ids(f.manager) >= {mine, other}
    assert _map_ids(f.supervisor) == {mine}
    assert _map_ids(unlinked) == set()  # no linked staff record: nothing
    assert f.supervisor.get(f"{T}/fleet/machines/{mine}").status_code == 200
    assert f.supervisor.get(f"{T}/fleet/machines/{other}").status_code == 404
    assert _history(f.supervisor, mine, now) == 200
    assert _history(f.supervisor, other, now) == 404
    alerts = f.supervisor.get(f"{T}/alerts")
    assert alerts.status_code == 200, alerts.text
    assert all(a["machine_id"] == mine for a in alerts.json()["items"])
    report = f.supervisor.get(f"{T}/reports/fleet.csv")
    assert report.status_code == 200, report.text
    other_code = f.owner.get(f"{T}/machines/{other}").json()["asset_code"]
    assert other_code not in report.text

    # The tenant opens the whole fleet to field users.
    r = f.owner.post(
        f"{T}/policies/TRACKING/versions",
        {"scope": "TENANT", "values": {"field_fleet_scope": "ALL"}, "reason": "Site leads see the whole fleet"},
    )
    assert r.status_code == 201, r.text
    assert _map_ids(f.supervisor) >= {mine, other}
    assert f.supervisor.get(f"{T}/fleet/machines/{other}").status_code == 200
    assert _history(f.supervisor, other, now) == 200
    assert other_code in f.supervisor.get(f"{T}/reports/fleet.csv").text

    # Tenant level only: a machine cannot widen or narrow it.
    m = f.owner.post(
        f"{T}/policies/TRACKING/versions",
        {"scope": "MACHINE", "scope_ref_id": mine, "values": {"field_fleet_scope": "ASSIGNED"}, "reason": "nope"},
    )
    assert m.json()["error"]["code"] == "POLICY_FIELD_NOT_OVERRIDABLE", m.text
