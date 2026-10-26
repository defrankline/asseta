"""DEC-031 Phase 2 asset safety: `anomaly_case.group_key` so the evidence of a machine running without work (tracker
engine-on without a job, unexplained meter hours outside jobs, after-hours movement) of one machine and tenant-local
day joins ONE case (S1), plus the FRAUD_CONTROLS platform default gaining `engine_without_work_case_min_minutes`,
`fuel_check_period` and `fuel_litres_per_hour_max` — all null (switched off), so every tenant keeps today's
behaviour until its owner opts in (replaceable configuration). The fuel norm may be set per machine category (new
policy scope MACHINE_CATEGORY; the scope column is a non-native enum, no DDL needed) or per machine.

The case guard trigger already freezes every column outside its mutable list, so `group_key` is immutable once a
case is opened.

Revision ID: dec31p2ast01
Revises: dec31p1rev01
Create Date: 2026-10-26 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dec31p2ast01"
down_revision: str | Sequence[str] | None = "dec31p1rev01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_KEYS = '{"engine_without_work_case_min_minutes": null, "fuel_check_period": null, "fuel_litres_per_hour_max": null}'
SEED_REASON = "Seeded platform default: DEC-031 engine-without-work and machine fuel checks off (replaceable)"


def upgrade() -> None:
    op.add_column("anomaly_case", sa.Column("group_key", sa.String(length=120), nullable=True))
    op.create_index("ix_anomaly_case_group", "anomaly_case", ["tenant_id", "group_key"])
    op.execute(f"""
        SELECT set_config('app.scope', 'system', true);
        INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from,
                                    values, reason, created_at, source)
        SELECT gen_random_uuid(), cur.policy_type, 'PLATFORM', NULL, NULL,
               (SELECT max(version) + 1 FROM policy_version
                 WHERE policy_type = 'FRAUD_CONTROLS' AND scope = 'PLATFORM' AND tenant_id IS NULL),
               cur.effective_from, cur.values || '{NEW_KEYS}'::jsonb, '{SEED_REASON}', now(), 'migration'
          FROM (SELECT policy_type, effective_from, values FROM policy_version
                 WHERE policy_type = 'FRAUD_CONTROLS' AND scope = 'PLATFORM' AND tenant_id IS NULL
                   AND effective_from <= now()
                 ORDER BY effective_from DESC, version DESC LIMIT 1) cur
         WHERE NOT (cur.values ? 'fuel_check_period');
    """)


def downgrade() -> None:
    op.execute(f"""
        SELECT set_config('app.scope', 'system', true);
        ALTER TABLE policy_version DISABLE TRIGGER trg_policy_version_immutable;
        DELETE FROM policy_version
         WHERE policy_type = 'FRAUD_CONTROLS' AND scope = 'PLATFORM' AND source = 'migration'
           AND reason = '{SEED_REASON}';
        DELETE FROM policy_version WHERE scope = 'MACHINE_CATEGORY';
        ALTER TABLE policy_version ENABLE TRIGGER trg_policy_version_immutable;
    """)
    op.drop_index("ix_anomaly_case_group", table_name="anomaly_case")
    op.drop_column("anomaly_case", "group_key")
