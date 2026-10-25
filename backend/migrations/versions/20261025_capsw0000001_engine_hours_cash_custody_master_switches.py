"""DEC-030 follow-up: master switches `enabled` on the ENGINE_HOURS and CASH_CUSTODY policies (capabilities
ENGINE_HOURS and CASH_CUSTODY). Existing tenants keep today's behaviour: the platform default every tenant inherits
gains `enabled: true` as a new platform version (policy versions are immutable, so the previous platform values are
carried over unchanged and only the switch is added). Tenant layers never set it, so every existing tenant resolves
enabled = true until its owner switches a capability off.

Revision ID: capsw0000001
Revises: gaps00000001
Create Date: 2026-10-25 15:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "capsw0000001"
down_revision: str | Sequence[str] | None = "gaps00000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POLICY_TYPES = ("ENGINE_HOURS", "CASH_CUSTODY")


def upgrade() -> None:
    seeds = "\n".join(
        f"""INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from,
                                        values, reason, created_at, source)
            SELECT gen_random_uuid(), cur.policy_type, 'PLATFORM', NULL, NULL,
                   (SELECT max(version) + 1 FROM policy_version
                     WHERE policy_type = '{ptype}' AND scope = 'PLATFORM' AND tenant_id IS NULL),
                   cur.effective_from, cur.values || '{{"enabled": true}}'::jsonb,
                   'Seeded platform default: capability switch on (replaceable configuration)', now(), 'migration'
              FROM (SELECT policy_type, effective_from, values FROM policy_version
                     WHERE policy_type = '{ptype}' AND scope = 'PLATFORM' AND tenant_id IS NULL
                       AND effective_from <= now()
                     ORDER BY effective_from DESC, version DESC LIMIT 1) cur
             WHERE NOT (cur.values ? 'enabled');"""
        for ptype in POLICY_TYPES
    )
    op.execute(f"""
        SELECT set_config('app.scope', 'system', true);
        {seeds}
    """)


def downgrade() -> None:
    # The previous schemas forbid unknown fields, so the seeded platform versions go (policy versions are otherwise
    # immutable: the guard trigger is paused for this one statement). Tenant versions naming `enabled` stay.
    types = ", ".join(f"'{t}'" for t in POLICY_TYPES)
    op.execute(f"""
        SELECT set_config('app.scope', 'system', true);
        ALTER TABLE policy_version DISABLE TRIGGER trg_policy_version_immutable;
        DELETE FROM policy_version
         WHERE policy_type IN ({types}) AND scope = 'PLATFORM' AND source = 'migration'
           AND reason LIKE 'Seeded platform default: capability switch on%';
        ALTER TABLE policy_version ENABLE TRIGGER trg_policy_version_immutable;
    """)
