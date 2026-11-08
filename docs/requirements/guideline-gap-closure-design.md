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

## Phase 1 implementation notes (backend, 2026-11-08)

Decisions taken while building A1-A6; a settings change or a new phase can revisit any of them.

**A1 allocation ledger.** `work_allocation` is written from the engine ledger on every reading, job start/complete, work-log
entry and approved explanation, and by the scheduler sweep; the migration backfills history (if it cannot, the idempotent
sweep does). Machines with no approved baseline are allocated too, as their readings show. An interval over midnight is
split by wall-clock share, cumulatively rounded so ranges abut exactly. Inside one interval the order on the meter is
customer work, then non-revenue activity, then in-job unexplained hours (the meter does not say which came first). Hours
whose meter range was already allocated (a reading went down with no approved reset) are not allocated again; they stay in
the day's total and show as the difference until a correction or an approved reset resolves it, which is why the
reconciliation shows a difference rather than the database failing the reading. `meter_epoch` counts approved resets so
the exclusion constraint only compares ranges on the same meter base. Identified variances are recorded as
AUTHORIZED_ACTIVITY with their classification, so they are still explained hours. A correction stands while the ledger
piece it replaced keeps the same hours; if the readings underneath change, the ledger replaces it.

**A2.** The switch is read per job at its start, so a change never reinterprets a running job. Any timed work-log entry
counts as cover (WORK, STANDBY, DOWNTIME, MOBILIZATION; NOTE does not); a still-open entry covers up to now. Uncovered hours are
UNEXPLAINED, listed and classified like any other unexplained segment, and are not billed or drawn. Non-revenue activity stays under
`REVENUE_RECONCILIATION`.

**A3 changeover (D3).** Two paths:
1. *Job to job*, the normal path: A's CLOSING then B's OPENING (B approved after A completes, as the one-active-job rule requires). No
   new records are needed; a gap between the readings is UNEXPLAINED (the guideline's 6 h / 3 h / 1 h).
2. *Mid-job*, for when B cannot be set up in time: the field recorder takes a DAILY reading on the running job with
   `changeover_to_customer_id` (`METER_CHANGEOVER` capability; same `METER_CAPTURE` op). This writes an append-only
   `machine_changeover`, never touches the job's status, and the one-active-job-per-machine rule stands: A remains the only
   running job. From that reading on, the allocation ledger shows the hours as customer B's work (job A's id kept as the
   executing job unless billing is split, below; the changeover's id on the entry).

Billing: **unchanged by default** (`ENGINE_HOURS.changeover_splits_billing` false): job A still bills its whole opening-to-closing window,
so a tenant that leaves it off gets the ledger's truth without any change to invoices. Switched on, a changeover must name the job
that bills the hours after it (`changeover_to_job_id`, else `CHANGEOVER_JOB_REQUIRED`; it must be awaiting approval, on this machine, for
that customer, else `CHANGEOVER_JOB_INVALID`; both are sync CONFLICTs). That job stays in the approval queue while A runs, so the
one-active-job rule stands; it is approved after A completes and runs its normal opening and closing readings. Its billable hours are its own
meter hours plus the hours A gave up. A loses exactly what B gains: only billable hours move (time A's billing already deducts stays deducted),
A's invoice and drawdown and B's agree with the ledger, where those entries carry job B, and prepaid hours come from B's customer. B cannot be cancelled or moved
while it is owed those hours (`JOB_HAS_CHANGEOVER_HOURS`); correct the changeover reading first.

**A4.** Hours total comes only from the two named readings (reset-aware). Billable defaults to total minus unbillable; a declared billable
that leaves a gap is stored as `difference_hours`; billable plus unbillable above the total is refused. A second report for the same
machine-day without `supersedes_id` is kept and flagged DUPLICATE_DAILY_REPORT, never overwritten. Unbillable reasons are `EngineHourReason`
entries of the new kind `UNBILLABLE_REASON` (tenant list).

**A5.** `VALUE_AT_RISK` is now the platform default of `unexplained_hours_treatment`; a tenant that set its own value keeps it. Under it,
unexplained hours are valued at the same rate source as before and shown separately, and only there; `EXPECT_REVENUE` and `EXCLUDE` still
behave as they did.

**A6.** `unexplained_flag_amount_hours` (cumulative per machine) raises `UNEXPLAINED_ENGINE_HOURS` with `basis: AMOUNT`, once per
multiple of the amount. A METER_DECREASE finding is labelled `POSSIBLE_METER_RESET`. A repeat DAILY *reading* is not flagged
(morning and evening readings are normal); the flag is on repeat daily *reports*.

A1 approval reference: `approval_ref_type` + `approval_ref_ids` on an entry (`engine_hour_classification`, `non_revenue_approval` or
`work_allocation_correction`; a list because several approved work-log entries can fall inside one interval).

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

## Phase 2 implementation notes (backend, 2026-11-08)

**B1 Ledger 6** (`adjustment_ledger_entry`, append-only: guard trigger, no UPDATE/DELETE grant, RLS). One row per *decided*
adjustment (APPROVED, REJECTED, REVOKED; a retry of the same decided record is ignored by a unique key). Proposals still
waiting are not rows here: the new actions live in `adjustment_request` until decided; the existing flows keep their own pending
rows. Original reference, type, original/new value or amount (`unit` says hours, money or reading), tenant reason (id + label kept),
evidence, requester, approver, timestamps, resulting balance, filterable customer/machine/custodian. Posted from: hours transfers,
cancellations, credit arrangements (decided and revoked), meter corrections, allocation corrections, engine-hour classifications
(including direct ones), non-revenue approvals, cash variance resolutions and write-offs (a rejected write-off proposal is
retained), custody adjustments, invoice voids. Retentions are not posted: an approved retention changes what must be remitted, not
the custody balance (the guideline's test). Backfilled from decided records (no resulting balance is reconstructed for them).

**B1 invoice voids.** `HIRE_BILLING.invoice_void_requires_approval` (default on): the void endpoint proposes (invoice stays ISSUED,
`pending_void_request_id`) and `tenant.adjustment.decide` approves; a draft is abandoned as before. Off: voids immediately, posted
with no approver.

**B1 propose/decide.** `adjustment_request` (uniform flow; proposer != approver is never relaxable). Evidence per
`CUSTOMER_HOURS.adjustment_evidence_required` (default on, purpose `ADJUSTMENT_EVIDENCE`); reasons from the existing reason lists
(`hours_reason_code` kinds CORRECTION, REFUND, REVERSAL) under `reason_code_required`. All checks re-run at the decision; the request
shows a forecast while PROPOSED and what happened once decided. One live or approved reversal per original (unique index).

**B2 corrections.** New ledger entry types `CORRECTION_ADD` (+) / `CORRECTION_DEDUCT` (-): a lot (purchase + machine) cannot go below
zero (`HOURS_CORRECTION_NEGATIVE`) or above what was activated (`HOURS_CORRECTION_EXCEEDS_LOT`). A correction can name the consumption
it gives back (`consumed_entry_id`, `job_id`); it cannot give back more than that entry (`HOURS_CORRECTION_EXCEEDS_ENTRY`).

**B3 refunds (D4).** `CUSTOMER_HOURS.refund_allowed` (default off). Entry type `REFUNDED` (-) on unused activated hours; the value
(hours x effective rate) must be covered by verified money on the purchase. `settlement` CREDIT returns it to unallocated credit;
PAY_OUT records `payout {method, reference, staff_member_id}` (a cash payout reduces that custodian's custody). The kept part of a
partly refunded allocation is re-written as a new allocation row (no amount is edited). `financial_adjustment` carries
HOURS_REFUND_CREDIT / HOURS_REFUND_PAYOUT.

**B4 reversals.** Offsetting records only; the payment keeps status VERIFIED and receives one stamp `reversed_at` + `reversal_id` (guard
trigger allows exactly that). PAYMENT_REVERSAL (bank/mobile money) and COLLECTION_REVERSAL (cash): allocations released, a `PAYMENT_REVERSAL`
financial adjustment debits the customer so the receivable stays right, hours the money paid for come off (unused first, `REVERSAL`
entries linked to the request), hours already used become money owed per `reversal_used_hours_treatment`: RECEIVABLE (default) issues an
ordinary hire invoice with `HOURS_RECOVERY` lines (one per job; due/overdue/allocation all work as usual; no job claim, the jobs stay
prepaid); CASE opens an investigation case (subject CUSTOMER) and bills nothing. Cash custody falls by the amount
(approved `custody_adjustment`, entity customer_payment); the balance may go negative and the ledger shows it. PURCHASE_REVERSAL:
unused hours come off, money stays with the used hours it paid for, the rest returns to credit, used hours no money covers become owed;
the purchase gets its existing cancellation stamp (`cancellation_id` = the request id) and open transfer/cancellation requests are
refused. Credit-activated hours stay active after a payment reversal (their arrangement still covers them). Running jobs' provisional
hours count as used.

## Phase 3 — Independence and evidence (3.3, T6, T8)

Custodian cannot confirm own remittance (policy-independent); credit activation approver ≠ purchase recorder; zero-amount
purchases need approval; evidence attachments on transfers, credit, classifications, cash variances, adjustments
(with per-type `*_evidence_required` policy); partial remittance needs an approved reason when `remit_full_balance`;
generated unique references for collections, remittances, transfers, retentions, adjustments; remittance evidence
status (`DECLARED` / `SUPPORTED` / `CONFIRMED`); collection linked to purchase or invoice (policy `collection_link_required`);
variance assignee, explanation + evidence, second-person closure (`variance_closure_requires_second_person`, default
true for the new flow, tenant-configurable), customer-hour variance type; client-created time on purchases, retentions,
adjustments.

## Phase 3 implementation notes (backend, 2026-11-08)

**Independence.** The custodian of a remittance can never confirm it (always, even when someone else recorded it). The
person who recorded a purchase can never activate it on credit. A purchase that costs nothing (fully discounted) waits
as a `ZERO_AMOUNT_ACTIVATION` adjustment request (`CUSTOMER_HOURS.zero_amount_requires_approval`, default on).

**Evidence** is an attachment id list on hours transfers, credit arrangements, classifications, non-revenue approvals,
cash variances and custody adjustments, enforced per type (`*_evidence_required`, default off; invoice voids keep
`adjustment_evidence_required`). Evidence never confirms money by itself. Ledger 6 carries it.

**Partial remittance.** Under `remit_full_balance`, a remittance short of the balance needs a reason (tenant list kind
PARTIAL_REMITTANCE plus the words); it stays recorded, and a second person with `tenant.finance.retention_approve` decides
the reason. Confirming the money is a separate decision; a rejected reason does not reject the money.

**References** (`finance.references`, tenant counter): COL-/PAY- collections and other customer payments, RMT- remittances,
CTR- cash transfers, HTR- hours transfers, RET- retentions, CADJ- custody adjustments, ARQ- adjustment requests, ADJ- Ledger 6
entries; backfilled in tenant-local years by created time. A remittance's `reference` stays the bank's or the mobile
network's transaction reference. `collection_number` is on every customer payment: cash COL-, others PAY-.

**Remittance evidence status** is derived, never stored: DECLARED, SUPPORTED (at least one attachment), CONFIRMED
(verified by someone else; only the confirmed amount reduces custody).

**Collections** can name an hours purchase (`purchase_id`, its id or an offline client id; linked up to its open
amount, the rest stays as customer credit) as well as invoices; `collection_link_required` refuses a free-standing one.

**Variances.** Assignment is to a holder of `tenant.finance.variance` (`GET /cash/variances/assignees`), never a party.
With `variance_closure_requires_second_person` (default on) `POST .../resolution` proposes the closure (CLOSURE_PROPOSED)
and a holder of `tenant.finance.variance_close` decides; whoever opened it, proposed the closure or is a party to it can
never close it. A write-off is always a proposal when either that policy or `writeoff_requires_approval` is on. History is
append-only in `cash_variance_event`. `CUSTOMER_HOUR` variances are the same row shape (unit HOURS, figures in hours,
closed as EXPLAINED or CORRECTED_ERROR); the sweep (`CUSTOMER_HOURS.variance_sweep_enabled`) compares purchases, ledger
consumption and work allocations, opens one per mismatch and does not reopen one already closed with the same figures.

**Case closure** by a second person is off by default (`OVERSIGHT.case_closure_requires_second_person`).

**Managed service switch.** `OVERSIGHT.managed_service_enabled` cannot be turned off while a mandate is open
(`MANAGED_SERVICE_MANDATE_ACTIVE`), cannot be changed at all under a mandate (`MANAGED_SERVICE_SWITCH_LOCKED`), the capability
reads on while a mandate is open however the switch came to be off, and revocation is never gated by it.

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
