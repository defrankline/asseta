"""Field work from a browser (R1): a supervisor without phones lists their own jobs (`mine`), the machines they work
on (no machine register access) and the capture policies their capture permissions cover."""

from tests.support.api import Actor, Api
from tests.support.finance import role, setup_finance


def test_my_jobs_and_field_machines_are_scoped_to_the_caller(api: Api) -> None:
    f = setup_finance(api)
    other = role(api, f.tid, "supervisor", "sup-unlinked")

    def job_ids(actor: Actor, mine: bool) -> set[str]:
        r = actor.get("/api/v1/tenant/jobs", **({"mine": "true"} if mine else {}))
        assert r.status_code == 200, r.text
        return {j["id"] for j in r.json()["items"]}

    assert job_ids(f.supervisor, True) == {f.c.job_id}
    assert f.c.job_id in job_ids(f.supervisor, False)  # unchanged: `mine` is opt-in
    assert job_ids(other, True) == set()  # no linked staff record: nothing assigned
    assert job_ids(f.owner, True) == set() and f.c.job_id in job_ids(f.owner, False)

    machine = f.owner.get(f"/api/v1/tenant/machines/{f.c.t.machine_id}").json()
    assert f.supervisor.get("/api/v1/tenant/machines").status_code == 403  # no machine register access
    r = f.supervisor.get("/api/v1/tenant/field/machines")
    assert r.status_code == 200, r.text
    assert [m["id"] for m in r.json()] == [machine["id"]]
    assert f.supervisor.get("/api/v1/tenant/field/machines", q=machine["asset_code"]).json()[0]["id"] == machine["id"]
    assert f.supervisor.get("/api/v1/tenant/field/machines", q="no-such-asset").json() == []
    assert other.get("/api/v1/tenant/field/machines").json() == []


def test_field_users_read_only_the_capture_policies_they_capture_under(api: Api) -> None:
    f = setup_finance(api)
    for ptype in ("METER_CAPTURE", "EXPENSE_CAPTURE"):
        r = f.supervisor.get(f"/api/v1/tenant/policies/{ptype}/effective")
        assert r.status_code == 200, r.text
        assert r.json()["policy_type"] == ptype
    assert f.supervisor.get("/api/v1/tenant/policies/HIRE_BILLING/effective").status_code == 403
    assert f.supervisor.get("/api/v1/tenant/policies/METER_CAPTURE/versions").status_code == 403
    operator = role(api, f.tid, "operator", "op-field")
    assert operator.get("/api/v1/tenant/policies/METER_CAPTURE/effective").status_code == 403
    assert f.owner.get("/api/v1/tenant/policies/HIRE_BILLING/effective").status_code == 200
