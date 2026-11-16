"""Field work from a browser (R1): a supervisor without phones lists their own machine reports (`mine`), the
machines they work on (no machine register access) and the capture policies their capture permissions cover."""

from tests.support.api import Actor, Api
from tests.support.finance import role
from tests.support.machine_reports import idle, later, report_body, setup_reports, submit


def test_my_reports_and_field_machines_are_scoped_to_the_caller(api: Api) -> None:
    ctx = setup_reports(api)
    f = ctx.f
    other = role(api, f.tid, "supervisor", "sup-unlinked")
    mine = submit(f.supervisor, report_body(ctx.machine_id, "1002", later(api, 2), [idle(ctx.reasons["TRANSIT"], 2)]))

    def report_ids(actor: Actor, only_mine: bool) -> set[str]:
        r = actor.get("/api/v1/tenant/machine-reports", **({"mine": "true"} if only_mine else {}))
        assert r.status_code == 200, r.text
        return {j["id"] for j in r.json()["items"]}

    assert report_ids(f.supervisor, True) == {mine["id"]}
    assert report_ids(f.owner, True) == set() and mine["id"] in report_ids(f.owner, False)  # `mine` is opt-in
    assert other.get("/api/v1/tenant/machine-reports", mine="true").json()["items"] == []

    machine = f.owner.get(f"/api/v1/tenant/machines/{f.c.t.machine_id}").json()
    assert f.supervisor.get("/api/v1/tenant/machines").status_code == 403  # no machine register access
    r = f.supervisor.get("/api/v1/tenant/field/machines")
    assert r.status_code == 200, r.text
    assert [m["id"] for m in r.json()] == [machine["id"]]
    assert f.supervisor.get("/api/v1/tenant/field/machines", q=machine["asset_code"]).json()[0]["id"] == machine["id"]
    assert f.supervisor.get("/api/v1/tenant/field/machines", q="no-such-asset").json() == []
    assert other.get("/api/v1/tenant/field/machines").json() == []


def test_field_users_read_only_the_capture_policies_they_capture_under(api: Api) -> None:
    f = setup_reports(api).f
    for ptype in ("METER_CAPTURE", "EXPENSE_CAPTURE"):
        r = f.supervisor.get(f"/api/v1/tenant/policies/{ptype}/effective")
        assert r.status_code == 200, r.text
        assert r.json()["policy_type"] == ptype
    assert f.supervisor.get("/api/v1/tenant/policies/FRAUD_CONTROLS/effective").status_code == 403
    assert f.supervisor.get("/api/v1/tenant/policies/METER_CAPTURE/versions").status_code == 403
    operator = role(api, f.tid, "operator", "op-field")
    assert operator.get("/api/v1/tenant/policies/METER_CAPTURE/effective").status_code == 403
    assert f.owner.get("/api/v1/tenant/policies/FRAUD_CONTROLS/effective").status_code == 200
