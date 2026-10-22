"""`asseta-ml` — ML data foundation and training jobs (ADR-007), runnable from cron or by hand.

    asseta-ml snapshot --tenant <uuid|all> [--from YYYY-MM-DD] [--to YYYY-MM-DD]
        Weekly point-in-time feature snapshots at each tenant-local week end in the range (default: the last two
        weeks, so a weekly cron run also catches a week end that was skipped). Backfills are processed in chunks of
        26 week ends, one transaction per tenant and chunk; existing points are never rewritten.
    asseta-ml train --tenant <uuid> [--seed N]
        Train and evaluate the tenant's anomaly model; INSUFFICIENT_DATA records readiness and creates no model.
    asseta-ml status
        Latest readiness, deployed versions and the platform inference switch, one JSON line per tenant.

Runs as the application role: facts and snapshots are read/written in each tenant's own RLS scope, governance rows
in the system scope; every statement is bounded by `statement_timeout`. Exit code 1 if any tenant failed.
"""

import argparse
import json
import sys
import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta

import structlog
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor
from asseta.core.clock import system_clock
from asseta.core.config import get_settings
from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.core.logging import configure_logging
from asseta.modules.intelligence.feature_store import MAX_SNAPSHOT_WEEKS, snapshot_tenant, sync_feature_definitions
from asseta.modules.intelligence.ml_lifecycle import current_ml_setting
from asseta.modules.intelligence.ml_models import DEPLOYED_STATUSES, ModelReadiness, ModelVersion
from asseta.modules.intelligence.ml_training import tracker_from_settings, train_tenant
from asseta.modules.tenancy.models import Tenant, TenantStatus

log = structlog.get_logger()
STATEMENT_TIMEOUT = "120s"
ACTOR = AuditActor(user_id=None, roles=["system"], source="ml-cli")


def _session_scope(session: Session) -> None:
    apply_scope(session, DbScope.SYSTEM, None, None)
    session.execute(text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'"))


def _tenants(arg: str) -> list[uuid.UUID]:
    if arg != "all":
        return [uuid.UUID(arg)]
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.SYSTEM, None, None)
        return list(s.execute(select(Tenant.id).where(Tenant.status != TenantStatus.CLOSED)).scalars())


def _day(value: str | None, default: date) -> date:
    return date.fromisoformat(value) if value else default


def cmd_snapshot(args: argparse.Namespace) -> int:
    now = system_clock()
    start = datetime.combine(_day(args.date_from, (now - timedelta(days=15)).date()), time.min, UTC)
    end = datetime.combine(_day(args.date_to, now.date()), time.min, UTC) + timedelta(days=2)
    failed = 0
    for tenant_id in _tenants(args.tenant):
        chunk_start = start - timedelta(days=1)
        while chunk_start <= end:
            chunk_end = min(end, chunk_start + timedelta(weeks=MAX_SNAPSHOT_WEEKS) - timedelta(seconds=1))
            try:
                with get_sessionmaker().begin() as s:
                    _session_scope(s)
                    sync_feature_definitions(s)
                    r = snapshot_tenant(s, tenant_id, chunk_start, chunk_end, now)
                log.info(
                    "ml_snapshot",
                    tenant_id=str(tenant_id),
                    week_ends=len(r.week_ends),
                    machines=r.machines,
                    written=r.written,
                    skipped_existing=r.skipped_existing,
                )
            except Exception:
                failed += 1
                log.exception("ml_snapshot_failed", tenant_id=str(tenant_id))
                break
            chunk_start = chunk_end + timedelta(seconds=1)
    return 1 if failed else 0


def cmd_train(args: argparse.Namespace) -> int:
    from asseta.main import build_object_store

    settings = get_settings()
    store, tracker = build_object_store(settings), tracker_from_settings(settings)
    tenant_id = uuid.UUID(args.tenant)
    with get_sessionmaker().begin() as s:
        _session_scope(s)
        sync_feature_definitions(s)
        r = train_tenant(s, tenant_id, system_clock(), store, tracker, ACTOR, seed=args.seed)
        out = {
            "tenant_id": str(tenant_id),
            "readiness": r.readiness.status.value,
            "reasons": r.readiness.reasons,
            "model_version": r.model.version if r.model else None,
            "evaluation_passed": r.evaluation.passed if r.evaluation else None,
            "mlflow_run_id": r.model.mlflow_run_id if r.model else None,
            "tracking_note": r.model.tracking_note if r.model else None,
        }
    print(json.dumps(out))
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    with get_sessionmaker().begin() as s:
        _session_scope(s)
        switch = current_ml_setting(s)
        print(json.dumps({"inference_enabled": switch.inference_enabled, "reason": switch.reason}))
        for tenant_id, name in s.execute(select(Tenant.id, Tenant.display_name).order_by(Tenant.display_name)):
            readiness = s.execute(
                select(ModelReadiness)
                .where(ModelReadiness.tenant_id == tenant_id)
                .order_by(ModelReadiness.computed_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            deployed = s.execute(
                select(ModelVersion).where(
                    ModelVersion.tenant_id == tenant_id, ModelVersion.status.in_(DEPLOYED_STATUSES)
                )
            ).scalars()
            print(
                json.dumps(
                    {
                        "tenant_id": str(tenant_id),
                        "tenant": name,
                        "readiness": readiness.status.value if readiness else "NOT_ASSESSED",
                        "reasons": readiness.reasons if readiness else [],
                        "deployed": [f"{m.name} v{m.version} {m.status.value}" for m in deployed],
                    }
                )
            )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asseta-ml", description=__doc__.split("\n\n")[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="command", required=True)
    snap = sub.add_parser("snapshot", help="compute weekly point-in-time feature snapshots")
    snap.add_argument("--tenant", required=True, help="tenant UUID or 'all'")
    snap.add_argument("--from", dest="date_from", help="first day of the range (YYYY-MM-DD)")
    snap.add_argument("--to", dest="date_to", help="last day of the range (YYYY-MM-DD)")
    snap.set_defaults(func=cmd_snapshot)
    train = sub.add_parser("train", help="train and evaluate one tenant's anomaly model")
    train.add_argument("--tenant", required=True, help="tenant UUID")
    train.add_argument("--seed", type=int, default=0)
    train.set_defaults(func=cmd_train)
    status = sub.add_parser("status", help="readiness, deployed models and the inference switch")
    status.set_defaults(func=cmd_status)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    configure_logging()
    args = build_parser().parse_args(argv)
    code: int = args.func(args)
    return code


if __name__ == "__main__":
    sys.exit(main())
