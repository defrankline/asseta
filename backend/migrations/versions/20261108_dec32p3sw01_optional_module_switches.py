"""DEC-032: five per-company optional-module switches (all default ON).

New platform versions add OVERSIGHT.insights_enabled, .investigations_enabled, .managed_service_enabled,
TRACKING.enabled and CASH_CUSTODY.deposit_accounts_enabled = true. Tenant versions only carry what a tenant changed, so
every existing tenant stays ON until it turns one off.

Revision ID: dec32p3sw01
Revises: dec32p2adj01
Create Date: 2026-11-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "dec32p3sw01"
down_revision: str | Sequence[str] | None = "dec32p2adj01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REASON = "DEC-032 optional module switches (default on)"
PATCHES = {
    "OVERSIGHT": '{"insights_enabled": true, "investigations_enabled": true, "managed_service_enabled": true}',
    "TRACKING": '{"enabled": true}',
    "CASH_CUSTODY": '{"deposit_accounts_enabled": true}',
}


def upgrade() -> None:
    for ptype, patch in PATCHES.items():
        op.execute(f"""
            SELECT set_config('app.scope', 'system', true);
            INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from,
                                        values, reason, created_at, source)
            SELECT gen_random_uuid(), cur.policy_type, 'PLATFORM', NULL, NULL,
                   (SELECT max(version) + 1 FROM policy_version
                     WHERE policy_type = '{ptype}' AND scope = 'PLATFORM' AND tenant_id IS NULL),
                   cur.effective_from, cur.values || '{patch}'::jsonb, '{REASON}', now(), 'migration'
              FROM (SELECT policy_type, effective_from, values FROM policy_version
                     WHERE policy_type = '{ptype}' AND scope = 'PLATFORM' AND tenant_id IS NULL
                       AND effective_from <= now()
                     ORDER BY effective_from DESC, version DESC LIMIT 1) cur;
        """)


def downgrade() -> None:
    for ptype in PATCHES:
        op.execute(f"""
            SELECT set_config('app.scope', 'system', true);
            ALTER TABLE policy_version DISABLE TRIGGER trg_policy_version_immutable;
            DELETE FROM policy_version
             WHERE policy_type = '{ptype}' AND scope = 'PLATFORM' AND source = 'migration' AND reason = '{REASON}';
            ALTER TABLE policy_version ENABLE TRIGGER trg_policy_version_immutable;
        """)
