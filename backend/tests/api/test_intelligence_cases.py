"""Gate 6 investigation cases: grouping, assign/note/resolve/reopen lifecycle with optimistic versions, segregation
of duties, permissions, AnomalyDetected publication and the §10 #9 acceptance scenario (neutral wording)."""

import json
from datetime import timedelta
from typing import Any

from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, category, expense_policy, role, setup_finance
from tests.support.intelligence import cases, expense, feed_events, fraud_policy, receipt, signals, sweep
from tests.support.jobs import unique_jpeg
from tests.support.notify import member, sql, user_id


def _duplicate_receipt_case(api: Api, f: FinCtx, submitter: Actor) -> dict[str, Any]:
    """Two expenses by `submitter` with the same receipt image -> one case on the second expense."""
    cat = category(f, "SPARES", "Spares")
    expense_policy(f, receipt_required_above="0", gps_required=False, auto_approve_limit="0")
    image = unique_jpeg()
    for _ in range(2):
        expense(api, submitter, cat, "45000", receipt_attachment_ids=[receipt(api, submitter, image)])
        api.clock.set_at(api.clock.now + timedelta(minutes=30))
    feed_events(api, f.tid)
    [case] = cases(f.owner)
    return case


def _no_fraud_wording(payload: Any) -> None:
    """No field name or text calls anyone fraudulent. `policy_version` stamps name the FRAUD_CONTROLS policy type
    (configuration identity, not a finding) and are excluded."""

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                assert "fraud" not in str(k).lower(), k
                if k != "policy_version":
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        else:
            assert "fraud" not in str(node).lower(), node

    walk(payload)


def test_section10_9_evidence_backed_case_resolved_with_legitimate_explanation(api: Api) -> None:
    f = setup_finance(api, "Accept Co", "ACC-1")
    reviewer = member(api, f.tid, "manager", "reviewer-acc")
    case = _duplicate_receipt_case(api, f, f.supervisor)
    assert (case["status"], case["severity"], case["subject_type"]) == ("OPEN", "WARNING", "EXPENSE")
    assert case["case_number"].startswith(f"CASE-{api.clock.now.year}-") and case["signal_count"] == 1

    detail = reviewer.get(f"/api/v1/tenant/cases/{case['id']}").json()
    [sig] = detail["signals"]
    assert sig["source_type"] == "RISK_SIGNAL" and sig["code"] == "DUPLICATE_RECEIPT"
    assert sig["evidence"]["receipt_sha256"] and sig["evidence"]["same_receipt_on"]  # actionable facts

    r = reviewer.post(
        f"/api/v1/tenant/cases/{case['id']}/assign",
        {"assignee_user_id": str(user_id(reviewer.subject)), "version": case["version"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["case"]["status"] == "IN_REVIEW"
    note = reviewer.post(f"/api/v1/tenant/cases/{case['id']}/notes", {"body": "Called the supplier."})
    assert note.status_code == 201, note.text
    explanation = "Supplier issued one receipt covering two deliveries; both are genuine and paid once each."
    current = reviewer.get(f"/api/v1/tenant/cases/{case['id']}").json()["case"]["version"]
    done = reviewer.post(
        f"/api/v1/tenant/cases/{case['id']}/resolve",
        {"outcome": "LEGITIMATE_EXPLANATION", "explanation": explanation, "version": current},
    )
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["case"]["status"] == "RESOLVED" and body["case"]["latest_outcome"] == "LEGITIMATE_EXPLANATION"
    assert [o["explanation"] for o in body["outcomes"]] == [explanation]
    _no_fraud_wording(body)
    _no_fraud_wording(signals(f.owner))
    _no_fraud_wording(cases(f.owner))
    actions = {r[0] for r in sql("SELECT action FROM audit_event WHERE entity_type = 'anomaly_case'")}
    assert {"intelligence.case.opened", "intelligence.case.assigned", "intelligence.case.resolved"} <= actions


def test_lifecycle_versions_reopen_and_new_outcome(api: Api) -> None:
    f = setup_finance(api, "Life Co", "LIFE-1")
    reviewer = member(api, f.tid, "manager", "reviewer-life")
    case = _duplicate_receipt_case(api, f, f.supervisor)
    path = f"/api/v1/tenant/cases/{case['id']}"
    stale = reviewer.post(f"{path}/resolve", {"outcome": "UNCONFIRMED", "explanation": "x" * 12, "version": 99})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_VERSION"
    short = reviewer.post(f"{path}/resolve", {"outcome": "UNCONFIRMED", "explanation": "too short"})
    assert short.status_code == 422
    assert reviewer.post(f"{path}/notes", {"body": "Looking"}).status_code == 201
    assert reviewer.get(path).json()["case"]["status"] == "IN_REVIEW"  # first note starts the review
    first = reviewer.post(f"{path}/resolve", {"outcome": "UNCONFIRMED", "explanation": "Could not reach supplier."})
    assert first.status_code == 200, first.text
    again = reviewer.post(f"{path}/resolve", {"outcome": "UNCONFIRMED", "explanation": "Second attempt here."})
    assert again.status_code == 409 and again.json()["error"]["code"] == "CASE_RESOLVED"
    reopen = reviewer.post(f"{path}/reopen", {"reason": "Supplier replied with a new statement."})
    assert reopen.status_code == 200 and reopen.json()["case"]["status"] == "IN_REVIEW", reopen.text
    assert reopen.json()["notes"][-1]["kind"] == "REOPEN"
    final = reviewer.post(
        f"{path}/resolve", {"outcome": "CONFIRMED_ISSUE", "explanation": "Receipt reused for a second claim."}
    )
    assert final.status_code == 200, final.text
    outcomes = final.json()["outcomes"]
    assert [(o["sequence"], o["outcome"]) for o in outcomes] == [(1, "UNCONFIRMED"), (2, "CONFIRMED_ISSUE")]
    key = "11111111-2222-4333-8444-555555555555"
    n1 = reviewer.post(f"{path}/notes", {"body": "Follow-up"}, key=key)
    n2 = reviewer.post(f"{path}/notes", {"body": "Follow-up"}, key=key)
    assert n1.status_code == n2.status_code == 201 and n1.json()["id"] == n2.json()["id"]  # idempotent replay
    bad = reviewer.post(f"{path}/assign", {"assignee_user_id": str(user_id(reviewer.subject))})
    assert bad.status_code == 409 and bad.json()["error"]["code"] == "CASE_RESOLVED"


def test_grouping_into_one_case_and_assignee_must_be_member(api: Api) -> None:
    f = setup_finance(api, "Group Co", "GRP-1")
    reviewer = member(api, f.tid, "manager", "reviewer-grp")
    f.accountant.post("/api/v1/tenant/cash/floats", {"staff_member_id": f.sup_staff_id, "amount": "300000"})
    api.clock.set_at(api.clock.now + timedelta(hours=49))
    sweep(api, f.tid)
    [case] = cases(f.owner)
    outsider = api.onboard("Outsider Co", price="1000")
    member(api, outsider["tenant"]["id"], "manager", "outsider-mgr")
    r = reviewer.post(f"/api/v1/tenant/cases/{case['id']}/assign", {"assignee_user_id": str(user_id("outsider-mgr"))})
    assert r.status_code == 422 and r.json()["error"]["code"] == "ASSIGNEE_NOT_MEMBER"
    # A later signal on the same supervisor within the grouping window joins the open case.
    fraud_policy(f.owner, cash_outstanding_max_amount="1000")
    sweep(api, f.tid)
    [case] = cases(f.owner)
    assert case["signal_count"] == 2 and case["severity"] == "CRITICAL"
    events = sql("SELECT payload FROM outbox_event WHERE event_type = 'AnomalyDetected' ORDER BY created_at")
    assert [e.payload["kind"] for e in events] == ["CASE_OPENED", "CASE_ESCALATED"]
    p = events[0].payload
    assert (p["entity_type"], p["entity_id"], p["link"]) == ("case", case["id"], f"/tenant/cases/{case['id']}")
    assert p["audience_permission"] == "tenant.case.manage" and p["title"].startswith("Needs review: ")
    assert json.dumps([e.payload for e in events]).lower().count("fraud") == 0


def test_segregation_of_duties_and_permissions(api: Api) -> None:
    f = setup_finance(api, "SoD Co", "SOD-1")
    owner_member = member(api, f.tid, "owner", f.owner.subject, sync=True)
    reviewer = member(api, f.tid, "manager", "reviewer-sod")
    case = _duplicate_receipt_case(api, f, owner_member)  # the owner's own expenses are the evidence
    path = f"/api/v1/tenant/cases/{case['id']}"
    me = str(user_id(owner_member.subject))
    assign = reviewer.post(f"{path}/assign", {"assignee_user_id": me})
    assert assign.status_code == 422 and assign.json()["error"]["code"] == "SEGREGATION_OF_DUTIES"
    own = owner_member.post(f"{path}/resolve", {"outcome": "LEGITIMATE_EXPLANATION", "explanation": "It is fine."})
    assert own.status_code == 422 and own.json()["error"]["code"] == "SEGREGATION_OF_DUTIES"
    assert sql("SELECT count(*) FROM outbox_event WHERE event_type = 'SegregationOfDutiesViolation'")[0][0] == 1
    assert reviewer.get(path).json()["case"]["status"] == "OPEN"  # refusal rolled everything back

    operator = role(api, f.tid, "operator", "op-sod")
    assert operator.get("/api/v1/tenant/cases").status_code == 403
    assert operator.get("/api/v1/tenant/risk-signals").status_code == 403
    assert f.supervisor.get("/api/v1/tenant/cases").status_code == 403
    assert f.accountant.get("/api/v1/tenant/cases").status_code == 200
    assert f.accountant.get(path).status_code == 200
    assert f.accountant.get("/api/v1/tenant/risk-signals").status_code == 200
    assert f.accountant.post(f"{path}/notes", {"body": "x"}).status_code == 403
    resolve = {"outcome": "UNCONFIRMED", "explanation": "Not enough to go on."}
    assert f.accountant.post(f"{path}/resolve", resolve).status_code == 403
    assert reviewer.post(f"{path}/resolve", resolve).status_code == 200

    # The refused attempt is itself a deterministic signal: a case about the owner's login, never auto-resolved.
    feed_events(api, f.tid)
    sod = [c for c in cases(f.owner) if c["title"] == "Attempt to approve or verify own record"]
    assert len(sod) == 1 and sod[0]["subject_type"] in ("USER", "STAFF")
