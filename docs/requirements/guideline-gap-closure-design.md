# Developer guideline gap closure (DEC-032)

Governs: `client-development-guideline.md` (Mzalendo, 2026-11-08), read with `client-accountability-requirements.md`.
Builds on DEC-030 (`accountability-design.md`) and DEC-031 (`revenue-asset-safety-design.md`). All their principles
apply: ledgers not balances; claimed ≠ confirmed; neutral wording; offline never bypasses a control; **configurable
multi-tenant SaaS** (every rule a versioned tenant policy with a platform default, approvals by permission with
proposer ≠ approver, business lists are tenant data; a client's answers are settings, not code).

Owner approved this plan on 2026-11-08 ("yes lets go"). Phases run in order 1 → 2 → 3, with 4 and 5 alongside 3 and 6
last. Each phase is finished on backend, web, Android and iOS before the next starts.

## Decisions (owner-approved)

| # | Question | Decision |
|---|---|---|
| D1 | Unexplained hours | Guideline 3.2.4 and scenario 7: never automatically wasted or billable. Shown as **value at risk** (hours × rate) and kept **out of** expected revenue and shortfall. Earlier behaviour stays selectable: `REVENUE_RECONCILIATION.unexplained_hours_treatment` gains `VALUE_AT_RISK` as the platform default (`EXPECT_REVENUE`, `EXCLUDE` remain). |
| D2 | Operators submitting readings | Managers record for operators by default. A tenant may grant operators permission to submit their own (role templates stay editable; permission-based, no role-name checks). |
| D3 | Two customers in one day | Allowed. A changeover reading closes one customer's allocation and opens the next. |
| D4 | Refunds | Approved refund exists, switchable per tenant. |

## Verified gaps this closes (code audit 2026-11-08)

**Conflict:** unexplained outside jobs priced into expected revenue; every hour inside a job window is automatically
customer work, so in-job unexplained hours cannot exist; MOBILIZATION stays billed until approved.

**Missing:** Ledger 3 for all hours (`WorkExecutionAllocation` is prepaid-only, one per job, written at completion, no
work date, start/end reading, approval, evidence); one day split across customers; per-day excavator report with
billable/unbillable/reason; single Ledger 6 with original value and resulting balance; customer-hour corrections;
refunds; reversal of posted transactions (verified payment cannot be reversed, hours stay active); supporting evidence
on transfers, credit, classifications, cash variances, adjustments; variance assignment and second-person closure; a
general customer-hour variance; approved reason for partial remittance.

**Partial:** custodian with verify permission can confirm own remittance recorded by someone else; credit activation
not checked against recorder; zero-amount purchases auto-activate; collection/remittance references optional and not
generated; collection not reliably linked to purchase; "supported by evidence" not a status; repeat daily reports not
flagged; investigation by age only; hours purchases, retentions, adjustments lack client-created time; dashboard gaps;
no employee 360 or transaction lookup; no Administrator template; Manager lacks meter approvals; Operator cannot submit;
no full tenant export; no balance verify tool; 7-day backups with optional off-host copy; reset tool not locked after
go-live; section 9 client deliverables.

## Phase 0 — Mzalendo settings (no code; owner does this in Policies)

`CUSTOMER_HOURS.default_billing_mode = PREPAID_HOURS`, `ENGINE_HOURS.baseline_required_before_start`,
`daily_report_required`, `CASH_CUSTODY.remit_full_balance`, `remittance_reference_required`,
`remittance_evidence_required`, `remittance_account_required`, `float_ack_required`.

## Phase 1 — Every engine hour allocated (3.2, 4.2, 4.3, T3, T4)

Policy additions under `ENGINE_HOURS` unless noted; all default to today's behaviour unless stated.

**A1. Work allocation ledger** (append-only, RLS, guard triggers, audited; "Ledger 3"). One entry per contiguous meter
range per machine and tenant-local work day: machine, work date, start reading ref + value, end reading ref + value,
hours, kind (`CUSTOMER_WORK` | `AUTHORIZED_ACTIVITY` | `UNEXPLAINED`), customer + job when customer work, activity
category when authorized, purchase lot(s) when prepaid (with per-lot hours), recorded by, approval ref where required,
evidence attachments, status, `supersedes_id`. Covers prepaid, invoiced and authorized activity alike.
- Written day by day from readings (scheduler sweep + on capture/sync; idempotent), not only at completion. Existing
  history is backfilled by migration from the engine ledger.
- Corrections never edit: a new entry supersedes the old; the original stays visible (4.3).
- **The database refuses overlapping allocated meter ranges** for active entries of a machine (exclusion constraint on
  a numeric range), so the same engine hours cannot be allocated twice.
- Reconciliation per machine per day: total engine hours = customer + authorized + unexplained, with the difference
  displayed.

**A2. Unexplained inside jobs.** `in_job_time_counts_as_customer_work` (default true = today) — when false, in-job hours
need a covering work-log entry; uncovered hours are UNEXPLAINED. Non-revenue activity remains governed by
`REVENUE_RECONCILIATION`.

**A3. Two customers in a day.** A **changeover reading** (job B's OPENING after job A's CLOSING, or a mid-job
changeover captured by the field recorder) closes one allocation and opens the next; allocations then show the
guideline's 6 h / 3 h / 1 h example. Offline via the existing capture op; capability announced.

**A4. Daily operational report** (a real record, append-only with superseding; policy `daily_report_required`). One per
excavator per tenant-local day: report date, opening and closing reading refs, total operating hours (derived),
billable hours, unbillable hours by reason (tenant list), customer/work allocations, evidence, submitted by, submitted
at + client-created at, review status (`SUBMITTED` → `REVIEWED` / `RETURNED`, permission-based, reviewer ≠ submitter).
Sync op `DAILY_REPORT` with capability; pre-filled from the day's readings and allocations. Web: Engine hours → Daily
reports; apps: Supervisor submits, Owner reviews. Missing/late reports use the existing cut-off flags.

**A5. Value at risk (D1).** Add `VALUE_AT_RISK` and make it the platform default; unexplained hours and their value
appear on the daily sheet, reconciliation and dashboard as a separate line, never in expected or shortfall.

**A6. Unusual readings and thresholds.** `unexplained_flag_amount_hours` (cumulative per machine, default null): opens
the investigation by amount as well as age. Repeat DAILY report for the same machine-day is flagged as a duplicate
(`DUPLICATE_DAILY_REPORT`). A decrease is labelled as a possible meter reset.

## Phase 2 — Corrections (T7, 4.6)

**B1. Adjustments ledger** (append-only "Ledger 6"): original transaction type + id + reference, adjustment type, original
value, new value or amount, reason (tenant list), evidence, requester, approver, timestamps, resulting balance. Existing
approval flows (transfers, corrections, write-offs, credit, classifications, custody adjustments, unbillable approvals)
post to it. Web: Finance → Adjustments ledger (all types, filters, drill-down).
**B2. Customer-hour corrections:** propose/approve ± hours against a lot with reason and evidence; new ledger entry type.
**B3. Refunds (D4):** policy `CUSTOMER_HOURS.refund_allowed`; approved refund of unused activated hours, with a money
record and resulting balances.
**B4. Reversal of posted transactions:** propose/approve reversal of a verified payment, collection or purchase. A
bounced payment deactivates unused hours; used hours become money owed (receivable or case). Offsetting records only.

## Phase 3 — Independence and evidence (3.3, T6, T8)

Custodian cannot confirm own remittance (policy-independent); credit activation approver ≠ purchase recorder; zero-amount
purchases need approval; evidence attachments on transfers, credit, classifications, cash variances, adjustments
(with per-type `*_evidence_required` policy); partial remittance needs an approved reason when `remit_full_balance`;
generated unique references for collections, remittances, transfers, retentions, adjustments; remittance evidence
status (`DECLARED` / `SUPPORTED` / `CONFIRMED`); collection linked to purchase or invoice (policy `collection_link_required`);
variance assignee, explanation + evidence, second-person closure (`variance_closure_requires_second_person`, default
true for the new flow, tenant-configurable), customer-hour variance type; client-created time on purchases, retentions,
adjustments.

## Phase 4 — Management view (6, 8, 10)

All section 8 figures on the accountability dashboard, each linking to its underlying transactions (add: total hours
purchased, remaining by customer, hours by excavator, allocated, non-customer, meter discrepancies, pending reports, total
cash collected, transferred, declared, confirmed, company outstanding, disputed, shortages vs overages, all pending
adjustments and approvals, all unresolved variances). Employee 360 page. Transaction lookup by reference. Role templates:
Administrator (configuration and user access, no business approvals), Manager gains meter approvals, optional operator
reading permission (D2), Finance/Cashier stays independent.

## Phase 5 — Data protection (6, 9)

Full tenant data export (all ledgers and evidence manifest; permission-gated, audited). Balance verification tool
recomputing every balance from its records and reporting mismatches (ledger prevails). Backup retention configurable
with required off-host copy check. Reset tool refuses a tenant marked live (explicit go-live marker; override needs a
deliberate flag and is audited).

## Phase 6 — Acceptance pack (9)

End-to-end test of scenario 13; all 13 scenarios demonstrated on a test company including real phones; client-readable
architecture, ledger structure, offline-vs-central statement, list of requirements that technology cannot fully enforce,
data ownership statement, training notes.

Technology limits to disclose: fake GPS not detected; photo of a photo passes; phone clock only flagged; meter tampering
caught only where a tracker compares; phone holder not proven.
