"""DEC-032 Phase 4: a credit arrangement's evidence can be changed while it is still only proposed, like its other
terms. Once decided it stays immutable.

Revision ID: dec32p4mgt01
Revises: dec32p5dat01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "dec32p4mgt01"
down_revision: str | Sequence[str] | None = "dec32p5dat01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DENY = (
    "RAISE EXCEPTION 'asseta: % on % is not permitted', TG_OP, TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege'"
)


def _guard(proposed_mutable: str) -> str:
    return f"""
        CREATE OR REPLACE FUNCTION guard_hours_proposal() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE mutable text[];
        BEGIN
          IF TG_OP = 'DELETE' THEN {DENY}; END IF;
          IF OLD.status = 'PROPOSED' AND NEW.status = 'PROPOSED' THEN
            mutable := ARRAY[{proposed_mutable}];
          ELSIF OLD.status = 'PROPOSED' AND NEW.status IN ('APPROVED', 'REJECTED', 'WITHDRAWN') THEN
            mutable := ARRAY['status','decided_by','decided_at','decision_note','version'];
          ELSIF OLD.status = 'APPROVED' AND NEW.status = 'REVOKED' THEN
            mutable := ARRAY['status','revoked_by','revoked_at','revoke_reason','version'];
          ELSE
            RAISE EXCEPTION 'asseta: % -> % is not permitted on %', OLD.status, NEW.status, TG_TABLE_NAME
              USING ERRCODE = 'insufficient_privilege';
          END IF;
          IF (to_jsonb(NEW) - mutable) IS DISTINCT FROM (to_jsonb(OLD) - mutable) THEN
            RAISE EXCEPTION 'asseta: decided terms are immutable' USING ERRCODE = 'insufficient_privilege';
          END IF;
          RETURN NEW;
        END $$;
    """


TERMS = "'percent','limit_amount','effective_from','effective_to','terms','reason','reason_code_id','version'"


def upgrade() -> None:
    op.execute(_guard(f"{TERMS},'evidence_attachment_ids'"))


def downgrade() -> None:
    op.execute(_guard(TERMS))
