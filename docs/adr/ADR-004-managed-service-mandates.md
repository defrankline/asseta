# ADR-004 — Managed-service mandates (platform staff acting for a client)

**Status:** Accepted (DEC-018), 2026-10-21. Modelled on the platform owner's Managed Service in their other product.

## Context

Some clients ask the platform owner to run their account. Before this decision, any Keycloak tenant-group
membership let a user into a tenant, platform staff included. A platform user put in a client's group by hand had
access with no consent record, no end date, no revocation, and nothing marking their actions as the platform's.
That broke `prompt.md` §1.1, which says the platform has no ordinary access to tenant business data and that any
support access must be explicit and audited.

## Decision

### Consent and lifecycle

- A user with `platform.mandate.manage` grants a mandate (`MSM-YYYY-NNNN`) for one client. The grant records:
  - the scope:
    - `FULL`: any of the client's roles;
    - `OPERATIONS`: never roles carrying `tenant.access.*` or `tenant.managed_service.*`;
  - a start date and an optional end date;
  - the client's written consent reference, for example the signed agreement number;
  - notes.
- The mandate takes effect at once. The client's administrators see it on their **Managed service** page and in a
  console banner. Each grant also emits an outbox event; the email channel is BL-027.
- Ending:
  - the client (`tenant.managed_service.revoke`) can revoke it at any time with a reason;
  - the platform can end it with a reason;
  - both use optimistic concurrency (`version`).
- One active mandate per client, enforced by a partial unique index.
- A mandate before its start date is shown as `SCHEDULED` and one past its end date as `EXPIRED`. Neither gives
  access.

### Access, with Keycloak still authoritative

- The platform assigns named **platform staff** (members of `/platform/*` Keycloak groups) to the client's own role
  groups. An assignment adds the person to `/tenants/<id>/<role>` in Keycloak and records a `mandate_assignment`.
- **Gate:** a user is *mandate-governed* in a tenant when they hold any `/platform/*` group, or have ever held an
  assignment there. For such a user, the API honours a tenant group only if it is in the verified token **and** an
  active assignment under an **in-force** mandate grants it.
  - Keycloak membership alone never carries platform staff into a tenant (`MANDATE_REQUIRED`).
  - A revoked, ended or expired mandate is refused on the very next request (`MANDATE_ENDED`), before the token
    expires.
- Revoking or ending a mandate removes the Keycloak group memberships and closes the assignments.
- Platform staff who are already ordinary users of the client cannot be assigned. The client cannot remove mandate
  roles one by one (`MANDATE_MANAGED`); it revokes the mandate instead.
- Mandate staff never count toward the client's last-owner guard.
- Staff acting under a mandate cannot revoke it (`MANDATE_SELF_REVOKE`).
- `/me` lists a platform user's mandated clients with their mandate badge. The web switcher shows "Your tenant"
  first, then those clients, and a persistent "Acting for … under MSM-…" banner while one is active.

### Accountability

- Every `audit_event` written while acting under a mandate carries `mandate_id`. It is stamped in `AuditService`
  from the request session, so every existing audit writer is covered.
- The client's Managed service page shows:
  - the mandate itself;
  - its staff and their roles;
  - the actions taken under it.
- Maker-checker is unchanged. The approver must be a different person, so under a mandate two different platform
  staff members prepare and approve, as the meter-reset segregation-of-duties test shows.

### Database

- `managed_service_mandate` and `mandate_assignment` have FORCE RLS. The platform and system scopes write. The
  client reads its own rows and may only update them to revoke.
- Triggers make closed mandates and removed assignments immutable, freeze the mandate terms, and limit a client
  update to `ACTIVE → REVOKED`.
- The app role has no `DELETE` on either table, which the privilege audit test confirms.

## Not included

- No billing link.
- No per-site or per-unit assignment. Asseta's tenant roles are tenant-wide today; this is BL-028.
- No working-hours windows.
- No third-party (non-platform) delegates.
