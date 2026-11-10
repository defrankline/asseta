# Petty cash funds (DEC-033)

Requested by Mzalendo Investment Ltd on 2026-11-10 ("a petty cash management module"). Neither client document
(`client-accountability-requirements.md`, `client-development-guideline.md`) mentions petty cash or expenses, so this
design starts from the guideline's cash rules (3.3, Ledgers 4 and 5) and the expenses already in the system.

Builds on DEC-030, DEC-031 and DEC-032. All their principles apply: ledgers not balances; claimed ≠ confirmed; neutral
wording; offline never bypasses a control; **configurable multi-tenant SaaS** (every rule a versioned tenant policy
with a platform default, approvals by permission with proposer ≠ approver, business lists are tenant data; one
client's answers are settings, not code).

**Status: draft with recommended defaults.** Awaiting the owner's approval and Mzalendo's answers to Q1–Q4 (end of
this document). An answer different from the default changes a setting, not the design.

## Decisions (recommended defaults)

| # | Question | Recommended default |
|---|---|---|
| D1 | Where petty cash lives | A **petty cash fund**: a named pot with one accountable holder, an approved limit and its own ledger. A tenant may have one office box, one per site or one per field manager; each is just a fund. |
| D2 | Spending from customer collections | A tenant switch. Platform default **allowed** (today's behaviour, nothing changes for other tenants); Mzalendo **not allowed**, because guideline 3.3.9 says the entire accountable cash balance is remitted. |
| D3 | How a fund is refilled | **Imprest**: the fund is topped up by the amount of approved spending since the last top-up, never above its limit. Funding and top-ups are proposed by one person and approved by another holding the approving permission. |
| D4 | Expense records | **One** expense record for all spending. A petty cash expense is an ordinary expense with "paid from: petty cash fund", so approvals, receipts, GPS, categories, machine/job links, reports and profitability keep working. |
| D5 | Money moved into or out of a fund | Never a cost. Only approved expenses are costs; funding, top-ups and returns are transfers, so nothing is counted twice. |
| D6 | Cash advances (money out before the purchase) | Phase 3, built only if Mzalendo uses them (Q4). |

## What exists today (code audit 2026-11-10)

**Reused as is:** expenses (`expenses/`): categories, receipts, GPS, machine/job attribution, offline capture,
auto-approve limit and approval by permission (`EXPENSE_CAPTURE`); deposit accounts (`CompanyDepositAccount`, types
BANK, MOBILE_MONEY, CASH_OFFICE); float acknowledgement pattern (`CashFloatAcknowledgement`); variance workflow
(`variance_workflow.py`: assign, explain, evidence, second-person closure, write-off); audit, outbox, notifications,
reports, data export, Find a reference, employee view, management dashboard.

**Conflicts this design removes:**
- Floats and customer collections share one custody balance per person. With `remit_full_balance` on (Mzalendo), a
  supervisor who keeps the float back is flagged as a partial remittance unless a retention is approved.
- An expense paid from cash in hand (`ExpensePaidFrom.CASH_CUSTODY`) lowers the cash the person must remit; under the
  auto-approve limit no human sees it. The guideline's custody formula (Ledger 4) has no spending line.
- Unused float comes back as an ordinary remittance, so it mixes with customer money in "cash confirmed received".
- A float does not record where the money came from.

**Missing:** a fund with a limit, top-ups from receipts, a holder handing a fund to someone else, physical cash
counts, returns of a fund, advances.

## Fund ledger

Each fund has its own balance, derived from movements (never stored), in the fund's currency:

```
fund balance = fundings and top-ups (acknowledged by the holder)
             − approved expenses paid from the fund
             − returns to the office (amount the office confirmed)
             ± approved adjustments
             − written-off count differences
             − advances issued + change returned on cleared advances        (phase 3)
```

Shown separately and never reducing accountability until confirmed: expenses pending approval, fundings and top-ups
awaiting acknowledgement, returns awaiting confirmation. Every figure drills down to the movements behind it, as the
custody ledger does today. **Available to spend** = balance − pending expenses.

A person's custody balance (collections) and a fund balance are never mixed: a holder who also collects sees two
separate figures, and full remittance applies only to collections.

## Data model

New tables (tenant-scoped with RLS, audit on every change, client-created ids and times for offline rows):

- `petty_cash_fund`: code, name, holder (`staff_member`), optional job site, currency, approved limit, low-balance
  level (optional), active flag, version. Full lifecycle: list, view, create, edit, deactivate (only at zero balance
  with nothing pending).
- `petty_cash_movement`: fund, kind (`FUNDING`, `TOP_UP`, `RETURN`), number (`PC-…`, searchable in Find a
  reference), amount, source or destination deposit account, method, reference, evidence attachments, status, and
  the people and times of each step:
  - FUNDING / TOP_UP: `PROPOSED` → `APPROVED` (or `REJECTED`) → `ISSUED` → `ACKNOWLEDGED` (or `DISPUTED`, which opens a
    variance with the declared and received amounts).
  - RETURN: `CLAIMED` by the holder → `CONFIRMED` by the office with the amount counted (difference opens a variance).
- `petty_cash_count`: fund, counted amount, expected balance at that moment (snapshot), difference, counted by, witness
  (optional), evidence, note. A non-zero difference opens a variance (`VarianceSource.PETTY_CASH_COUNT`) and follows
  the existing workflow, including write-off by a second person.
- `petty_cash_holder_change`: fund, from holder, to holder, a count at the change, acknowledgement by the new holder.
  Until acknowledged, the old holder stays accountable.
- `petty_cash_adjustment`: proposed and approved by different people, with a reason from the tenant's cash reason
  list and evidence (same rules as custody adjustments).

Changed:
- `expense`: `paid_from` gains `PETTY_CASH`; new `petty_cash_fund_id` (required when PETTY_CASH, check constraint).
  Existing rows unchanged.
- `VarianceSource` gains `PETTY_CASH_COUNT`, `PETTY_CASH_FUNDING`, `PETTY_CASH_RETURN`.
- `supervisor_cash_custody` floats stay for what they are good for (change for collections); nothing migrates.

## Rules

1. Only the fund's current holder records expenses paid from it (or a recorder for them, under the existing
   `recorders_may_record_for_others` switch). The fund and the expense must have the same currency.
2. An expense larger than **available to spend** is refused online. Offline it is accepted (the phone may be stale),
   kept `PENDING_APPROVAL` whatever the auto-approve limit, and flagged as an overspend for the approver.
3. An expense above the fund's per-expense maximum (policy) always needs a human approval.
4. A top-up proposal is pre-filled with approved spending since the last top-up, capped at limit − balance; the
   proposer may lower it, and raising it above the cap needs a reason. The approver sees the expenses behind it.
5. Proposer ≠ approver, approver ≠ holder, issuer ≠ holder; the holder acknowledges what they received.
6. When spending from collections is not allowed (D2), an expense paid from cash in hand is refused online; from
   offline sync it is kept `PENDING_APPROVAL`, never auto-approved, and flagged. Nothing silently reduces what
   must be remitted.
7. A count is due every N days (policy); an overdue count and a fund below its low-balance level raise notifications.
   The holder may count, but a count by the holder alone is marked "self-count" when the policy asks for a witness.
8. Rejected expenses stay as evidence and never touch the fund (as today).

## Policy `PETTY_CASH` (capability `PETTY_CASH`)

| Field | Platform default | Mzalendo (recommended) |
|---|---|---|
| `enabled` | false (menus hidden) | true |
| `spend_from_collections_allowed` (in `CASH_CUSTODY`) | true | false |
| `max_expense_amount` (null = no maximum) | null | **[amount]** |
| `overspend_allowed_offline` | true (kept pending + flagged) | true |
| `count_every_days` (null = no schedule) | null | 7 |
| `count_witness_required` | false | true |
| `return_evidence_required` | false | true |
| `funding_evidence_required` | false | true |
| `advances_enabled` (phase 3) | false | per Q4 |
| `advance_clear_within_days` (phase 3) | 7 | 7 |

Fund limits are per fund (tenant data), not policy. Receipts, GPS and auto-approve limits stay in `EXPENSE_CAPTURE`;
a site or staff override works as it does today. Mzalendo's values go through `scripts/apply-tenant-policies.sh`.

## Permissions (role templates stay editable)

- `tenant.petty_cash.read`: see funds and their ledgers (a holder always sees their own fund).
- `tenant.petty_cash.manage`: create, edit, deactivate funds; change holder.
- `tenant.petty_cash.propose`: propose funding, top-ups and adjustments; confirm returns; issue approved money.
- `tenant.petty_cash.approve`: approve funding, top-ups and adjustments (an approving permission; only the owner
  assigns approving roles).
- `tenant.petty_cash.count`: record a count or witness one.

Templates: Owner all; Manager read, manage, count; Accountant read, propose, count; Supervisor read (own fund),
count. Holders record expenses with the existing `tenant.expense.write`.

## Everything it connects to

- **Profitability and dashboard:** no new code for costs, because they already count approved expenses. The money
  overview gains "petty cash held" per currency beside "cash with supervisors".
- **Revenue reconciliation:** unchanged; it compares hours and rates with money billed and does not use expenses.
- **Collections and remittance:** unchanged for tenants that allow spending from collections; cleaner for those that
  do not.
- **Reports:** fund statement (movements with running balance) and petty cash expenses by category, machine and job.
- **Employee view:** funds held and their balances. **Find a reference:** `PC-` numbers. **Data export** and
  **balance verification:** include the new tables and recompute fund balances.
- **Notifications:** funding or top-up awaiting approval, awaiting acknowledgement, return awaiting confirmation,
  count overdue, fund low, overspend flagged.
- **Offline (Supervisor app):** the holder's funds and balances in the sync snapshot; expenses, acknowledgements,
  top-up requests, returns and counts queued offline with client ids and times.

## Screens

- **Web:** Finance → Petty cash: Funds (list, view with statement, create, edit, deactivate, change holder), Top-ups
  and fundings, Returns, Counts. Approvals → Petty cash. Holder dropdowns, accounts and funds use async Autocomplete.
- **Supervisor app (Android and iOS, identical):** My petty cash: balance and available to spend, record an expense
  paid from the fund, acknowledge or dispute money received, request a top-up, return the fund, record a count.
- **Owner app (Android and iOS):** approve fundings, top-ups and adjustments.
- User manual: Tenant Owner, Manager, Accountant, Supervisor tabs, in the repo and the shared doc.

## Phases

Each phase is finished on backend, web, Android and iOS before the next starts.

1. **Funds and spending:** funds, funding (propose, approve, issue, acknowledge), expenses paid from a fund, the
   `spend_from_collections_allowed` switch, fund statement, policy and permissions.
2. **Keeping it straight:** top-ups, returns, counts and variances, holder change, adjustments, notifications,
   reports, dashboard figure, export and balance verification.
3. **Advances** (only if Q4 is yes): cash out before a purchase, cleared with receipts and change within N days.

## Tests

Backend per rule above (ledger formula, pending vs confirmed, proposer ≠ approver ≠ holder, overspend online and
offline, the collections switch online and offline, top-up cap, count variance through closure and write-off, holder
change, deactivation guard, RLS isolation, idempotent sync); web components and pages; Android and iOS view models;
acceptance scenarios added to `docs/client-pack/05-acceptance-scenarios.md`.

## Questions for Mzalendo

1. Is there one office cash box, or one fund per field manager or site? (Default: both supported; set up what they
   use.)
2. May staff ever spend from customer collections, for example fuel at a remote site before a float arrives?
   (Default for Mzalendo: no.) **This one matters most.**
3. Is each fund a fixed amount topped up from receipts, and who approves top-ups? (Default: fixed limit, approved by
   an approving role other than the requester.)
4. Do they hand out cash before a purchase? (Default: phase 3 only if yes.)

## Out of scope

Bank reconciliation of deposit accounts, supplier payables, payroll and allowances, per-diem rules, and a general
ledger or chart of accounts.
