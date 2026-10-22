# ADR-005 — Active notifications: rules, inbox, WebSocket push and SMS

**Status:** Accepted (DEC-022 b), 2026-10-22.

## Context

The owner wants "an active, engaging, alive system with full websocket notifications and SMS notifications on
actions to take, reminders, anomalies detections". Domain events already leave every business transaction through
the outbox and Kafka; nothing consumed them for people.

## Decision

### Pipeline

`outbox → Kafka (asseta.*) → asseta-notification-worker → rules → audience → preferences → inbox row (+ SMS
delivery) → after commit: Redis pub/sub → WebSocket gateway on every API instance`.

- **Rules** (`modules/notification/rules.py`) are code: one function per event type returns *intents* (type,
  audience, title, body, link, dedupe key, severity). The type catalog (`types.py`) is finite: category, default
  severity, default SMS, **mandatory** channels and **low-priority** flag. Rules read in the event tenant's RLS scope.
- **Audiences** resolve against the Keycloak-synced mirrors (DEC-005): tenant users by permission or role, a specific
  user, *the supervisor concerned* (machine assignment → staff record → linked login, still a tenant member), and
  platform staff by permission (new `platform_membership` mirror, reconciled with tenant memberships on every mirror
  pull and hourly by the scheduler). **Mandate-aware** (DEC-018): a user with mandate history in a tenant counts only
  through role groups assigned by an in-force mandate, exactly like the request gate. Tenant audiences never resolve
  without the event's own tenant.
- **Idempotent**: notifications are unique per `(recipient, dedupe_key)`; event keys derive from the outbox event id,
  reminder keys from rule + subject + tenant-local date. Kafka redelivery and scheduler re-runs never duplicate.
- **Preferences**: per user and type (`in_app`, `sms`), with tenant-wide defaults set by the tenant owner
  (`tenant.notification.manage`); user row > tenant default > type default. Mandatory channels cannot be disabled
  (`422 MANDATORY_CHANNEL`) and are forced on at delivery. Low-priority types send SMS only after explicit opt-in.
  If a user switches in-app off, the row is still written (for the SMS and the audit trail) but hidden from the inbox.

### Channels

- **In-app inbox** (`notification`): FORCE RLS confines rows to the recipient (`app.actor_id`) in one context (tenant
  or platform); only `read_at` may change (trigger); no DELETE grant.
- **WebSocket** `/api/v1/ws` (protocol in `docs/api.md`): Keycloak token in the first message or
  `Sec-WebSocket-Protocol` (never the URL); same membership/mandate/access-state rules as REST, re-checked every
  60 s; heartbeat, idle timeout, token expiry with re-auth on the open socket. Fan-out uses Redis pub/sub so any API
  instance delivers. Pushes are best effort: the inbox is the durable record. Besides notifications the worker pushes
  lightweight `entity.changed` events (alerts, approvals, payments, handovers, jobs, fleet positions, platform
  invoices) so open screens refresh.
- **SMS** on `asseta.core.sms` (`ConsoleSmsClient` by default; `NextSmsClient` when `ASSETA_SMS_PROVIDER=nextsms`,
  credentials only from the environment). `sms_delivery` rows (id = provider `reference`) are dispatched by the worker:
  quiet hours in tenant-local time (CRITICAL bypasses) → per-number hourly rate limit (deferral) → **tenant SMS wallet
  debit per segment** (GSM-7 160/153, UCS-2 70/67; idempotent per delivery) → send → retry with exponential backoff
  on 429/5xx/network, else `FAILED` with the debit refunded. An empty wallet gives `REFUSED_NO_CREDIT` and an in-app
  `SMS_WALLET_EMPTY` to tenant billing readers. SMS to platform staff (platform context) and to mandate staff is never
  tenant-billed. Delivery is at-least-once (a crash between send and commit re-sends the same reference).

### Reminders and anomalies

`asseta-notification-scheduler` runs every 15 min: platform invoices due soon / overdue (tenant + platform digest),
customer hire invoices overdue, supervisor cash still held after the tenant-local cutoff, approvals pending > N hours,
stale/offline trackers, subscription restriction (past due / suspension) within N days, jobs missing opening/closing
readings, low SMS wallet. Thresholds: `ASSETA_NOTIFY_*` settings. Anomalies: tracking alerts (geofence, tamper, low
power, GPS anomaly, offline), meter exceptions (`MeterExceptionRaised`), sync clock skew / quarantine
(`SyncAnomalyDetected`), refused segregation-of-duties attempts (`SegregationOfDutiesViolation`, committed in its own
transaction because the refused request rolls back).

**Gate 6 seam:** fraud/anomaly rules publish `AnomalyDetected` (`kind`, `severity`, `title`, `body`, `entity_type`,
`entity_id`, `link`, `audience_permission`) through the outbox; the existing rule turns it into notifications with no
engine change. The SoD signal is also an input for those rules.

## Consequences

- Recipients must exist in the membership mirror (Keycloak is authoritative; the mirror refreshes on role changes,
  at startup and hourly). A user added in Keycloak directly is notified after the next refresh.
- Mobile push and e-mail arrived in Gate 7 (below).
- Redis outage: in-app notifications still persist; live push resumes when Redis returns (clients re-read the inbox).

## Gate 7 addendum — PUSH and EMAIL channels

- **Routing** (`modules/notification/routing.py`): PUSH and EMAIL are chosen per *category x severity* ("configurable
  priority notifications"): user row > tenant default (`tenant.notification.manage`) > built-in (push for ACTION and
  for WARNING/CRITICAL; e-mail for CRITICAL). IN_APP and SMS keep their per-type preferences. A channel a type declares
  mandatory is forced on and its cell cannot be switched off (`422 MANDATORY_CHANNEL`); access-restriction notices
  (`SUBSCRIPTION_RESTRICTION_UPCOMING`) are always e-mailed. API: `GET/PUT /api/v1/{tenant,platform}/notification-routing`.
- **Devices**: `POST/GET/DELETE /api/v1/me/push-devices` (ANDROID/IOS, OWNER/SUPERVISOR app). With `X-Tenant-ID` the
  full tenant gate applies and the device receives only that tenant's notifications; without it the request runs in
  the self-service `user` RLS scope and the device receives every context of the user. DELETE deactivates (never
  deletes). A token re-registered later by another user (handed-over phone) belongs to that user only.
- **Token storage**: providers need the exact token, so it is stored as issued plus a SHA-256 for lookups. FORCE RLS
  confines rows to the owning user and the SYSTEM worker, the API returns only a hint, and the database relies on
  encryption at rest; application-level encryption needs a managed key (KMS) that R1 deployments do not have.
- **Delivery** (`notification_delivery`, `channel_dispatch.py`): queued in the notification transaction (one row per
  device / address), dispatched by `asseta-notification-worker` with exponential backoff
  (`ASSETA_NOTIFY_CHANNEL_*`); the delivery id is the provider reference (`apns-id`, `X-Asseta-Reference`). A provider
  "unregistered" reply (FCM `UNREGISTERED`/404, APNs 410/`BadDeviceToken`/`DeviceTokenNotForTopic`) deactivates the
  device (`PROVIDER_UNREGISTERED`). Log: `GET /api/v1/{tenant,platform}/notification-deliveries` (manage permission).
- **Providers** (environment only, console by default): `ASSETA_EMAIL_PROVIDER=console|smtp` + `ASSETA_EMAIL_*`;
  `ASSETA_PUSH_ANDROID_PROVIDER=console|fcm` (HTTP v1, service-account JSON file) and
  `ASSETA_PUSH_IOS_PROVIDER=console|apns` (token-based .p8 over HTTP/2). Key files are mounted, never committed.
  Local development can route e-mail to the Mailpit container (see `.env.example`).
