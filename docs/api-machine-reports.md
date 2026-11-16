# Machine reports, credit invoices and the fuel switch: API for the web and phone apps (ADR-008)

Server side of [ADR-008](adr/ADR-008-machine-reports-replace-jobs.md) §1–§3. The OpenAPI contract
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

Retired: `CUSTOMER_HOURS.walk_in_standard_contract` and `prepaid_job_auto_approval` ("Book the job" is gone). Stored
versions that carry them still resolve (the keys are ignored); new versions setting them get `POLICY_UNKNOWN_FIELD`.

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
  `{id, invoice_number, amount, paid, balance, due_date, status, overdue}` (both null without a CREDIT line).
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
no invoice. Status (derived): `UNPAID`, `PART_PAID`, `PAID`, `CANCELLED` (its order was cancelled). `overdue` /
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
| `INVOICE_CANCELLED` | 422 | The order was cancelled |
| `PAYMENT_NOT_PERMITTED` | 403 | BANK/MOBILE_MONEY by field staff while `field_noncash_payments` is off |
| `STAFF_NOT_LINKED`, `NOT_CUSTODIAN` | 4xx | Cash custody rules (as for collections) |

### Customer hours

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

- The reading: give `capture` (a new DAILY reading, same shape and evidence rules as `POST /meter-captures`; job-less)
  **or** `capture_id` (a reading already recorded). To correct a rejected report send `capture_id` = its reading and
  `corrects_report_id` = the rejected report.
- Previous reading = end of the machine's last APPROVED report, else its approved meter baseline; an approved meter
  reset after that restarts the count at the reset's new reading. Difference = new − previous.
- Lines: CUSTOMER (`customer_id`, `hours` > 0) or NON_PRODUCTIVE (`reason_id` from the reason list, `hours` > 0,
  `note` required). One line per customer. Hours in steps of the machine's meter precision (0.1 for one decimal).
  Sum of lines == difference exactly.
- Each customer's hours ≤ available = activated − used − reserved by other SUBMITTED reports (scope per
  `report_hours_scope`). The submitted report reserves them.
- One SUBMITTED report per machine; one SUBMITTED/APPROVED report per reading.

Response `MachineReportDto`: `id, report_number (MR-yyyy-nnnnn), machine_id, machine_code, machine_name, capture_id,
start_source (REPORT|BASELINE|RESET), start_ref, start_reading, start_at, end_reading, end_at, hours, customer_hours,
non_productive_hours, status (SUBMITTED|APPROVED|REJECTED), corrects_id, corrected_by_id, note, source (API|SYNC),
submitted_by(_name), submitted_at, client_created_at, decided_by(_name), decided_at, decision_note, policy_version,
photo_attachment_id, capture_state, findings[], tracker, lines[]`. Lines: `id, line_no, kind, customer_id,
customer_name, reason_id, reason_code, reason_name, hours, note, available_hours (SUBMITTED detail), lots[]
(APPROVED: {purchase_id, purchase_number, machine_id, hours})`.

| Code | HTTP | When |
|---|---|---|
| `MACHINE_NOT_FOUND` | 404 | |
| `MACHINE_NOT_ASSIGNED` | 422 | Caller is not the machine's open SUPERVISOR assignment and lacks `…approve` |
| `REPORT_PENDING` | 422 | The machine has a SUBMITTED report |
| `BASELINE_REQUIRED` | 422 | No approved report and no approved baseline |
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
| `VALIDATION_FAILED` | 422 | Shape (both/neither of capture and capture_id, missing note, …) |

### Read

- `GET /machine-reports` — `listMachineReports`; `q` (number / machine), `machine_id`, `status`, `queue=PENDING`
  (approval queue), `customer_id`, `mine=true`, `date_from`/`date_to` (submission day). Field users see their own
  reports and those on machines assigned to them; holders of `…approve` (or `tenant.finance.report`) see all.
- `GET /machine-reports/{id}` — detail with `findings` (the reading's review findings) and `tracker`
  `{available, tracker_hours, meter_hours, difference (meter − tracker), tracker_from_at, tracker_to_at}` from the
  tracker's engine-hour counter over the report period.
- `GET /machine-reports/status?machine_id=…` — `listMachineReportStatus`: per machine (field users: assigned ones)
  `{machine_id, machine_code, machine_name, meter_decimal_places, previous_reading, previous_at, previous_source,
  last_approved_reading, last_approved_at, last_report_at, days_since_report, pending_report_id,
  pending_report_number, rejected_report_id}`.
- `GET /machine-reports/context/{machine_id}` — `getMachineReportContext` (submit or approve permission): the form's
  first step `{previous_reading, previous_at, previous_source, meter_epoch, meter_decimal_places, pending_report_id,
  last_report_at, hours_scope, customers[] (available hours > 0), reasons[]}`.
- `GET /machine-reports/available-hours?machine_id=&customer_id=…` — `listReportHours`:
  `{customer_id, machine_id (MACHINE scope), remaining, reserved, available}`.

### Decide (permission `tenant.machine_report.approve`, never your own)

- `POST /machine-reports/{id}/approve` `{"note": "optional"}` — consumes the customers' hours from their orders oldest
  activated first (hours ledger `CONSUMED`, `machine_report_id` set), writes the allocation ledger (one entry per line
  over the meter range: `CUSTOMER_WORK` with lots, `AUTHORIZED_ACTIVITY` with the reason; source `MACHINE_REPORT`,
  superseding derived entries of that range) and makes the reading the machine's last approved one.
- `POST /machine-reports/{id}/reject` `{"reason": "…"}` — releases the reservation; the supervisor corrects it on the
  same reading.

| Code | HTTP | When |
|---|---|---|
| `REPORT_NOT_FOUND` | 404 | |
| `REPORT_NOT_PENDING` | 422 | Already decided |
| `SEGREGATION_OF_DUTIES` | 422 | Deciding your own report |
| `REPORT_READINGS_CHANGED` | 422 | The machine's previous reading changed since submission (baseline/reset): reject it |
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
`REPORT_PENDING`, `REPORT_ID_CONFLICT`, `BASELINE_REQUIRED`, `READING_NOT_HIGHER`, `NOTHING_TO_REPORT`,
`REPORT_SUM_MISMATCH`, `HOURS_NOT_AVAILABLE`, `HOURS_DISABLED`, `REASON_INVALID`, `REASON_NOT_FOUND`,
`CUSTOMER_NOT_FOUND`, `CAPTURE_REJECTED`, `CAPTURE_ALREADY_REPORTED`, `CORRECTS_INVALID`. `REJECTED`:
`HOURS_PRECISION`, `DUPLICATE_CUSTOMER_LINE`, `VALIDATION_FAILED`, `BAD_PAYLOAD`, `PERMISSION_DENIED`.

The phone checks the sum and its cached available hours before queueing; the server decides.

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
| `open_credit_invoices` | `…invoice_payment` holders, hours on | `CreditInvoiceDto` (no payments) with balance > 0, oldest due first |

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
| `CREDIT_INVOICE_OVERDUE` | `tenant.finance.payment`, `tenant.hours.credit_activate` | Once per invoice past its due date |
| `MACHINE_REPORT_MISSING` | `tenant.machine_report.approve` | Daily while a machine moved with no report for `machine_report_reminder_days` |

Notification `data.kind` for links: `MACHINE_REPORT`, `CREDIT_INVOICE`, `HOURS_PURCHASE`.

## 7. Reports (`GET /reports/{code}.csv|.pdf`)

`customer_hours` (bought / activated / used / left / awaiting / credit owed), `machine_hours` (approved report hours
per machine: customer work and each reason, with share), `sales_collections` (sold by payment line and collected by
method in the period), `credit_invoices`, `credit_invoice_payments`; cash per supervisor is the existing `cash`
report.
