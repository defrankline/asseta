"""Deterministic policy resolution `get_effective_policy(type, tenant, machine, site, at)` and versioning.

Resolution merges, for instant `at`, the latest effective version at each scope:
platform default -> tenant default -> machine override -> site override (only fields allowed per scope),
then validates the merged result against the typed schema. The returned `version_stamp` is recorded on every
evaluated event so later policy changes never silently reinterpret accepted history.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from pydantic import BaseModel, ValidationError
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.db import utcnow
from asseta.core.errors import BusinessRuleViolation, ErrorDetail
from asseta.modules.policy.models import PolicyVersion
from asseta.modules.policy.schemas import (
    OVERRIDABLE,
    SCHEMAS,
    CustomerHoursPolicy,
    DeviceSyncPolicy,
    ExpenseCapturePolicy,
    FraudControlsPolicy,
    HireBillingPolicy,
    MeterCapturePolicy,
    PolicyScope,
    PolicyType,
    TrackingPolicy,
)

BACKDATE_TOLERANCE = timedelta(minutes=5)
_ABBR = {PolicyScope.PLATFORM: "P", PolicyScope.TENANT: "T", PolicyScope.MACHINE: "M", PolicyScope.SITE: "S"}


@dataclass(frozen=True)
class EffectivePolicy[P: BaseModel]:
    policy: P
    version_stamp: str
    version_ids: tuple[uuid.UUID, ...]


class PolicyService:
    def __init__(self, session: Session):
        self._s = session

    def _latest(
        self, ptype: PolicyType, scope: PolicyScope, tenant_id: uuid.UUID | None, ref: uuid.UUID | None, at: datetime
    ) -> PolicyVersion | None:
        conds = [
            PolicyVersion.policy_type == ptype,
            PolicyVersion.scope == scope,
            PolicyVersion.effective_from <= at,
            PolicyVersion.tenant_id.is_(None) if tenant_id is None else PolicyVersion.tenant_id == tenant_id,
            PolicyVersion.scope_ref_id.is_(None) if ref is None else PolicyVersion.scope_ref_id == ref,
        ]
        return self._s.execute(
            select(PolicyVersion)
            .where(and_(*conds))
            .order_by(PolicyVersion.effective_from.desc(), PolicyVersion.version.desc())
            .limit(1)
        ).scalar_one_or_none()

    def resolve(
        self,
        ptype: PolicyType,
        tenant_id: uuid.UUID | None,
        *,
        machine_id: uuid.UUID | None = None,
        site_id: uuid.UUID | None = None,
        at: datetime | None = None,
    ) -> EffectivePolicy[BaseModel]:
        at = at or utcnow()
        layers: list[tuple[PolicyScope, uuid.UUID | None, uuid.UUID | None]] = [(PolicyScope.PLATFORM, None, None)]
        if tenant_id is not None:
            layers.append((PolicyScope.TENANT, tenant_id, None))
            if machine_id is not None:
                layers.append((PolicyScope.MACHINE, tenant_id, machine_id))
            if site_id is not None:
                layers.append((PolicyScope.SITE, tenant_id, site_id))
        merged: dict[str, Any] = {}
        stamp, ids = [], []
        for scope, tid, ref in layers:
            row = self._latest(ptype, scope, tid, ref, at)
            if row is None:
                continue
            merged.update(row.values)
            stamp.append(f"{_ABBR[scope]}{row.version}")
            ids.append(row.id)
        if not ids:
            raise BusinessRuleViolation(f"No {ptype.value} policy configured", code="POLICY_NOT_CONFIGURED")
        schema = SCHEMAS[ptype]
        self._validate(schema, merged)
        return EffectivePolicy(schema.model_validate(merged), f"{ptype.value}@{'.'.join(stamp)}", tuple(ids))

    def tracking(
        self,
        tenant_id: uuid.UUID,
        machine_id: uuid.UUID | None = None,
        site_id: uuid.UUID | None = None,
        at: datetime | None = None,
    ) -> EffectivePolicy[TrackingPolicy]:
        return cast(
            EffectivePolicy[TrackingPolicy],
            self.resolve(PolicyType.TRACKING, tenant_id, machine_id=machine_id, site_id=site_id, at=at),
        )

    def meter_capture(
        self,
        tenant_id: uuid.UUID,
        machine_id: uuid.UUID | None = None,
        site_id: uuid.UUID | None = None,
        at: datetime | None = None,
    ) -> EffectivePolicy[MeterCapturePolicy]:
        return cast(
            EffectivePolicy[MeterCapturePolicy],
            self.resolve(PolicyType.METER_CAPTURE, tenant_id, machine_id=machine_id, site_id=site_id, at=at),
        )

    def hire_billing(self, tenant_id: uuid.UUID, at: datetime | None = None) -> EffectivePolicy[HireBillingPolicy]:
        return cast(EffectivePolicy[HireBillingPolicy], self.resolve(PolicyType.HIRE_BILLING, tenant_id, at=at))

    def device_sync(self, tenant_id: uuid.UUID, at: datetime | None = None) -> EffectivePolicy[DeviceSyncPolicy]:
        return cast(EffectivePolicy[DeviceSyncPolicy], self.resolve(PolicyType.DEVICE_SYNC, tenant_id, at=at))

    def expense_capture(
        self, tenant_id: uuid.UUID, at: datetime | None = None
    ) -> EffectivePolicy[ExpenseCapturePolicy]:
        return cast(EffectivePolicy[ExpenseCapturePolicy], self.resolve(PolicyType.EXPENSE_CAPTURE, tenant_id, at=at))

    def fraud_controls(
        self, tenant_id: uuid.UUID, machine_id: uuid.UUID | None = None, at: datetime | None = None
    ) -> EffectivePolicy[FraudControlsPolicy]:
        return cast(
            EffectivePolicy[FraudControlsPolicy],
            self.resolve(PolicyType.FRAUD_CONTROLS, tenant_id, machine_id=machine_id, at=at),
        )

    def customer_hours(self, tenant_id: uuid.UUID, at: datetime | None = None) -> EffectivePolicy[CustomerHoursPolicy]:
        return cast(EffectivePolicy[CustomerHoursPolicy], self.resolve(PolicyType.CUSTOMER_HOURS, tenant_id, at=at))

    def by_stamp(self, ptype: PolicyType, version_ids: list[uuid.UUID]) -> dict[str, Any]:
        """Re-materialize the policy snapshot a device enforced offline, from its version ids."""
        rows = {
            r.id: r for r in self._s.execute(select(PolicyVersion).where(PolicyVersion.id.in_(version_ids))).scalars()
        }
        if set(version_ids) - rows.keys() or any(r.policy_type is not ptype for r in rows.values()):
            raise BusinessRuleViolation("Unknown policy snapshot", code="POLICY_SNAPSHOT_UNKNOWN")
        order = [PolicyScope.PLATFORM, PolicyScope.TENANT, PolicyScope.MACHINE, PolicyScope.SITE]
        merged: dict[str, Any] = {}
        for row in sorted(rows.values(), key=lambda r: order.index(r.scope)):
            merged.update(row.values)
        return merged

    def create_version(
        self,
        *,
        ptype: PolicyType,
        scope: PolicyScope,
        tenant_id: uuid.UUID | None,
        scope_ref_id: uuid.UUID | None,
        values: dict[str, Any],
        effective_from: datetime | None,
        reason: str,
        actor: AuditActor,
    ) -> PolicyVersion:
        now = utcnow()
        effective = effective_from or now
        if effective < now - BACKDATE_TOLERANCE:
            raise BusinessRuleViolation("Policy changes cannot be backdated", code="POLICY_BACKDATED")
        if (scope is PolicyScope.PLATFORM) != (tenant_id is None):
            raise BusinessRuleViolation("Platform policies have no tenant; others require one", code="POLICY_SCOPE")
        if (scope in (PolicyScope.MACHINE, PolicyScope.SITE)) != (scope_ref_id is not None):
            raise BusinessRuleViolation("Machine/site policies require scope_ref_id", code="POLICY_SCOPE")
        allowed = OVERRIDABLE.get(ptype, {}).get(scope)
        if allowed is not None and (extra := set(values) - allowed):
            raise BusinessRuleViolation(
                f"Fields not overridable at {scope.value}: {sorted(extra)}", code="POLICY_FIELD_NOT_OVERRIDABLE"
            )
        schema = SCHEMAS[ptype]
        unknown = set(values) - set(schema.model_fields)
        if unknown:
            raise BusinessRuleViolation(f"Unknown fields {sorted(unknown)}", code="POLICY_UNKNOWN_FIELD")
        if scope is PolicyScope.PLATFORM:
            self._validate(schema, values)  # platform layer must be complete
        version = (
            int(
                self._s.execute(
                    select(func.coalesce(func.max(PolicyVersion.version), 0)).where(
                        PolicyVersion.policy_type == ptype,
                        PolicyVersion.scope == scope,
                        PolicyVersion.tenant_id.is_(None)
                        if tenant_id is None
                        else PolicyVersion.tenant_id == tenant_id,
                        PolicyVersion.scope_ref_id.is_(None)
                        if scope_ref_id is None
                        else PolicyVersion.scope_ref_id == scope_ref_id,
                    )
                ).scalar_one()
            )
            + 1
        )
        row = PolicyVersion(
            id=uuid.uuid4(),
            policy_type=ptype,
            scope=scope,
            tenant_id=tenant_id,
            scope_ref_id=scope_ref_id,
            version=version,
            effective_from=effective,
            values=values,
            reason=reason,
            created_by=actor.user_id,
        )
        self._s.add(row)
        self._s.flush()
        # The merged result for this scope must still validate (e.g. ordering constraints).
        self.resolve(
            ptype,
            tenant_id,
            machine_id=scope_ref_id if scope is PolicyScope.MACHINE else None,
            site_id=scope_ref_id if scope is PolicyScope.SITE else None,
            at=effective,
        )
        AuditService(self._s).record(
            actor=actor,
            action=f"policy.{ptype.value.lower()}.versioned",
            entity_type="policy_version",
            entity_id=row.id,
            tenant_id=tenant_id,
            after={"scope": scope.value, "version": version, "values": values, "effective_from": effective.isoformat()},
            reason=reason,
            policy_version=f"{_ABBR[scope]}{version}",
        )
        return row

    @staticmethod
    def _validate(schema: type[BaseModel], values: dict[str, Any]) -> None:
        try:
            schema.model_validate(values)
        except ValidationError as exc:
            raise BusinessRuleViolation(
                "Invalid policy values",
                code="POLICY_INVALID",
                details=[
                    ErrorDetail(field=".".join(str(p) for p in e["loc"]) or None, issue=e["msg"]) for e in exc.errors()
                ],
            ) from exc
