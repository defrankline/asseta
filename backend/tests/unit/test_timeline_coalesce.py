"""Timeline worker batching (Gate 7E): one replay per machine per batch, from the earliest event time."""

from asseta.workers.timeline_worker import coalesce


def _p(tenant: str, machine: str, t: str) -> dict[str, str]:
    return {"tenant_id": tenant, "machine_id": machine, "event_time": t}


def test_coalesce_keeps_earliest_event_per_machine_and_separates_tenants() -> None:
    batch = [
        _p("T1", "M1", "2026-10-22T10:05:00+00:00"),
        _p("T1", "M1", "2026-10-22T09:00:00+00:00"),  # late fix in the same batch: replay must start here
        _p("T1", "M2", "2026-10-22T10:00:00+00:00"),
        _p("T2", "M1", "2026-10-22T11:00:00+00:00"),  # same machine id under another tenant is never merged
        _p("T1", "M1", "2026-10-22T10:10:00+00:00"),
    ]
    out = {(p["tenant_id"], p["machine_id"]): p["event_time"] for p in coalesce(batch)}
    assert out == {
        ("T1", "M1"): "2026-10-22T09:00:00+00:00",
        ("T1", "M2"): "2026-10-22T10:00:00+00:00",
        ("T2", "M1"): "2026-10-22T11:00:00+00:00",
    }


def test_coalesce_empty_batch() -> None:
    assert coalesce([]) == []
