"""Read-only diagnosis: what the first sync download (bootstrap) contains for one supervisor login.

Usage on the live server (from /home/asseta):
  scripts/compose-live.sh run --rm --no-deps -T -v ./backend/scripts:/app/scripts:ro --entrypoint python api \\
      /app/scripts/diag_sync_scope.py supervisor.wambura@demo.asseta.co.tz

Builds the same SyncData the phone receives (SyncService._data, no device needed) in sessions that are closed
without commit, and prints the linked staff record, jobs and machines. Changes nothing.
"""

import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.modules.fleet.models import StaffMember
from asseta.modules.identity.models import AppUser
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.scope import own_staff
from asseta.modules.sync.service import SyncService


def main(email: str) -> int:
    sm = get_sessionmaker()
    with sm() as s:  # autobegin; closing the session rolls back
        apply_scope(s, DbScope.SYSTEM, None, None)
        user = s.execute(select(AppUser).where(AppUser.email == email)).scalar_one_or_none()
        if user is None:
            print(f"no app_user with email {email}")
            return 1
        print(f"user {user.id} subject={user.keycloak_subject}")
        tenants = (
            s.execute(select(StaffMember.tenant_id).where(StaffMember.keycloak_subject == user.keycloak_subject))
            .scalars()
            .all()
        )
    if not tenants:
        print("no staff record linked to this login in any tenant")
        return 1
    for tid in tenants:
        with sm() as s:  # autobegin; closing the session rolls back
            apply_scope(s, DbScope.TENANT, uuid.UUID(str(tid)), user.id)
            ctx = RequestContext(
                user.id,
                user.keycloak_subject,
                DbScope.TENANT,
                uuid.UUID(str(tid)),
                frozenset({"supervisor"}),
                frozenset({"tenant.sync.read", "tenant.collection.record"}),
            )
            svc = SyncService(s, ctx, datetime.now(UTC))
            staff = own_staff(s, ctx)
            print(f"tenant {tid}: staff={getattr(staff, 'full_name', None)} ({getattr(staff, 'id', None)})")
            data, cursor, more = svc._data(None)
            print(f"  cursor={cursor} has_more={more}")
            print(f"  jobs={[(j.job_number, str(j.status)) for j in data.jobs]}")
            print(f"  machines={[m.asset_code for m in data.machines]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
