# Machine reports, credit invoices and the fuel switch: API for the web and phone apps (ADR-008)

Server side of [ADR-008](adr/ADR-008-machine-reports-replace-jobs.md) §1–§4 (§8 below lists everything §4 removed). The OpenAPI contract
(`contracts/openapi.json`) is authoritative for every field; this page is the working summary with the rules,
error codes and offline operations. All paths are under `/api/v1/tenant` with the usual `Authorization` and
`X-Tenant-ID` headers. Hours and money are decimal strings. Errors use the standard envelope
`{"error": {"code", "message", "correlation_id", "details"}}`: 422 business rule, 404 not found, 403 permission,
409 version/duplicate conflicts.

## Permissions and role templates

| Permission | Meaning | Templates |
|---|---|---|
| `tenant.machine_report.submit` | Submit reports on machines assigned to you | supervisor, manager, owner |
| `tenant.machine_report.read` | Read reports, report status, tracker cross-check | supervisor (own/assigned), accountant, manager, owner |
| `tenant.machine_report.approve` | Approve / reject (never your own), report on any machine | manager, owner (a decision permission) |
| `tenant.hours.invoice_payment` | Record payments of credit invoices | supervisor, accountant, manager, owner |
| `tenant.meter.reasons` | Edit the machine-report reason list | administrator, owner |

Approval is by permission, never by role, and the person who submitted a report never decides it
(`SEGREGATION_OF_DUTIES`).

## Company settings (tenant policy)

| Policy . key | Default | Meaning |
|---|---|---|
| `CUSTOMER_HOURS.field_credit_sales` | `false` | Field staff may record a CREDIT line. Holders of `tenant.hours.credit_activate` always may. |
| `CUSTOMER_HOURS.field_noncash_payments` | `false` (exists) | Field staff may record BANK / MOBILE_MONEY lines and invoice payments. |
| `CUSTOMER_HOURS.report_hours_scope` | `CUSTOMER` | Hours a report draws on: `CUSTOMER` = any of the customer's hours; `MACHINE` = only the customer's hours on the reported machine. |
| `CUSTOMER_HOURS.machine_report_reminder_days` | `3` | Remind approvers about a machine that moved (meter or tracker) with no report for this many days; `null` = off. |
| `EXPENSE_CAPTURE.fuel_enabled` | `true` | Fuel on/off (§3). |

Retired settings (jobs, contracts, hire invoices, site check-ins and job revenue differences are gone): stored
versions that carry them still resolve (the keys are ignored); new versions setting them get `POLICY_UNKNOWN_FIELD`.
The full list is in §8.

## 1. Orders with a CREDIT line and credit invoices

### Recording an order — `POST /hours-purchases` (unchanged path)

`payments[]` lines now take `method` `CASH | BANK | MOBILE_MONEY | CREDIT`:

```json
{
  "customer_id": "…", "machine_id": "…", "hours": "10", "client_id": "…",
  "payments": [
    {"method": "CASH", "amount": "340000", "received_at": "2026-11-16T08:00:00Z"},
    {"method": "MOBILE_MONEY", "amount": "170000", "reference": "QK12AB34", "received_at": "…",
     "evidence_attachment_ids": ["…"]},
    {"method": "CREDIT", "amount": "340000"}
  ]
}
```

- CREDIT: amount only (no reference, no `received_at`), at most one line, registered customers only.
- Lines may not add up to more than the order amount (`PAYMENTS_EXCEED_TOTAL`). A single line without `amount` is the
  whole order (also for CREDIT).
- The `job` field ("Book the job") is removed and ignored if sent.
- Response (`HoursPurchaseDto`) adds `credit_amount` and `credit_invoice`
  `{id, invoice_number, amount, paid, balance, due_date, status, overdue, rejection}` (both null without a CREDIT
  line), `credit_status` (`AWAITING_ACTIVATION | ACTIVATED | REJECTED`, null without a CREDIT line) and
  `credit_rejection` `{rejected_at, rejected_by, rejected_by_name, reason, hours, amount}` (null unless REJECTED).
  Order `status` adds `CREDIT_REJECTED` (the whole order was on credit and the credit was rejected).
- Credit makes no hours usable: the credit part waits for `POST /hours-purchases/{id}/credit-activations` (existing,
  `tenant.hours.credit_activate`, within the customer's credit arrangement, never by the order's recorder).

| Code | HTTP | When |
|---|---|---|
| `CREDIT_SALES_NOT_ALLOWED` | 403 | Field user, `field_credit_sales` off |
| `CREDIT_NOT_ALLOWED` | 422 | Tenant switched credit off (`credit_allowed` / activation basis) |
| `WALK_IN_NO_CREDIT` | 422 | Walk-in customer (new or existing) |
| `PAYMENTS_EXCEED_TOTAL` | 422 | Lines above the order amount |
| `VALIDATION_FAILED` | 422 | Two CREDIT lines; a money line without `received_at`; BANK/MOBILE_MONEY without reference |

### Credit invoices

The order's CREDIT line is invoiced automatically: `CI-<yyyy>-<nnnnn>` (per tenant), hours = credit amount / the
order's effective rate, `due_date` = tenant-local day of the sale + the customer's `payment_terms_days`. Paid orders get
no invoice. Status (derived): `UNPAID`, `PART_PAID`, `PAID`, `CANCELLED` (its order was cancelled or its credit was
rejected, §1 "Rejecting credit"; `rejection` then carries who, when and why). `overdue` /
`days_overdue`: due date passed with a balance. Recorded payments count (claimed or verified) until rejected or
reversed; `paid_verified` is the verified part.

- `GET /credit-invoices` — `listCreditInvoices`; query `q` (invoice/order number, customer), `customer_id`,
  `purchase_id`, `status`, `overdue=true|false`, `date_from`/`date_to` (issue day), `page`, `page_size`.
  Permission `tenant.hours.read`.
- `GET /credit-invoices/{id}` — `getCreditInvoice`, with `payments[]`
  `{id, payment_id, amount, method, reference, collection_number, payment_status, received_at, received_by_staff_id,
  received_by_staff_name, recorded_by, recorded_by_name, created_at, counts}`.
- `POST /credit-invoices/{id}/payments` — `recordCreditInvoicePayment` (201, returns the invoice), permission
  `tenant.hours.invoice_payment`, `Idempotency-Key` supported:

```json
{"client_id": "…", "amount": "170000", "method": "CASH | BANK | MOBILE_MONEY", "reference": "required for BANK/MOBILE_MONEY",
 "received_at": "…", "staff_member_id": "optional cash custodian", "note": "…", "evidence_attachment_ids": []}
```

CASH goes into the recorder's (or named custodian's) cash custody like any collection (`COL-…` number); BANK /
MOBILE_MONEY stay claimed until verified (`PAY-…`). Every payment is also linked to the order, so verified money
activates the order's hours and settles the customer's credit exposure. The tenant's `cash_activation` applies to the
cash.

| Code | HTTP | When |
|---|---|---|
| `INVOICE_NOT_FOUND` | 404 | |
| `INVOICE_OVERPAYMENT` | 422 | Amount above the balance |
| `INVOICE_PAID` | 422 | Nothing left to pay |
| `INVOICE_CANCELLED` | 422 | The order was cancelled or its credit was rejected |
| `PAYMENT_NOT_PERMITTED` | 403 | BANK/MOBILE_MONEY by field staff while `field_noncash_payments` is off |
| `STAFF_NOT_LINKED`, `NOT_CUSTODIAN` | 4xx | Cash custody rules (as for collections) |

### Customer hours

Orders whose credit part waits for approval: `GET /hours-purchases?queue=CREDIT_TO_ACTIVATE` (open orders with a
credit invoice whose credit was not rejected and hours not yet activated; the credit approvers' queue,
`POST /hours-purchases/{id}/credit-activations` approves, `POST /hours-purchases/{id}/credit/reject` rejects). `queue=AWAITING_ACTIVATION` lists every order with hours awaiting activation (cash or bank waiting for
verification included); `UNPAID` / `UNCONFIRMED` narrow it by payment state.

### Rejecting credit — `POST /hours-purchases/{id}/credit/reject` (`rejectHoursCredit`)

Owner decision: next to approving (activating) the credit part, a credit approver may reject it. Permission
`tenant.hours.credit_activate`; never the person who recorded the sale. Body `{"reason": "…"}` (required, 3–1000
characters). `Idempotency-Key` supported. Returns the order (`HoursPurchaseDto`).

Effect:
- The credit part is REJECTED (`credit_status`, `credit_rejection`: who, when, reason). The credit hours are never
  activated and no longer count as awaiting activation; the order leaves `queue=CREDIT_TO_ACTIVATE`.
- Its credit invoice becomes `CANCELLED` (reason kept in `rejection`, balance 0): still listed (`status=CANCELLED`),
  never overdue, excluded from what the customer owes (customer balance and statement, `credit_owed`, open
  receivables, reports' open amounts) and from `open_credit_invoices` on phones. Payments on it are refused
  (`INVOICE_CANCELLED`). The credit amount is no longer counted as sold (`sales_collections`) nor as bought hours
  (`customer_hours`).
- Paid parts of the order stay unchanged; if the rejected credit was all that held them back (no partial activation),
  their verified money activates their hours now.
- Audit `hours.credit_rejected` (reason); event `HoursCreditRejected`; notification `HOURS_CREDIT_REJECTED` to the
  seller: "Credit for {customer} was not approved: {reason}".
- A rejection is final (single database stamp); credit activation on that order is refused afterwards
  (`CREDIT_REJECTED`).

| Code | HTTP | When |
|---|---|---|
| `NO_CREDIT_PART` | 422 | The order has no CREDIT line |
| `CREDIT_NOT_AWAITING` | 422 | Hours of the order were already activated on credit, or the credit was already rejected |
| `CREDIT_INVOICE_HAS_PAYMENTS` | 422 | Payments are recorded on the credit invoice (rejected or reversed payments do not count) |
| `PURCHASE_CANCELLED` | 422 | The order is cancelled |
| `SEGREGATION_OF_DUTIES` | 422 | The caller recorded the sale |
| `VALIDATION_FAILED` | 422 | Reason missing or shorter than 3 characters |

### Customer hours summary

`GET /customer-hours?customer_id=` — `listCustomerHours`: per customer `{customer_id, customer_name, bought, activated,
used, left, awaiting_activation, credit_owed}`.

## 2. Machine reports

### Submit — `POST /machine-reports` (`submitMachineReport`, 201)

Permission `tenant.machine_report.submit`. `Idempotency-Key` supported; `id` makes retries safe.

```json
{
  "id": "device-generated uuid (optional online)",
  "machine_id": "…",
  "capture": {
    "id": "device-generated reading id", "kind": "DAILY", "machine_id": "…",
    "capture_mode": "AUTOMATIC | MANUAL", "reading": "1005.0",
    "ocr_raw_text": "…", "ocr_value": "1005.0", "ocr_confidence": 0.97, "ocr_engine": "mlkit-text-v2@android",
    "photo_attachment_id": "…",
    "gps": {"status": "FIX", "latitude": -6.8, "longitude": 39.28, "accuracy_m": 8, "captured_at": "…", "provider": "fused"},
    "device_id": "…", "captured_at": "…", "policy_version_ids": []
  },
  "lines": [
    {"kind": "CUSTOMER", "customer_id": "…", "hours": "4.0"},
    {"kind": "NON_PRODUCTIVE", "reason_id": "…", "hours": "1.0", "note": "Moved to the second site"}
  ],
  "note": "optional",
  "client_created_at": "device time"
}
```

- The reading: give `capture` (a new DAILY reading, same shape and evidence rules as `POST /meter-captures`) **or**
  `capture_id` (a reading already recorded, e.g. with `POST /meter-captures` or the sync operation `METER_CAPTURE` just
  before). To correct a rejected report send `capture_id` = its reading and `corrects_report_id` = the rejected report.
- **Opening report** (`"opening": true`, `"lines": []`): a machine with no starting reading yet (no approved report,
  no approved baseline: `opening_required: true` in its status/context, `previous_reading` null) gets an opening report
  first. It carries only the reading (difference 0, `hours` 0, `start_source` `OPENING`, `start_reading` =
  `end_reading` = the reading). It is approved or rejected like any report (approval consumes nothing and writes no
  allocations); once approved its reading is where the next report starts. Neither the ENGINE_HOURS capability nor a
  meter baseline is needed for machine reports.
- The phones send a report as two operations: a normal DAILY `METER_CAPTURE` (the reading, with its photo/OCR/GPS),
  then `MACHINE_REPORT` with `capture_id` = that reading (an opening report: `opening: true`, `lines: []`; a normal
  report: `opening` absent or false, with lines). REST accepts exactly the same body. DAILY readings are accepted
  whatever the tenant's ENGINE_HOURS switch.
- Previous reading = end of the machine's last APPROVED report, else its approved meter baseline; an approved meter
  reset after that restarts the count at the reset's new reading. Difference = new − previous.
- Lines (a normal report: at least one): CUSTOMER (`customer_id`, `hours` > 0) or NON_PRODUCTIVE (`reason_id` from the reason list, `hours` > 0,
  `note` required). One line per customer. Hours in steps of the machine's meter precision (0.1 for one decimal).
  Sum of lines == difference exactly.
- Each customer's hours ≤ available = activated − used − reserved by other SUBMITTED reports (scope per
  `report_hours_scope`). The submitted report reserves them.
- One SUBMITTED report per machine; one SUBMITTED/APPROVED report per reading.
- Meter vs tracker: when the machine's tracker has an engine-hour counter at both ends of the report's period and the
  meter moved more or less than it beyond `METER_CAPTURE.telemetry_engine_hours_tolerance`, the report's reading gets
  a `TELEMETRY_MISMATCH` finding (evidence for the approver, shown in `findings`; it does not hold the reading).

Response `MachineReportDto`: `id, report_number (MR-yyyy-nnnnn), machine_id, machine_code, machine_name, capture_id,
opening, start_source (REPORT|BASELINE|RESET|OPENING), start_ref, start_reading, start_at, end_reading, end_at, hours, customer_hours,
non_productive_hours, status (SUBMITTED|APPROVED|REJECTED), corrects_id, corrected_by_id, note, source (API|SYNC),
submitted_by(_name), submitted_at, client_created_at, decided_by(_name), decided_at, decision_note, policy_version,
photo_attachment_id, capture_state, findings[], tracker, lines[]`. Lines: `id, line_no, kind, customer_id,
customer_name, reason_id, reason_code, reason_name, hours, note, available_hours (SUBMITTED detail), lots[]
(APPROVED: {purchase_id, purchase_number, machine_id, hours})`.

`submitted_by` and `decided_by` are app user ids: the same id `GET /api/v1/me` returns as `user_id` (compare them to
tell "my reports"; `mine=true` on the list filters on it server side).

| Code | HTTP | When |
|---|---|---|
| `MACHINE_NOT_FOUND` | 404 | |
| `MACHINE_NOT_ASSIGNED` | 422 | Caller is not the machine's open SUPERVISOR assignment and lacks `…approve` |
| `REPORT_PENDING` | 422 | The machine has a SUBMITTED report |
| `OPENING_REPORT_REQUIRED` | 422 | The machine has no starting reading yet and the report is not an opening report |
| `OPENING_NOT_ALLOWED` | 422 | `opening: true` but the machine already has a starting reading |
| `READING_NOT_HIGHER` / `NOTHING_TO_REPORT` | 422 | New reading below / equal to the previous |
| `REPORT_SUM_MISMATCH` | 422 | Lines ≠ difference |
| `HOURS_PRECISION` | 422 | Hours not in the meter's steps |
| `DUPLICATE_CUSTOMER_LINE` | 422 | A customer twice |
| `HOURS_NOT_AVAILABLE` | 422 | A customer's total above their available hours |
| `CUSTOMER_NOT_FOUND`, `REASON_NOT_FOUND` | 404 | |
| `REASON_INVALID` | 422 | Not an active machine-report reason |
| `CAPTURE_NOT_FOUND` / `CAPTURE_MACHINE_MISMATCH` / `CAPTURE_REJECTED` | 404/422 | Bad `capture_id` / reading refused by evidence rules |
| `CAPTURE_ALREADY_REPORTED` | 422 | The reading has a SUBMITTED/APPROVED report |
| `CORRECTS_INVALID` | 422 | `corrects_report_id` is not a rejected report of this machine on the same reading |
| `REPORT_ID_CONFLICT` | 409 | `id` reused with another machine/reading |
| `HOURS_DISABLED` | 422 | Customer lines while customer hours are switched off |
| `VALIDATION_FAILED` | 422 | Shape (both/neither of capture and capture_id, missing note, lines on an opening report, no lines on a normal one, …) |

### Read

- `GET /machine-reports` — `listMachineReports`; `q` (number / machine), `machine_id`, `status`, `queue=PENDING`
  (approval queue), `customer_id`, `mine=true`, `date_from`/`date_to` (submission day). Field users see their own
  reports and those on machines assigned to them; holders of `…approve` (or `tenant.finance.report`) see all.
- `GET /machine-reports/{id}` — detail with `findings` (the reading's review findings) and `tracker`
  `{available, tracker_hours, meter_hours, difference (meter − tracker), tracker_from_at, tracker_to_at}` from the
  tracker's engine-hour counter over the report period.
- `GET /machine-reports/status?machine_id=…` — `listMachineReportStatus`: per machine (field users: assigned ones)
  `{machine_id, machine_code, machine_name, meter_decimal_places, previous_reading, previous_at, previous_source,
  opening_required, last_approved_reading, last_approved_at, last_report_at, days_since_report, pending_report_id,
  pending_report_number, rejected_report_id}`.
- `GET /machine-reports/context/{machine_id}` — `getMachineReportContext` (submit or approve permission): the form's
  first step `{previous_reading, previous_at, previous_source, opening_required, meter_epoch, meter_decimal_places,
  pending_report_id,
  last_report_at, hours_scope, customers[] (available hours > 0), reasons[]}`.
- `GET /machine-reports/available-hours?machine_id=&customer_id=…` — `listReportHours`:
  `{customer_id, machine_id (MACHINE scope), remaining, reserved, available}`.

### Decide (permission `tenant.machine_report.approve`, never your own)

- `POST /machine-reports/{id}/approve` `{"note": "optional"}` — consumes the customers' hours from their orders oldest
  activated first (hours ledger `CONSUMED`, `machine_report_id` set), writes the allocation ledger (one entry per line
  over the meter range: `CUSTOMER_WORK` with lots, `AUTHORIZED_ACTIVITY` with the reason; source `MACHINE_REPORT`,
  superseding derived entries of that range) and makes the reading the machine's last approved one. Open
  `UNEXPLAINED_HOURS` engine-hour flags of the machine that lie inside the report's period are closed as EXPLAINED
  ("Accounted for by machine report MR-…", reviewer = the approver); they stay open while the report waits or after a
  rejection.
- `POST /machine-reports/{id}/reject` `{"reason": "…"}` — releases the reservation; the supervisor corrects it on the
  same reading.

| Code | HTTP | When |
|---|---|---|
| `REPORT_NOT_FOUND` | 404 | |
| `REPORT_NOT_PENDING` | 422 | Already decided |
| `SEGREGATION_OF_DUTIES` | 422 | Deciding your own report |
| `REPORT_READINGS_CHANGED` | 422 | The machine's previous reading changed since submission (baseline/reset; for an opening report: the machine got a starting reading meanwhile): reject it |
| `HOURS_NOT_AVAILABLE` | 422 | A customer's hours are no longer there (cancelled, expired): reject it |

### Reason list (kind `NON_PRODUCTIVE` of the engine-hour reason table)

`GET /machine-report-reasons?include_inactive=` (`listMachineReportReasons`; submit, read or reasons permission),
`POST /machine-report-reasons` `{code, name, description?}`, `PUT /machine-report-reasons/{id}`
`{code, name, description?, version}`, `POST …/{id}/deactivate|reactivate` `{reason, version}` (`tenant.meter.reasons`).
Defaults for every company: `TRANSIT` Transit between sites, `BREAKDOWN` Breakdown / repair, `SERVICING` Servicing,
`IDLE_ON_SITE` Idle on site, `WAITING_CUSTOMER` Waiting for customer, `WEATHER` Weather (new companies at onboarding;
existing ones: `scripts/seed-machine-report-reasons.sh [--yes]`, idempotent).

## 3. Offline (sync protocol 1)

New capability strings in `bootstrap` / `changes` `capabilities` (announced only while customer hours are on, except
`OP_MACHINE_REPORT` which is always announced):

| Capability | What it means |
|---|---|
| `OP_MACHINE_REPORT` | Operation `MACHINE_REPORT`; `SyncData.machine_report_*` and `my_machine_reports` |
| `OP_CREDIT_INVOICE_PAYMENT` | Operation `CREDIT_INVOICE_PAYMENT`; `SyncData.open_credit_invoices` |
| `OP_HOURS_SALE_CREDIT` | `HOURS_PURCHASE` accepts a CREDIT payment line |
| ~~`OP_HOURS_SALE_BOOKING`~~ | Removed ("Book the job") |

### `MACHINE_REPORT` (permission `tenant.machine_report.submit`)

Payload = the submit body above without `id` (the **operation id is the report id**; `client_created_at` is taken
from `created_at_device`), plus optional `photo_upload_id` (resumable blob upload, purpose `METER_PHOTO`; the op is
`DEFERRED` with `ATTACHMENT_PENDING` until it completes, then becomes the reading's photo). Acked result:
`{"entity": MachineReportDto}`. A replay returns `DUPLICATE` with the same entity.

Kept for review as `CONFLICT` (the reading was taken in the field): `MACHINE_NOT_ASSIGNED`, `MACHINE_NOT_FOUND`,
`REPORT_PENDING`, `REPORT_ID_CONFLICT`, `OPENING_REPORT_REQUIRED`, `READING_NOT_HIGHER`, `NOTHING_TO_REPORT`,
`REPORT_SUM_MISMATCH`, `HOURS_NOT_AVAILABLE`, `HOURS_DISABLED`, `REASON_INVALID`, `REASON_NOT_FOUND`,
`CUSTOMER_NOT_FOUND`, `CAPTURE_REJECTED`, `CAPTURE_ALREADY_REPORTED`, `CORRECTS_INVALID`. `REJECTED`:
`HOURS_PRECISION`, `DUPLICATE_CUSTOMER_LINE`, `VALIDATION_FAILED`, `BAD_PAYLOAD`, `PERMISSION_DENIED`.

The phone checks the sum and its cached available hours before queueing; the server decides. `OPENING_NOT_ALLOWED`
is `REJECTED` (another report gave the machine its start meanwhile: send a normal report on the same reading).
`METER_DAILY_READING` (DAILY `METER_CAPTURE`) is always announced (no longer tied to ENGINE_HOURS).

### `CREDIT_INVOICE_PAYMENT` (permission `tenant.hours.invoice_payment`)

```json
{"invoice_id": "…", "amount": "85000", "method": "CASH", "reference": null, "received_at": "…",
 "staff_member_id": null, "note": null, "evidence_attachment_ids": [], "evidence_upload_ids": []}
```

The **operation id is the payment's client id**. `evidence_upload_ids`: blob uploads (purpose `PAYMENT_EVIDENCE`).
Acked result: `{"entity": CreditInvoiceDto}`. Money operation: refusals caused by state that moved (`INVOICE_PAID`,
`INVOICE_OVERPAYMENT`, `INVOICE_CANCELLED`, `INVOICE_NOT_FOUND`, custody codes) are
`CONFLICT`, never lost.

### `HOURS_PURCHASE` with a CREDIT line

As online; refusals `CREDIT_SALES_NOT_ALLOWED`, `CREDIT_NOT_ALLOWED`, `WALK_IN_NO_CREDIT`, `PAYMENTS_EXCEED_TOTAL`,
are `CONFLICT` (money changed hands); `PAYMENT_NOT_PERMITTED` stays `REJECTED`. The acked entity carries `credit_amount` and
`credit_invoice`.

### Snapshots in `SyncData` (full snapshots on every bootstrap and delta — replace the local sets)

| Field | Sent to | Content |
|---|---|---|
| `machine_report_reasons` | `…submit` holders | Active reasons `{id, code, name, description, is_active, version}` |
| `machine_report_states` | `…submit` holders | `MachineReportStatusDto` of the caller's machines (open SUPERVISOR assignment) |
| `machine_report_hours` | `…submit` holders | `AvailableHoursDto` with `customer_name`, customers with available > 0 (per machine when scope is MACHINE) |
| `my_machine_reports` | `…submit` holders | The caller's reports of the last 30 days and any still SUBMITTED |
| `open_credit_invoices` | `…invoice_payment` holders, hours on | `CreditInvoiceDto` (no payments) with balance > 0, oldest due first; never a CANCELLED invoice (order cancelled or credit rejected) |

## 4. Fuel switch (§3)

`EXPENSE_CAPTURE.fuel_enabled = false`:
- `/api/v1/me` lists `FUEL` in `disabled_capabilities`; menu `tenant.field.fuel` disappears and `tenant.expenses` is
  labelled "Expenses".
- `POST/GET /fuel-events` → 422 `FUEL_DISABLED`; sync `FUEL_EVENT` → `CONFLICT FUEL_DISABLED`; `my_fuel_events` is
  empty.
- No fuel checks (fuel allowance, machine fuel norm), no fuel efficiency insights, no fuel line in profitability, no
  fuel in the revenue daily sheet. Recorded fuel is kept, hidden.

## 5. Menus (backend definitions)

| Key | Label | Path | Group | Permission |
|---|---|---|---|---|
| `tenant.approvals.machine_reports` | Machine reports | `/tenant/machine-reports` | Approvals (`tenant.approvals`, new) | `tenant.machine_report.read` |
| `tenant.field.machine_report` | Machine report | `/tenant/field/machine-report` | Field work | `tenant.machine_report.submit` |
| `tenant.hours.credit_invoices` | Credit invoices | `/tenant/hours/credit-invoices` | Customer hours | `tenant.hours.read` |
| `tenant.machine_report_reasons` | Machine report reasons | `/tenant/machine-report-reasons` | Administration | `tenant.meter.reasons` |

## 6. Notifications

| Type | To | When |
|---|---|---|
| `MACHINE_REPORT_SUBMITTED` | `tenant.machine_report.approve` | A report waits for a decision (link `/tenant/machine-reports/{id}`) |
| `MACHINE_REPORT_APPROVED` / `MACHINE_REPORT_REJECTED` | the submitter | Decision (rejection carries the reason) |
| `HOURS_CREDIT_TO_ACTIVATE` | `tenant.hours.credit_activate` | An order with a CREDIT line (link to the order) |
| `HOURS_CREDIT_REJECTED` | the seller (who recorded the sale) | Its credit was rejected: "Credit for {customer} was not approved: {reason}" (link to the order) |
| `CREDIT_INVOICE_OVERDUE` | `tenant.finance.payment`, `tenant.hours.credit_activate` | Once per invoice past its due date |
| `MACHINE_REPORT_MISSING` | `tenant.machine_report.approve` | Daily while a machine moved with no report for `machine_report_reminder_days` |

Notification `data.kind` for links: `MACHINE_REPORT`, `CREDIT_INVOICE`, `HOURS_PURCHASE`.

## 7. Reports (`GET /reports/{code}.csv|.pdf`)

`customer_hours` (bought / activated / used / left / awaiting / credit owed), `machine_hours` (approved report hours
per machine: customer work and each reason, with share), `sales_collections` (sold by payment line and collected by
method in the period), `credit_invoices`, `credit_invoice_payments`; cash per supervisor is the existing `cash`
report.

## 8. Removed by ADR-008 §4 (all tenants)

Database migration `adr8rm01` drops the job, contract, changeover, work-execution-allocation, hire-invoice, revenue
reconciliation and site check-in tables; audit history keeps its text. Readings taken as job opening/closing readings
are kept as DAILY readings; signals and cases whose subject was a job now name its machine.

**Endpoints removed** (operationId): `createJob`, `requestJob`, `listJobs`, `getJobSummary`, `updateJob`,
`transitionJob`, `logJobActivity`, `listJobActivities`, `acknowledgeJob`, `listJobAcknowledgements`, `listJobCaptures`
(`/jobs/{id}/meter-captures`), `createContract`, `listContracts`, `getContract`, `updateContract`, `closeContract`,
`reopenContract`, `listFieldContracts`, `createHireInvoiceDraft`, `listHireInvoices`, `getHireInvoice`,
`issueHireInvoice`, `voidHireInvoice`, `allocateCustomerPayment`, `listWorkExecutionAllocations`,
`getWorkExecutionAllocation`, `listUnbilledWork`, `recordSiteCheckin`, `getMySiteCheckins`, `listSiteCheckins`,
`getSiteCheckin`, `listDailyMachineSheet`, `exportDailyMachineSheetCsv`, `getDailyMachineSheetDay`,
`listRevenueDifferences`, `getRevenueDifference`, `explainRevenueDifference`, `decideRevenueDifference`,
`listRevenueReasons`, `getRevenueReason`, `createRevenueReason`, `updateRevenueReason`, `deactivateRevenueReason`,
`reactivateRevenueReason`, `listNonRevenueActivities`, `listNonRevenueApprovals`, `getNonRevenueApproval`,
`proposeNonRevenueApproval`, `decideNonRevenueApproval`, reports `jobs.csv` / `jobs.pdf`.
**Renamed** (same paths): `listJobExceptions` → `listMeterExceptions`, `getJobException` → `getMeterException`,
`reviewJobException` → `reviewMeterException`.

**Changed endpoints and DTOs:**
- `POST/PUT /customers`: `code` is optional; left blank the server assigns the next free `CUST-<nnnnn>` (unique per
  company; on edit a blank code keeps the current one). Customer deactivation no longer checks jobs.
- `GET /field/machines`: the machines currently assigned to the caller (permission: any of
  `tenant.machine_report.submit`, `tenant.machine_report.read`, `tenant.meter.capture`).
- Meter readings (`MeterCaptureIn` / `MeterCaptureDto`): no `job_id`, `changeover_to_customer_id`,
  `changeover_to_job_id`; `kind` is only `DAILY` (default) and `machine_id` is required. `GET /meter-captures` and the
  readings report have no `job_id` filter/column. Exceptions have no `job_id`. Attachment purpose `SIGNATURE` is gone.
- Engine hours ledger: segment kinds are `REPORTED` (inside a submitted or approved machine report: `report_id`,
  `report_number`) and `UNALLOCATED`; `CUSTOMER_WORK` / `NON_REVENUE`, `job_id`, `job_number`, `activity_type`,
  `overlapping_job_ids` and `overlaps` are gone; totals have `reported_hours` instead of `customer_work_hours` /
  `non_revenue_hours`. Work allocations have no `job_id`, `job_number`, `activity_type`, `changeover_id` (filter
  `job_id` gone); daily-report allocation rows likewise. Meter corrections have no `job_id`.
- Customer hours: no `provisional` figures (daily drawdown removed); ledger entries carry `machine_report_id` /
  `machine_report_number` instead of `job_id`, `allocation_id`, `usage_day` (list filter `machine_report_id`); the
  customer statement's usage lines are per day and machine report (`machine_report_id`, `machine_report_number`; no
  `basis`, `job_running`), movement lines carry `machine_report_id`, totals have no `provisional_at_close`. Ledger
  entry types `PROVISIONAL` / `PROVISIONAL_REVERSED` are gone.
- Customer payments: no `allocations` (hire invoices) on `CustomerPaymentIn`, `CashCollectionIn` or
  `CustomerPaymentDto`. Customer balance and statement (`/customers/{id}/balance`, `/statement`) are on credit
  invoices: balance fields `invoiced, verified_payments, balance, unallocated_credit, claimed_unverified,
  open_invoices` (`reversed`, `payment_reversals_and_refunds` gone); statement line kinds `INVOICE` | `PAYMENT`.
- Adjustments: `INVOICE_VOID` requests are refused (`REQUEST_TYPE_RETIRED`); `invoice_id` gone; an hours correction
  names `machine_report_id` (was `job_id`). A reversal that leaves used hours unpaid always opens a case.
- Profitability: `group_by` `MACHINE` | `CUSTOMER` (`JOB` gone); revenue = customer hours used in approved machine
  reports x their order's effective price, dated at approval (`reversed_revenue` gone); costs are per machine (one
  "Unattributed" row when grouped by customer).
- Overview: `work.machine_reports_by_status` (was `jobs_by_status`; section needs `tenant.machine_report.read`);
  receivables are credit-invoice balances. Fleet map `reported_work_status` / overview `reported_work_state`:
  `REPORT_PENDING`, `REPORT_REJECTED`, `REPORTED`, `NOT_REPORTED` (from the machine's latest machine report).
- Idle machines (`listIdleMachines`): active machines with no approved machine-report hours for
  `OVERSIGHT.idle_after_days`; rows carry `last_machine_report_id` / `last_machine_report_number` (job fields gone).
- Scorecard: no `revenue_differences`, `revenue_difference_totals`, `checkins_missed`, `checkins_made`; records have
  no `job_id`. Accountability: approvals tile `machine_reports` (was `jobs_awaiting_approval`; `non_revenue_approvals`,
  `revenue_decisions` gone); tiles `revenue_differences` and `unbilled_work` gone; exceptions section has no
  `changeover_jobs_awaiting_approval`; lookup finds `MR-` and `CI-` numbers (not hire invoices or jobs).
- Machine retirement is refused while a machine report on it waits for a decision (`MACHINE_HAS_PENDING_REPORT`;
  `MACHINE_HAS_OPEN_JOBS` and `STAFF_HAS_ACTIVE_JOBS` gone). Site deactivation no longer checks anything.
- Onboarding checklist: steps `CUSTOMERS` (was `CUSTOMERS_AND_CONTRACTS`) and `FIRST_MACHINE_REPORT` (was `FIRST_JOB`).

**Sync:** operations `JOB_ACTIVITY`, `JOB_ACKNOWLEDGEMENT`, `JOB_TRANSITION`, `JOB_REQUEST`, `SITE_CHECKIN`;
capabilities `OP_JOB_REQUEST`, `OP_SITE_CHECKIN`, `METER_CHANGEOVER`, `SYNC_CHANGEOVER_JOBS`, `SYNC_OPEN_INVOICES`;
`SyncData.jobs`, `contracts`, `open_invoices`, `changeover_jobs`, `my_job_activities`, `my_acknowledgements`. Blob
purpose `SIGNATURE`. `SyncData.customers` now carries the company's active customers (callers holding
`tenant.customer.read`) and `sites` its active sites (bootstrap; deltas carry changes and deactivations).
`machines` are the machines assigned to the caller.

**Permissions:** `tenant.job.read`, `tenant.job.write`, `tenant.job.approve`, `tenant.job.log`,
`tenant.job.request`, `tenant.revenue.read`, `tenant.revenue.explain`, `tenant.revenue.decide`,
`tenant.site_checkin.record`, `tenant.finance.invoice` (deactivated in the catalog; role templates no longer grant
them).

**Menus:** `tenant.jobs`, `tenant.field.jobs`, `tenant.hours.allocations`, `tenant.engine_hours.daily_sheet`,
`tenant.engine_hours.non_revenue`, `tenant.revenue_differences`, `tenant.revenue_reasons`, `tenant.unbilled_work`,
`tenant.site_checkins`, `tenant.field.checkin`. `tenant.finance` is labelled "Customer payments".

**Tenant capabilities** (no longer in `disabled_capabilities`): `REVENUE_RECONCILIATION`, `UNBILLED_WORK`,
`SITE_CHECKIN`.

**Policies:** types `REVENUE_RECONCILIATION` and `HIRE_BILLING` removed (their versions are deleted by the
migration). Retired fields (ignored in stored versions, `POLICY_UNKNOWN_FIELD` in new ones):
`CUSTOMER_HOURS.walk_in_standard_contract`, `prepaid_job_auto_approval`, `billing_modes`, `default_billing_mode`,
`over_consumption`, `overrun_exception_blocking`, `drawdown`, `reversal_used_hours_treatment`;
`ENGINE_HOURS.baseline_required_before_start`, `prevent_overlapping_allocation`, `prevent_overlapping_activity`,
`in_job_time_counts_as_customer_work`, `changeover_splits_billing`; `METER_CAPTURE.opening_mode`;
`FRAUD_CONTROLS.engine_activity_min_minutes`, `authorization_tolerance_minutes`,
`engine_without_work_case_min_minutes`; `OVERSIGHT.unbilled_after_days`, `site_checkin_required`,
`site_checkin_times`, `site_checkin_window_minutes`, `site_checkin_max_distance_m`. Renamed:
`METER_CAPTURE.closing_mode` → `capture_mode` (stored versions are read under the new name; device policy snapshots
carry `capture_mode`). `OVERSIGHT.repeat_pattern_items` no longer accepts `REVENUE_DIFFERENCE` / `MISSED_CHECKIN`
(left out of stored versions). `OVERSIGHT.idle_after_days` now means "no approved machine-report hours".

**Notification types:** `JOB_AWAITING_APPROVAL`, `JOB_ASSIGNED`, `JOB_REQUEST_APPROVED`, `JOB_AUTO_APPROVAL_HELD`,
`JOB_CANCELLED`, `JOB_MISSING_READINGS`, `HOURS_OVERRUN`, `UNBILLED_WORK`, `HIRE_INVOICE_OVERDUE`,
`REVENUE_DIFFERENCE`, `NON_REVENUE_APPROVAL_REQUESTED` (stored notifications keep their text). `entity.changed` no
longer sends `job` / `hire_invoice`.

**Risk signals no longer raised:** `UNREPORTED_ENGINE_ACTIVITY`, `WORK_WITHOUT_AUTHORIZATION`,
`ENGINE_RUNNING_WITHOUT_WORK` (older signals stay readable). `FUEL_ALLOWANCE_EXCEEDED` is now judged per approved
machine report (fuel over the report's period vs its meter hours); `MACHINE_FUEL_ABOVE_NORM` evidence has no job
fields. Meter findings `OVERLAPPING_ALLOCATION`, `HOURS_OVERRUN` and `CONTINUITY_GAP` are no longer raised.
