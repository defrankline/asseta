# Accountability design: how Asseta meets the client controls

Governs: `docs/requirements/client-accountability-requirements.md` (control IDs `[3.x.y]`). Decision DEC-030.
Status of each control before this work: see the gap analysis of 2026-10-24 (track.md session log).

Principles that apply everywhere:
- **Ledgers, not balances.** Every balance (customer hours, engine hours, custody cash) is derived from append-only
  entries; corrections are reversing/adjusting entries with reason + approver ([3.4.*]).
- **Claimed ≠ confirmed.** Anything a field person or customer asserts starts CLAIMED/PENDING; only an independent
  authorised person confirms it; the claimant can never confirm their own claim (SEGREGATION_OF_DUTIES).
- **Neutral wording.** Unexplained ≠ fraud. No "fraud" wording in tenant UI.
- **Configurable, not hard-coded.** Thresholds (aging days, tolerances, remittance cut-off, credit limits) are tenant
  policy, versioned and audited.
- **Offline never bypasses a control.** Field ops arrive at the server as claims; the server applies the control.
- Existing behaviour that already satisfies a control stays (see "Already covered" per section).

Open questions for the client are listed at the end with the default we build meanwhile.

---

## A. Customer hours (3.1) — new `hours` module

### Entities
- **Customer kinds.** `Customer.kind = REGISTERED | WALK_IN`. A walk-in needs only a display name and a phone number
  (optional); code auto-assigned `WALK-<nnnnn>`. Walk-ins can later be upgraded to REGISTERED (audited) [3.1.3].
- **Customer discount (predefined, authorised).** `CustomerDiscount(customer, percent, effective_from/to, reason,
  proposed_by, approved_by)`. Proposed by one person, approved by another holding `tenant.hours.discount_approve`.
  Only APPROVED, in-effect discounts apply — automatically, never typed per sale [3.1.4].
- **Standard rate.** The existing rate card (per machine category, versioned) is the only price source for a
  purchase. No manual price override on purchases [3.1.4].
- **Hours purchase** `HP-<yyyy>-<nnnnn>` (gap-free per tenant, unique) [3.1.1]: customer, machine (the specific
  excavator) [3.1.2], hours, currency, rate snapshot (rate card id + rate), discount snapshot (discount id + %),
  amount = hours × rate × (1 − discount) [3.1.4], created_by/at, optional job_site. Status derived:
  `AWAITING_PAYMENT → PARTLY_ACTIVE → ACTIVE → CONSUMED`, or `CANCELLED` (only while nothing consumed; reason +
  approver). Immutable after creation except via ledger entries / cancellation.
- **Payment ↔ purchase link** [3.1.5]: payments stay `CustomerPayment` (CLAIMED → VERIFIED by another person,
  already built) and are linked to a purchase through `PurchasePaymentAllocation` (same rules as invoice
  allocations: row locks, no over-allocation, released on rejection) [3.1.8 duplicate allocation].
- **Payment evidence** [3.1.6]: payments/collections accept attachments (receipt photo, mobile-money screenshot) —
  stored as evidence only; status stays CLAIMED until independently verified.
- **Credit arrangement** [3.1.7]: `CreditArrangement(customer, limit amount, currency, effective dates, reason,
  approved_by)` approved by `tenant.hours.credit_approve` (SoD with proposer). Credit exposure = credit-activated
  amount not yet covered by verified payments.
- **Hours ledger** (append-only) per purchase & machine: `ACTIVATED`, `CONSUMED`, `TRANSFER_OUT`, `TRANSFER_IN`,
  `EXPIRED`, `REVERSAL`. Unused activated hours expire after the tenant policy `purchased_hours_expiry_days`
  (configurable, counted from activation; Q3). Derived per purchase: purchased, activated, consumed, remaining = activated − consumed ± transfers.

### Activation [3.1.7, 3.1.8]
- Paid activation is automatic and only from VERIFIED money: when an allocated payment is verified, activated hours
  rise to `floor(verified_allocated_amount / effective_rate, precision)` (partial payments activate partially).
  A payment rejection after activation reverses the un-consumed part (REVERSAL entry) and raises an exception if
  hours were already consumed.
- Credit activation is an explicit action "Activate on credit" by someone with `tenant.hours.credit_activate`,
  within the customer's available credit; records who/when/why.
- Nobody can activate hours any other way (no manual "activate" button without payment or credit).

### Consumption: Work Execution Allocation [3.2.4, 3.1.8]
- A job for a prepaid customer names the hours purchase(s) it draws from (`Job.billing_mode = PREPAID_HOURS |
  INVOICE`; INVOICE keeps today's post-paid flow for contract customers).
- START of a PREPAID_HOURS job requires remaining activated hours > 0 on that machine (`NO_AVAILABLE_HOURS`).
- On COMPLETE, the job's billable hours (from approved readings, existing calculation) become a **Work Execution
  Allocation** (WEA): CONSUMED ledger entries FIFO across the customer's active purchases for that machine, under
  row locks. Hours beyond what is available are NOT consumed: an `HOURS_OVERRUN` blocking exception is raised with
  the excess; it is cleared only by a new paid/credit activation (then allocated) or a reviewed write-off.
- One WEA per job; a job's engine interval can be allocated once (see B) [3.2.5].
- Offline: two field users completing jobs against the same remaining hours are serialised at the server; the second
  gets a partial allocation + HOURS_OVERRUN (controlled, visible) [3.5.5].

### Transfer between excavators [3.1.9]
- `HoursTransfer(purchase, from_machine, to_machine, hours ≤ remaining, reason, requested_by, approved_by)`;
  approval by `tenant.hours.transfer_approve`, SoD. On approval: TRANSFER_OUT / TRANSFER_IN ledger entries. The
  purchase keeps its original machine; the purchase page shows the full transfer history.

### Already covered
Duplicate payment allocation and references; claimed vs verified payments; rate cards versioned and audited.

---

## B. Engine hours (3.2) — extend `meter`

- **Approved baseline per machine** [3.2.1]: `MachineMeterBaseline(machine, reading, photo, captured_by, approved_by,
  approved_at)`. Two people (SoD). Until approved, the machine's reconciliation status is `NO_BASELINE` and job
  START is refused (`BASELINE_REQUIRED`). Re-baselining only through the existing meter-reset flow.
- **Readings outside jobs** [3.2.2]: new `ReadingKind.DAILY` (and job readings as today); `job_id` nullable for DAILY.
  Same evidence rules (photo/GPS per policy, captured_at, received_at, user, device).
- **Machine engine-hour ledger** [3.2.3]: consecutive ACCEPTED readings of a machine form intervals (start reading →
  end reading, elapsed hours). Each interval is split into segments:
  - `CUSTOMER_WORK` — covered by a job's opening→closing (allocated to that job and, if prepaid, its WEA) [3.2.4];
  - `UNALLOCATED` — everything else; classification state: `UNEXPLAINED` (default) → `APPROVED_NON_CUSTOMER`
    (category: maintenance, relocation, testing, company work, other + note; approved by `tenant.meter.classify`,
    SoD with proposer) or `IDENTIFIED_VARIANCE` (reason, approved) [3.2.6].
  - No hour may sit in two segments: job intervals on one machine may not overlap in time or meter range
    (`OVERLAPPING_ALLOCATION`), and job activity entries may not overlap (`OVERLAPPING_ACTIVITY`) [3.2.5].
- **Flags** [3.2.7]: existing 15 exception types stay; add `MISSING_DAILY_REPORT` (machine on an active job or with
  engine activity and no DAILY/job reading by the policy cut-off hour) and `UNEXPLAINED_HOURS` (segment opened).
- **Aging → investigation, never → verdict** [3.2.8]: policy `unexplained_hours_investigation_after_days`
  (default 3). When an UNEXPLAINED segment is older, an investigation case is opened (existing cases module); the
  segment stays UNEXPLAINED — time never reclassifies it.
- **Corrections** [3.2.9]: superseding a reading needs a reason (min 10 chars), is proposed by one person and
  approved by another (`tenant.meter.approve`), audited with before/after and the superseded id.

### Already covered
Evidence on readings, decrease/impossible-increment/continuity-gap/telemetry checks, meter resets with SoD, no
automatic verdict.

---

## C. Cash custody chain (3.3) — extend `finance` cash

- **Who can be a custodian** [3.3.1]: any active staff member, with or without a login (operators hold cash but
  do not record — Q1). **Recorders** are staff with `tenant.collection.record` (Supervisor and Manager templates;
  any role can be granted it) who record collections, transfers and remittances on a custodian's behalf. A transfer
  is acknowledged by the receiving custodian; when the recorder *is* the receiver, recording it is the
  acknowledgement (with the amount actually received). Operators keep no field-app write permissions by default.
- **Collections** [3.3.1]: amount, custodian, customer (walk-in allowed), and link to the hours purchase or job when
  there is one; evidence attachments.
- **Field-to-field transfer** [3.3.3, 3.3.4]: `CashTransfer(from_custodian, to_custodian, amount declared, note)`
  created by the sender (online or offline) → `PENDING_ACKNOWLEDGEMENT`. The receiver acknowledges with the amount
  actually received (`ACKNOWLEDGED`, may differ) or disputes it. Until acknowledged the money stays in the
  sender's custody (shown "in transit"). Never a company receipt.
- **Remittance to company** [3.3.5, 3.3.6]: today's handover, renamed "Remittance". The office records the amount
  actually received (may differ from declared) when confirming; claimant ≠ confirmer.
- **Variance** [3.3.7]: any declared ≠ received (transfer or remittance) creates a `CashVariance` (OPEN →
  RESOLVED with outcome RECOVERED / CORRECTED_ERROR / WRITTEN_OFF; write-off needs `tenant.finance.writeoff`, SoD)
  and links an investigation case when above the policy threshold.
- **Full remittance by default** [3.3.8]: policy `remit_full_balance` (default on) with cut-off; a remittance less
  than the custodian's outstanding balance needs an authorised `CashRetention` (amount, reason, approver) or it
  raises `PARTIAL_REMITTANCE`. Approved cash expenses remain the other authorised use.
- **Floats** are company → custodian transfers that the receiver must acknowledge too.
- **Custody corrections** [3.4.2]: `CustodyAdjustment` (reversal or adjustment entry, reason, proposer, approver).
- **Direct payments** [3.3.9]: already built (bank/mobile money/office receipt never touch field custody).
- **Expected balance** [3.3.2] = opening + floats acknowledged + collections + transfers in (acknowledged amount) −
  transfers out (acknowledged) − approved cash expenses − remittances received − approved adjustments, derived.

---

## D. Integrity, offline, oversight (3.4–3.6)

- [3.4.8] Every reconciliation figure drills down to its transactions and evidence (web).
- [3.6.10 "unauthorized attempts"] Permission refusals and SoD attempts are recorded as security events and listed.
- [3.5.5] Office **Sync conflicts** screen: conflicted/rejected field operations with evidence; outcome
  (re-applied as … / dismissed with reason), audited.
- **Accountability dashboard** (web + Owner app summary) with the 3.6 list: customer hours purchased / activated /
  consumed / remaining; engine-hour reconciliation per machine; unexplained hours and open investigations; cash per
  custodian; transfers awaiting acknowledgement; remittances awaiting confirmation; payments awaiting confirmation
  and hours awaiting activation; missing/overdue daily reports; unauthorised attempts, open variances and
  discrepancies, outstanding approvals. Each tile alerts (push/inbox) per notification routing.

---

## Questions for the client (we build the default meanwhile)

| # | Question | Default built |
|---|---|---|
| Q1 | Do operators carry phones and record collections/transfers themselves? | **Answered 2026-10-24:** operators carry phones but managers record on their behalf. Operators are cash custodians without needing a login or the field app; supervisors/managers (field recorders) record collections, transfers and work for them. |
| Q2 | Are hours bought for one excavator only, or can one purchase cover several? | **Answered:** per specific machine, not per site. One excavator per purchase; moving hours = authorised transfer. |
| Q3 | Do purchased hours expire? Refunds of unused hours? | **Answered:** unused hours expire after a configurable period (tenant policy `purchased_hours_expiry_days`, counted from activation; EXPIRED ledger entry; alert before expiry). Refunds: still open — default is an approved cancellation of the remaining hours. |
| Q4 | Who approves credit (and discounts, transfers, write-offs, classifications)? | **Answered:** whoever holds the permission — the tenant owner/admin or any role granted it. Nothing is tied to a fixed role; permission + segregation of duties only. Credit is per customer with a money limit. |
| Q5 | Rounding of consumed hours (per 0.1 h, per hour, minimum hours per day)? | Existing tenant meter rounding policy; minimum hours from the rate card. |
| Q6 | Aging threshold for unexplained hours? | 3 days, configurable. |
| Q7 | What is the "daily operational report"? | A daily meter reading per working machine + the day's work log; cut-off hour configurable. |
| Q8 | May a custodian keep any cash (e.g. a working float) instead of remitting everything? | Only with an approved retention. |
