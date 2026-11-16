# ADR-008: Machine reports replace jobs (reconciliation model)

Status: accepted by the owner, 2026-11-16. Applies to **all tenants** (no tenant is live yet, so the model may be
revamped freely). Approved screens: Supervisor and Owner app canvas
<https://claude.ai/artifact/8dqJMowFRbUY61NNqkYw7k>; plan <https://claude.ai/artifact/X6t8xgDsuMQUhsgcijDHNL>.

## Decision

Asseta stops managing **jobs**. A hire company sells machine **hours** to customers (an **order**) and supervisors
account for every engine hour of the machines assigned to them in **machine reports**: from the last approved meter
reading to a new one, the difference is split across customers (taken from hours they bought) and non-productive
reasons. The owner or manager approves each report. What owners read: per customer hours bought / used / left; per
machine productive vs non-productive hours by reason; money collected by method; credit invoices and payments.

## 1. Orders (sell hours)

- An order = the existing hours purchase: customer (registered or walk-in), machine, hours, rate-card price (and
  approved discounts), split payment lines. **No job is created**; "Book the job" is removed.
- Payment line methods: **CASH** (always the default line), **BANK**, **MOBILE_MONEY** (reference + optional evidence
  photo), **CREDIT** (amount only; registered customers only, never walk-ins; at most one credit line).
- Hours become **usable** (activated) as today: cash/bank/mobile parts per the tenant's cash-activation / verification
  rules; the credit part only after someone with `tenant.hours.credit_activate` approves it within the customer's
  credit arrangement limit (existing credit-activation flow). Credit never makes hours usable by itself.
- **Credit invoice:** recording an order with a credit part automatically creates an invoice for that part
  (hours × price, numbered per tenant, due date from the customer's payment terms). The customer pays it in **full or
  in several parts**, each part CASH / BANK / MOBILE_MONEY, recorded by the office (web, Owner app) **or by a supervisor
  in the field** (a cash part goes into that supervisor's cash custody like any collection). Statuses: UNPAID,
  PART_PAID, PAID; overdue after the due date. Paid orders get no invoice. These invoices replace job-based hire
  invoices.
- Company settings (CUSTOMER_HOURS policy): `field_noncash_payments` (exists), new `field_credit_sales` (default
  false; office holders of `tenant.hours.credit_activate` may always record credit).

## 2. Machine reports

- **Who/what:** a supervisor reports only on machines currently assigned to them (open `machine_assignment`, role
  SUPERVISOR). Owners/managers may report on any machine (web) but never approve their own.
- **Reading:** a new meter capture (photo, on-phone OCR, GPS, time; reuse meter capture / evidence). Previous reading =
  the end reading of the machine's last APPROVED report, else its meter baseline. New reading must be greater (meter
  resets keep using the existing reset flow). Difference 0 → nothing to report.
- **Lines** (the supervisor completes them in the same submission; no "explain later"):
  - CUSTOMER: `customer_id`, `hours` > 0. Each customer's total in the report ≤ that customer's **available hours**
    = activated − consumed − reserved by other pending reports. Hours are drawn from that customer's orders FIFO
    (oldest activated first), recorded as lots.
  - NON_PRODUCTIVE: `reason_id` (tenant reason list), `hours` > 0, `note` (required text).
  - Sum of lines == difference exactly (hours with 1 decimal, the machine's meter precision).
- **States:** SUBMITTED → APPROVED | REJECTED. One SUBMITTED report per machine at a time (the next waits).
  - Submitted: customer hours are **reserved**.
  - Approved (permission `tenant.machine_report.approve`, owner/manager by default; proposer never approves):
    customer hours consumed from the order lots (hours ledger CONSUMED), allocation-ledger entries written
    (CUSTOMER_WORK with lots; AUTHORIZED_ACTIVITY with the reason), the reading becomes the machine's last approved
    reading.
  - Rejected (reason required): reservation released; the supervisor submits a corrected split for the **same
    reading** (a new report version referencing it).
- **Approver aid:** the report detail shows tracker engine hours for the same period when the machine has a tracker
  (from existing telemetry/engine-hours data), and the difference against the meter.
- **Reasons list:** per-tenant editable list (reuse the engine-hour reason table/kind). Default entries created for
  every tenant (new tenants at onboarding, existing tenants by a one-off data step — not a migration of tenant
  values): Transit between sites, Breakdown / repair, Servicing, Idle on site, Waiting for customer, Weather.
- **Offline:** phones submit through sync operation `MACHINE_REPORT` (capability `OP_MACHINE_REPORT`) with a client id;
  the phone checks the sum and the cached available hours; the server is authoritative (refusals surface like other
  sync conflicts).
- **Permissions:** `tenant.machine_report.submit` (supervisor template), `tenant.machine_report.read`,
  `tenant.machine_report.approve` (owner/manager templates). Supervisors also hold the credit-invoice payment
  recording permission.
- **Notifications:** report submitted → approvers; approved/rejected → submitter; credit sale recorded → credit
  approvers; invoice overdue → office; machine with meter/tracker movement and no report for N days → owner
  (tenant policy, default 3 days).

## 3. Fuel switch

New tenant setting `fuel_enabled` (default true) on the policy that owns fuel capture. Off: no Fuel tab/menu/approval/
checks/insights/profitability line anywhere (server refuses fuel records, `/me` lists `FUEL` in
`disabled_capabilities`, phones hide the tab entirely, never flash it). Existing records kept, hidden. To be switched
off for Mzalendo and the demo company after deploy (not in migrations).

## 4. Removed (all tenants)

Jobs (request, approve, number, start/close, detail, "My jobs", job sync ops, job notifications), "Book the job",
walk-in standard contract for jobs, prepaid-job auto-approval, machine changeover, opening/closing readings per job,
daily drawdown of running jobs, job-derived work allocations, contracts (customer + rate card + payment terms stay),
required customer code (generated when blank), job-based hire invoices and "Unbilled work", job revenue differences,
site check-ins, job-based oversight/insight detectors (re-pointed to machine reports where the signal still matters:
idle machines = no approved report hours; meter vs tracker), job fields on reports and profitability (now per machine
and per customer). Database: old job tables may be dropped (no live tenant data to keep); keep migrations forward-only
and leave audit history readable.

## 5. Apps

- Supervisor app: sliding side menu + Home tiles (Sell hours, Machine report, Money, Dashboard); Sell hours with the four
  methods; Machine report in 3 steps (reading → account for hours → review & submit); Money (cash in hand, collections
  by method, handed over, expenses, petty cash, record credit-invoice payment); Dashboard (hours sold/used, productive vs
  non-productive, My machines list/map with report status, reports). No Jobs, no Fuel when off.
- Owner app: same shell; Home tiles (Approvals, Customers, Machines, Money); Approvals (machine reports, credit,
  expenses, petty cash); machine-report approval with tracker cross-check; Customers & hours with credit invoices;
  Machines (map + productive vs non-productive); Money (sold by method, cash per supervisor, credit invoices, Record
  payment); Reports.
- Web: the same functions for office and for supervisors without phones; Approvals › Machine reports; Customer hours
  balances; credit invoices and payments; reports; job menus removed.
