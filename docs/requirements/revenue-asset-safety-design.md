# Revenue and asset-safety design (DEC-031)

Goal (Platform Owner, 2026-10-26): **maximum revenue and maximum safety of assets** — every working hour turns into
money that reaches the owner, machines are used only for work, and nothing is lost unnoticed.

Source: owner conversation of 2026-10-25/26 describing how the founding tenant's manager reconciles
("today's reading − last reading − movement hours = real working hours, then match the hours with the money"),
deposits cash to the owner's bank / mobile-money account for the owner to check against the statement, sells
prepaid hours used over days or weeks, and must stay on top of remote sites.

Builds on DEC-030 (`accountability-design.md`): engine-hour ledger, customer hours, cash custody chain, oversight.
All DEC-030 principles apply unchanged: ledgers not balances; claimed ≠ confirmed; neutral wording (a difference is
"to explain", never "fraud"); offline never bypasses a control; **configurable SaaS** — every rule below is a tenant
policy with a safe platform default, capabilities switch on per tenant (off = today's behaviour), approvals are
permissions with proposer ≠ approver, business lists are tenant data. The founding tenant's answers become its
settings, not code.

## What exists today (verified in code, 2026-10-26)

| Need | Today |
|---|---|
| Reading-to-reading hours per machine | Engine-hour ledger: intervals inside a job window = customer work; outside = unallocated → unexplained until a second person approves a non-customer category (tenant list) or variance |
| Movement hours inside a job | Work-log MOBILIZATION is non-billable by default but the job summary only subtracts STANDBY/DOWNTIME, and the engine ledger ignores the work log; movement inside a job counts as customer work. A fixed `mobilization_fee` charge exists |
| Hours × rate vs money | **Missing.** Pieces: job charges, invoices, verified payments, prepaid purchases/allocations, cash custody, profitability (revenue vs cost, no hours) |
| Per-machine per-day view | **Missing.** Per-machine interval list; weekly utilisation report |
| Remittance proof | Amount, time, optional free-text reference, note; owner confirms with amount received → variance (shortfall *and* surplus) → case above `cash.variance_case_threshold`. No destination account, no evidence photo, reference optional. Customer payments already have method CASH/BANK/MOBILE_MONEY + reference required for non-cash |
| Remote sites | Daily remittance cut-off (one hour for the whole tenant), risk-signal "cash held at most/up to", approved retentions |
| Prepaid hours over weeks | Deducted only at job completion; HOURS_EXPIRING warning (`expiry_warning_days`); **no** low-balance warning; **no** customer hours statement |
| Engine on without a job | Risk signal UNREPORTED_ENGINE_ACTIVITY from tracker ignition/engine counter (verified trackers only), linked into cases |
| Fuel | FUEL_ALLOWANCE_EXCEEDED: litres per meter hour **per job** (default off); weekly fuel-efficiency insight. Nothing per machine outside jobs |
| Idle machines / unbilled work | **Missing** (no idle report; `billing_ready` only gates invoicing) |
| Manager oversight | Data exists (missing daily reports, unexplained hours, alerts, cash held, differences, refused attempts) but no per-person view |

## Phases and items

Each phase ships on its own (backend → web + Android + iOS together → user manual), fully tested.

### Phase 1 — Did the machines' work turn into money? (revenue)

**R1. Revenue-hour basis (policy `REVENUE_RECONCILIATION`)**
- `enabled` (default off).
- `non_revenue_activity_types`: which work-log types are non-revenue inside a job (default: MOBILIZATION). Tenant can
  add STANDBY etc. (STANDBY stays governed by the contract's standby treatment for *billing*).
- `deduct_non_revenue_from_working_hours` (default false = today): when true, non-revenue work-log time inside a
  job window is shown as its own bucket (e.g. "Movement") in the engine-hour ledger and daily sheet, not as customer
  work.
- `deduct_non_revenue_from_prepaid_hours` (default false): whether that time is drawn from the customer's prepaid
  hours (see P1).
- Billing of movement stays a contract term (`mobilization_fee`, rate card); this item never changes invoicing
  unless the tenant switches the deduction on, and then only through the existing billable-hours computation.

**R2. Daily machine sheet** (read model, no new ledger)
One row per machine per tenant-local day: readings (first/last, count), engine hours, customer-work hours,
non-revenue hours (by type), approved non-customer hours, unexplained hours, jobs and customers, fuel litres,
expected revenue, money attributed (R3), difference, flags (missing daily report, unexplained, engine-on-no-job,
fuel above norm). Web: Engine hours → **Daily machine sheet** (filters machine, site, day range; drill to readings,
jobs, ledger, money). Owner app: read-only per machine. Export CSV.

**R3. Hours-to-money reconciliation**
- Policy (`REVENUE_RECONCILIATION`): `period` (DAY, WEEK, JOB; default WEEK), `tolerance_percent` and
  `tolerance_amount` (either exceeded → difference), `case_threshold_amount` (opens/joins an investigation like cash
  variances), `basis` (INVOICED_OR_PREPAID default).
- Expected revenue per machine per period = customer-work hours (after R1) × the job's locked hourly rate (+ standby
  per contract, + mobilization fee in the period it is charged).
- Money attributed = prepaid hours consumed × purchase effective rate + invoice lines issued for those jobs (and,
  where the tenant wants cash-in matching, verified payments / confirmed cash collections linked to the job or
  purchase).
- Result per machine-period: expected, attributed, difference, status OPEN → EXPLAINED (reason from a tenant list,
  second-person approval) or CONFIRMED. Neutral wording ("revenue difference to explain").
- Sweep after each period closes (tenant time zone), idempotent per machine-period; notification
  REVENUE_DIFFERENCE to holders of the decide permission; dashboard tile; links to the daily sheet.
- Permissions: `tenant.revenue.read`, `tenant.revenue.explain`, `tenant.revenue.decide`.

### Phase 2 — Engine running and fuel (asset safety)

**S1. Engine running without work, one case per machine-day**: link the existing signals (tracker engine-on outside
job windows, meter unallocated hours, after-hours movement) for the same machine and day into one case with all
evidence, instead of separate signals; shown on the daily sheet. Policy: `engine_without_work_case_min_minutes`.

**S2. Fuel against hours per machine**: extend the fuel rule from per-job to per machine per period (all fuel
issued/purchased into the machine vs engine hours in the period, inside or outside jobs). Policy: `fuel_litres_per_hour_max`
per machine category (machine override allowed), `fuel_check_period`. Above norm → risk signal → case. Daily sheet
shows litres and litres/hour.

### Phase 3 — Money reaches the owner (deposits)

**D1. Company deposit accounts** (tenant data): name, type BANK / MOBILE_MONEY / CASH_OFFICE, institution, masked
account number, currency, active. Full lifecycle (list/detail/create/edit/deactivate), permission
`tenant.finance.accounts.manage`.

**D2. Stronger remittances**: remittance gains `method` (CASH_TO_OFFICE, BANK_DEPOSIT, MOBILE_MONEY),
`deposit_account_id`, `reference`, evidence photos (same evidence store as payments; offline capture through the
existing sync op, photos uploaded like reading photos). Policy (`CASH_CUSTODY`): `remittance_reference_required`
(for BANK/MOBILE_MONEY), `remittance_evidence_required`, `remittance_account_required`. Owner confirm screen shows
account, reference and photo side by side with "amount received". Surplus (statement shows more) already opens a
negative variance — label it "Surplus to explain".

**D3. Remote-site cash allowance**: `cash.max_holding_days` with site and staff overrides (tenant default null =
today). Cash held longer than its allowance (and not covered by an approved retention) → REMITTANCE_OVERDUE with the
reason "held longer than allowed", instead of only the daily cut-off. Works alongside the cut-off.

### Phase 4 — Prepaid hours used over days and weeks

**P1. Daily drawdown**: policy `CUSTOMER_HOURS.drawdown` = AT_COMPLETION (default, today) or DAILY. DAILY: customer-work
hours per day from readings on a prepaid job are allocated provisionally each day (PROVISIONAL allocation entries,
reversed and replaced by the final allocation at completion, so totals always reconcile). Live balance; overrun
detected the day it happens (existing over-consumption policy applies).

**P2. Low-balance warning**: `CUSTOMER_HOURS.low_balance_hours` (null = off); notification HOURS_LOW_BALANCE to the
office, and optionally the customer contact by SMS (`low_balance_notify_customer`, uses SMS credits).

**P3. Customer hours statement**: per customer (and machine), period: bought, activated, used per day/job, transferred,
expired, remaining, expiry date; PDF and share link from web; Owner app view.

### Phase 5 — Is everyone on top of things?

**M1. Per-person scorecard** (read model): per field recorder / custodian / supervisor for a period — daily reports
late or missing, unexplained engine hours on their machines, alerts open and time to acknowledge, cash held (days,
amount), cash differences (count, total, how many just under the case threshold), revenue differences on their
machines, refused attempts. Policy (`OVERSIGHT`): `scorecard_enabled`, `near_threshold_percent` (e.g. 90 %),
`repeat_pattern_count` (e.g. 3 differences in 30 days → pattern signal → case). Web: Overview → **People
scorecard**; Owner app: More → Scorecard. Neutral wording.

**M2. Unbilled and idle**: `OVERSIGHT.unbilled_after_days` (completed + billing-ready + not invoiced → UNBILLED_WORK
notification and tile); `OVERSIGHT.idle_after_days` (active machine with no job and no engine hours for N days →
IDLE_MACHINE tile/report, links to the fleet).

**M3. Site check-in (optional, off)**: `OVERSIGHT.site_checkin_required` with times of day; the Supervisor app asks
for a GPS check-in at the site at those times; missed check-in is a scorecard item. Only person-location data the
tenant deliberately switches on; shown to the person in the app.

## Open questions for the client (defaults built meanwhile)

| # | Question | Default built |
|---|---|---|
| Q9 | Is movement inside a job charged to the customer / taken from prepaid hours? | Not deducted (today); tenant switches R1 on |
| Q10 | Money check period and tolerance? | Weekly, 5 % or a tenant amount, case above a tenant amount |
| Q11 | How many days may cash be held at remote sites? | No limit (today) until set |
| Q12 | Low-balance warning: threshold, and does the customer get an SMS? | Off |
| Q13 | Does the owner want site check-ins? | Off |
| Q14 | Which deposit accounts does the owner use? | Tenant enters them (D1) |

Owner decision: APPROVED 2026-10-26 ("The goal is maximum revenue and maximum safety of assets" … "yes lets goooo").

## Implementation notes — Phase 1 (backend, 2026-10-26)

Ambiguities resolved while building R1–R3 (all tenant-configurable where a rule is involved):

- **Capability.** `REVENUE_RECONCILIATION.enabled` is the master switch (capability `REVENUE_RECONCILIATION`, platform
  default **off**). Off = R1 deductions read as off, the sheet/difference/reason endpoints refuse with
  `REVENUE_RECONCILIATION_DISABLED`, menus and the dashboard tile are hidden, and the sweep skips the tenant.
- **Owner rule (2026-10-26): non-productive hours count as revenue until explained and approved.**
  `non_revenue_requires_approval` (default **true**): a non-revenue work-log entry inside a job (declared types, e.g.
  movement to/from a site) becomes non-revenue only after one person explains it (`tenant.revenue.explain`, tenant
  reason + note) and another approves it (`tenant.revenue.decide`; proposer ≠ approver; same PROPOSED → APPROVED /
  REJECTED flow and statuses as engine-hour classifications, record `non_revenue_approval`). Until approved it stays
  customer work, billable and expected revenue (shown as `non_revenue_pending_hours` on the daily sheet). Engine hours
  **outside** jobs that are not approved as non-customer activity (unexplained, proposed, rejected, or classified as
  an identified variance — only APPROVED_NON_CUSTOMER removes them) are **expected revenue**
  (`unexplained_hours_treatment` EXPECT_REVENUE default | EXCLUDE) at `unexplained_hours_rate_source`
  MACHINE_RATE_CARD (default: the machine category's rate card in force, its currency; no rate card = shown, not
  priced) | TENANT_RATE (`unexplained_hours_rate`, tenant base currency); they are their own line ("unexplained hours
  expected as revenue") on the sheet and in each difference. When a classification or non-revenue approval is
  approved later, recorded differences of the overlapping periods are recomputed at once (whatever `recheck_days`):
  open ones are refreshed (CLEARED when back within tolerance); EXPLAINED / CONFIRMED ones keep their figures and get
  an append-only **adjustment** entry (previous, new, amount, cause).
- **R1 scope.** Only *non-billable, ended* work-log entries of the declared types count (an entry logged as billable
  stays revenue). Their wall-clock overlap with a customer-work interval becomes the NON_REVENUE bucket, capped at the
  interval's engine hours. `deduct_non_revenue_from_working_hours` also removes that time from an INVOICE job's
  billable hours, and `deduct_non_revenue_from_prepaid_hours` from a PREPAID job's drawdown — both through the job
  summary's existing billable-hours computation, using the policy in force when the job **started** (a later switch
  never re-prices a running job). The ledger view uses the policy in force now.
- **Expected revenue** mirrors billing: customer-work hours less the job's non-billable time (DOWNTIME/STANDBY
  always, declared types when deducted) × locked hourly rate, + STANDBY_RATE standby × standby rate, + mobilization
  fee in the period containing the job's start, less the job's discount. Tax is never revenue. Intervals spanning a
  day/period boundary are split by wall-clock time.
- **Money attributed** (`basis = INVOICED_OR_PREPAID`, the only basis built): issued invoice lines of the job (hire,
  standby, mobilization, discount) + prepaid CONSUMED hours × purchase effective rate, spread over periods in
  proportion to the job's expected revenue. Cash-in matching (verified payments) is deferred.
- **Differences** are opened only for a **shortfall** beyond tolerance (`tolerance_percent` of the expected revenue
  of completed work, or `tolerance_amount`, either exceeded); more money than expected (e.g. minimum-hours billing) is
  not a difference. Work of jobs still running counts as `in_progress`, never as a difference.
- **Periods** are tenant-local DAY, ISO WEEK (Monday–Sunday) or JOB (per completed job). Closed periods ending within
  `recheck_days` (default 28) are re-examined every scheduler cycle: an OPEN difference whose money arrived later
  becomes **CLEARED** (system, final); figures of differences awaiting a decision are refreshed. Statuses: OPEN →
  EXPLANATION_PROPOSED (explain, `tenant.revenue.explain`) → EXPLAINED (APPROVE) or back to OPEN (REJECT); CONFIRMED
  (CONFIRM, from OPEN or proposed: the difference is real, money to recover). Deciding needs `tenant.revenue.decide`
  and is refused to the explainer. Reasons are a tenant list managed by decide holders.
- **Daily sheet fuel** = litres issued or purchased into the machine that day (USAGE logs are not added, to avoid
  double counting). Flags come from existing records: MISSING_DAILY_REPORT exceptions, UNREPORTED_ENGINE_ACTIVITY and
  FUEL_ALLOWANCE_EXCEEDED risk signals, unexplained ledger hours, and revenue differences covering the day.
