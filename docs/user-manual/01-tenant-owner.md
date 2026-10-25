# Asseta user manual: Tenant Owner

> Part of the [Asseta user manual](README.md). Read the README first for signing in and the glossary.

## Who this is for

This manual is for the owner, or the top administrator, of an equipment-hire company that uses Asseta. In Asseta your company is called a **tenant**, and you hold the **Tenant Owner** role.

You can see and do everything in your company's account. You work in two places:

- The **web console** at <https://asseta.co.tz>, for set-up, administration, reviews and finance.
- The **Asseta Owner** app on Android or iPhone, to watch the business and run it on the go: approve or create jobs, decide expenses and meter resets, confirm cash handovers, review exceptions, issue cash floats and react to alerts.

### Running the business from a distance

You may be far from your machines, for example in Dar es Salaam while the machines work in Katavi. Asseta is built so you can still decide from your phone. A job starts in one of two ways:

- **The supervisor requests it from the field.** A customer on site asks for work; the supervisor sends a job request from their phone. You set the price and approve it, or decline it with a reason. See [Approve jobs](#6-approve-expenses-and-jobs) and [Approvals](#approvals) in the app.
- **You create it and assign a supervisor.** In the web console (**Operations → Jobs**) or in the Owner app (**Jobs → New job**). With **Approve now**, the supervisor is notified at once.

Either way the supervisor then takes the readings, logs the work and collects the customer acknowledgement in the field, and you follow it all from the app.

Many day-to-day tasks are shared with other roles. This manual points to their manuals rather than repeating every step:

- Jobs, customers, machines, trackers and geofences: [Manager / Dispatcher](02-manager-dispatcher.md).
- Field work: [Supervisor](03-supervisor.md).
- Invoices, payments and cash: [Accountant](04-accountant.md).

## What you can do

Everything any other role can do, plus the tasks reserved for owners by default:

- **Approve jobs and set their price**, including jobs supervisors request from the field.
- **Review meter and GPS exceptions.** This unblocks invoicing.
- **Decide meter reset requests.**
- **Set company policies**: reading modes, GPS rules, expense limits, tracking thresholds, billing rounding, device offline limits and risk-signal thresholds.
- **Manage users' roles** (Users & roles).
- **Enroll machines as billable assets** in your Asseta subscription.
- **See your Asseta subscription**, its invoices and your SMS wallet.
- **Review or revoke a managed-service mandate**, if the Platform Owner helps run your account.
- **Set company-wide notification defaults** and see the SMS delivery log.
- **Read the audit log**: who changed what, and when.
- **Switch on the accountability controls** for customer hours, engine hours and cash, and watch them on the **Accountability** dashboard (see [Switching on the controls](#switching-on-the-controls)).
- **Decide engine-hour records**: meter baselines, explanations of engine hours and reading corrections (never your own).
- **Review refused attempts** (**Security events**) and **resolve sync conflicts**.

By default the owner role holds every permission, so you can also make every decision described in the other chapters (hours discounts, credit, transfers, cancellations, write-offs, retentions, custody adjustments). Your company can give any of these permissions to other roles; the person who proposed something can never decide it.

## Where you work

### Web console menus

| Group | Menus |
|---|---|
| Overview | Dashboard, Fleet map, Accountability |
| Field work | My jobs, Readings, Fuel, Expenses, Cash, Customer hours |
| Operations | Jobs, Customers, Staff |
| Fleet | Machines, Trackers, Sites & geofences, Alerts |
| Customer hours | Hours purchases, Balances, Hours ledger, Work allocations, Transfers, Cancellations, Customer discounts, Credit arrangements, Walk-in customers, Reason lists |
| Engine hours | Reconciliation, Hours to explain, Hour explanations, Meter baselines, Reading corrections, Engine-hour reasons |
| Finance | Hire finance, Cash custody, Expenses & fuel, Approvals, Profitability |
| Risk & review | Exceptions, Meter resets, Investigations, Insights, Security events, Sync conflicts |
| Administration | Policies, Users & roles, Audit log, Subscription, Managed service, Notifications, My access |

When a control is switched off in your policies, its menus are left out. For example, with **Customer hours switched on** set to No, the whole **Customer hours** group and **Field work → Customer hours** disappear. Opening such a page by its address shows "Customer hours is not enabled for your company".

The top bar has:

- The **company switcher** (your company's name).
- A connection indicator.
- The **notification bell**.
- Your name.
- A light/dark mode toggle.
- **Sign out**.

### The Asseta Owner app

| Tab | What it holds |
|---|---|
| **Overview** | Your dashboard tiles (fleet, jobs, money, investigations) |
| **Fleet** | Map or list of machines with live/last-known status |
| **Jobs** | Jobs and their hours, charges, readings, work log, expenses, fuel and customer acknowledgement; **New job**; approve or decline jobs waiting for approval |
| **Alerts** | Tracking alerts to acknowledge or resolve |
| **More** | Approvals (expenses, meter resets, jobs, cash handovers, exceptions, and the accountability requests), **Accountability**, Meter exceptions, Field spend, Cash with supervisors (with **Issue float**), Investigations, Notifications, Settings, Company |

---

## Getting started: setting up your company

The Platform Owner (the company that runs Asseta) onboards your company, agrees your subscription fee, and sends you a **temporary password** through a secure channel. Then:

1. **Sign in** at <https://asseta.co.tz> and set your own password. You may also be asked to set up an authenticator app. See [Signing in](README.md#signing-in).
2. **Check your subscription**: **Administration → Subscription** shows your agreement, price per machine and billing period.
3. **Review your policies**: **Administration → Policies**. Asseta starts you with sensible defaults. Change them as needed (see [Task 3](#3-set-company-policies)).
4. **Add your machines**: **Fleet → Machines**. Then enrol each one as a billable asset ([Task 2](#2-enroll-machines-as-billable-assets)).
5. **Register trackers** and assign them to machines: **Fleet → Trackers**.
6. **Add staff**: **Operations → Staff**. Create your supervisors and operators, and link each supervisor to their Asseta login.
7. **Assign staff to machines** on each machine's **Staff assignments** tab. A supervisor can request jobs only on machines assigned to them (or already on their jobs).
8. **Create job sites and geofences**: **Fleet → Sites & geofences**.
9. **Add customers, contracts and rate cards**: **Operations → Customers**.
10. **Create your first job** and approve it, in the web console or the Owner app. Your supervisor sees it on their phone after syncing. From then on supervisors can also request jobs from the field for you to approve.
11. **Install the Asseta Owner app** and enable push notifications.
12. **Decide which accountability controls to use** and switch them on: see [Switching on the controls](#switching-on-the-controls).

Steps 4 to 10 are described in the [Manager / Dispatcher manual](02-manager-dispatcher.md).

---

## Tasks in the web console

### 1. Read the dashboard

**Overview → Dashboard** ("Fleet, work, money and risk at a glance") has four sections:

- **Fleet**:
  - **Machines** by connectivity (Live, Recent, Stale, Offline, Never reported, No tracker)
  - **Engine on (verified)**: from tracker ignition data with a fresh position, never guessed
  - **Reported work state**: as reported by supervisors
  - **Open alerts** by severity
- **Work**:
  - **Jobs** by status
  - **Pending approvals**
  - **Readings needing review**: provisional readings with an open exception
- **Money**, per currency:
  - **Receivables outstanding**
  - **Overdue**
  - **Receipts this month**
  - **Approved expenses this month**
  - **Cash held by supervisors**
- **Risk**:
  - **Open exceptions**: meter and GPS exceptions awaiting review
  - **Open cases**
  - **Signals (last 7 days)**

Click a tile to open the matching filtered list.

The **Accountability** section at the bottom links to the accountability dashboard (**Open the accountability dashboard**). See [Task 14](#14-accountability-dashboard).

### 2. Enroll machines as billable assets

Your Asseta subscription is charged **per billable machine**, not per user.

1. Go to **Fleet → Machines**, find the machine and choose **Enroll as billable asset**.
2. Choose **Billable from** (the start date). Asseta previews any proration charge for the part-period, or shows **No proration charge**.
3. Confirm.

The machine is now counted on your subscription and can have a tracker assigned. Replacing its tracker later does **not** create a second billable machine.

To stop billing a machine (sold, scrapped or returned), contact the Platform Owner, who ends the enrollment with a reason and preview any credit.

### 3. Set company policies

**Administration → Policies** controls how Asseta behaves.

1. Choose the **Policy type**.
2. Look at the **Effective policy** (what applies now) and the **Version history**.
3. To change it, click **New override**. The dialog is **New {type} policy version**.
4. Choose the **Scope**:
   - **Tenant default (all fields)**: applies to everything.
   - **Machine override**: applies to one machine.
   - **Site override**: applies to one site.
5. Turn on only the fields you want to override and set their values.
6. Set **Effective from (empty = now)** and a **Reason**.
7. Click **Create version**.

Changes are versioned and never rewrite past records. Every reading, expense and alert keeps the policy version that applied when it was recorded. Supervisors' phones pick up new rules at their next sync.

The most important settings:

| Policy type | Setting | What it does |
|---|---|---|
| Meter capture | **Opening reading mode** / **Closing reading mode** | **Automatic (photo + on-device OCR)** or **Manual (numeric entry)**, set separately for opening and closing |
| | **Photo required for manual readings** | Whether a typed reading also needs a photo |
| | **Minimum OCR confidence**, **Max recapture attempts** | When the phone's automatic reading is trusted, and how many retakes before manual entry is allowed |
| | **OCR corrections require review** | Flag readings where the supervisor changed the camera's number |
| | **GPS enforcement** | **Soft — keep as provisional for review**, or **Hard — reject the reading** when there is no valid GPS fix |
| | **GPS max accuracy**, **GPS max fix age** | How good and how fresh the phone's location must be |
| | **Tracker distance tolerance**, **Tracker comparison window** | How far the phone may be from the machine's tracker at the same moment |
| | **Max meter hours per elapsed hour**, **Continuity tolerance**, **Telemetry engine-hours tolerance** | Checks for unrealistic meter jumps, gaps between jobs, and differences from tracker engine hours |
| Expense capture | **Receipt required above**, **GPS required on expenses**, **Maximum GPS accuracy**, **Auto-approve up to** | Receipt rules and the limit above which expenses wait in Approvals |
| Tracking | **Live max age**, **Stale after**, **Offline after** | When a machine shows Live, Stale or Offline |
| | **Geofence tolerance**, **Max position accuracy**, **Max plausible speed** | Geofence and GPS-quality rules |
| | **Operating window start/end**, **Operating weekdays** | Approved working hours; movement outside them raises an *Unauthorized movement* alert |
| | **Low power voltage** | Tracker power alert threshold |
| Hire billing | **Billable hours increment**, **Rounding** | How meter hours become billable hours (for example 0.1 h, rounded Up / Half up / Down) |
| Device sync | **Offline grant**, **Policy snapshot validity** | How long supervisors' phones may work offline and keep cached rules |
| | **Device clock skew alert** | When a wrong phone clock is reported |
| Risk signals | **Engine activity without a running job**, **Fuel allowance**, **Weekly spending per machine** | Thresholds for automatic review signals |
| | **Cash held at most** / **Cash held up to** | When cash not handed over is flagged |
| | **Duplicate receipt lookback**, **Case grouping window**, and others | How signals are found and grouped |

| Customer hours | **Customer hours switched on** | The master switch for prepaid hours. Off: no purchases or prepaid jobs; jobs are invoiced, and the **Customer hours** menus and app buttons are hidden |
| | **Walk-in customers allowed** | Whether hours can be sold to walk-in customers without full registration |
| | **Billing methods allowed on jobs**, **Default billing of new jobs** | **Invoice after the work** and/or **Prepaid customer hours**, and which one a new job uses unless changed |
| | **Hours activate from** | **Verified payments** and/or **Approved credit** |
| | **Partial payments activate hours pro rata**, **Activation step** | Whether part-payment activates part of the hours, and the step activated hours are rounded down to |
| | **Unused hours expire after**, **Warn before expiry** | Days from activation (empty = never expire), and how many days before expiry a warning is sent |
| | **When a prepaid job has no hours left** | **Do not let the job start**, or **Allow it and flag the excess** |
| | **Excess hours block the job until reviewed** | Whether hours beyond the purchase block invoicing until reviewed |
| | **Transfers between machines need a second person**, **Cancellations need a second person**, **Discounts need a second person** | Whether these requests wait for a second person's approval |
| | **Cancel the rest of a partly used purchase** | Whether the unused part of a purchase can be cancelled once some hours are used |
| | **Highest discount**, **Credit arrangements allowed** | The largest discount that can be proposed, and whether customers can get credit |
| | **A reason from the tenant list is required** | Whether requests must pick a reason from your [reason lists](#switching-on-the-controls) |
| Engine hours | **Approved meter baseline before a job starts** | Off: jobs start without an approved baseline (reconciliation still begins at the baseline) |
| | **Daily report required**, **Daily report cut-off** | A working machine needs a meter reading every day by the cut-off hour (local time) |
| | **Open an investigation for unexplained hours after** | Days after which unexplained hours open an investigation (empty = never). Time never changes how the hours are classified |
| | **Flag unexplained hours above** | Ignore very small unexplained amounts |
| | **Classifications need a second person**, **Reading corrections need a second person** | Whether explanations of engine hours and meter corrections wait for a second person |
| | **Count readings still under review** | Whether provisional readings count in the engine-hour ledger |
| | **Refuse overlapping job intervals**, **Refuse overlapping work-log entries** | Stop the same engine hour being counted twice |
| Cash custody | **Recorders record for any custodian** | Field recorders may record cash for staff without a login (otherwise own custody only) |
| | **Receiver acknowledges transfers**, **Recording a transfer you receive acknowledges it** | Whether a cash transfer waits for the receiver to confirm the amount |
| | **Receiver acknowledges floats** | Whether a float waits for the receiver to confirm it |
| | **Remit the full balance** | A remittance leaving unretained cash with the custodian is flagged |
| | **Daily remittance cut-off** | Local hour by which cash should be remitted; leave empty for no daily cut-off |
| | **Open a case for differences above** | Cash differences above this amount open an investigation (empty = never automatically) |
| | **Write-offs need a second approver**, **Approved retentions allowed** | Write-off and retention rules |
| Oversight | **Hidden dashboard tiles** | Ticked tiles are hidden from the accountability dashboard |
| | **Refused-attempts window** | How many days of refused attempts the dashboard counts |

Hire billing, Device sync, Expense capture, Customer hours, Cash custody and Oversight are company-wide only. They cannot be overridden per machine or site. In Engine hours, only **Approved meter baseline before a job starts** and **Daily report required** can be set per machine.

**Hourly hire prices** are not policies. They are set in rate cards and on each job (see the [Manager manual](02-manager-dispatcher.md#1-add-a-customer-a-contract-and-rate-cards)). Your **Asseta subscription price** is negotiated with Asseta and cannot be edited here.

### 4. Review meter and GPS exceptions

When a reading looks unusual, Asseta records an **exception**: a neutral note of what was found, with evidence. Some exceptions are **blocking**. The job cannot be invoiced until someone reviews them.

1. Go to **Risk & review → Exceptions** ("Meter and GPS evidence that requires review before billing").
2. Filter by **Status**, **Type**, **Blocks billing** or **Job**. Each row shows **What was recorded**.
3. Open an exception to see:
   - The reading, photo, GPS result and tracker comparison.
   - The policy version that applied.
   - Whether it **Blocks billing until reviewed**.
4. Click to review it. Choose the **Outcome**:
   - **Explained — a legitimate reason was found**
   - **Discrepancy confirmed — evidence stands as recorded**
5. Write a **Review note** (at least 5 characters) and click **Record review**.

*What you'll see:* "Review recorded." The status changes to **Reviewed — explained** or **Reviewed — discrepancy confirmed**. Once no blocking exceptions remain, the job shows **Billing ready**. The supervisor sees your note on their reading.

Exception types you will meet:

- GPS unavailable / inaccurate / not fresh
- Location differs from tracker
- Capture mode differs from policy
- Meter photo missing
- Low OCR confidence
- Reading differs from OCR
- Meter reading decreased
- Increment exceeds elapsed time
- Gap since previous job
- Photo reused
- Differs from tracker engine hours
- Device clock ahead of server
- Offline policy not confirmed
- Hours beyond what the customer has active (a prepaid job used more hours than were activated)
- Daily report missing
- Engine hours not yet explained
- Job intervals overlap

As Asseta says on screen: *"Exceptions are recorded evidence that requires review. They are not a conclusion about any person."*

You can also review exceptions in the Owner app (see [Approvals](#approvals)).

If something needs a deeper look, the evidence can be grouped into an **investigation** (see [Task 7](#7-investigations-and-insights)).

### 5. Decide meter reset requests

A supervisor requests a meter reset when an hour meter is replaced or rolls over.

1. Go to **Risk & review → Meter resets** ("Replaced or rolled-over hour meters across all machines, awaiting or after a decision"). It shows pending resets by default; filter by **Status** or **Machine**. Each row shows the **Machine**, **Requested by**, **Reading (old → new)**, **Reason** and **Evidence**.

   You can also open a job's **Meter resets** tab (from **Operations → Jobs**), or **More → Approvals → Meter resets** in the Owner app.
2. Check the **Old** and **New** readings, the **Effective** time, the **Reason** and the evidence (**View evidence**).
3. Click **Decide**. Choose the **Decision**:
   - **Approve reset (documented reason accepted)**
   - **Reject reset**
4. Write a **Note** and click **Record decision**.

The person who requested a reset can never decide it: *"You requested this reset; another approver must decide it."* After approval, later readings are compared against the new meter value.

### 6. Approve expenses and jobs

- **Expenses** above the auto-approval limit wait in **Finance → Approvals**. See the [Manager manual, Task 11](02-manager-dispatcher.md#11-decide-expense-approvals).
- **Jobs**: open a job in **Pending approval** and click **Approve**. This fixes the hourly price for billing. See the [Manager manual, Task 3](02-manager-dispatcher.md#3-submit-and-approve-a-job).
- **Jobs requested from the field** carry a **Field request** chip in **Operations → Jobs**. When you approve one, the dialog shows "Requested from the field by <supervisor>" and what the customer asked for. If no rate card applies, the price shows "No price yet (set on approval)": enter the **Hourly rate** to approve it at that price. To refuse it, click **Decline request** and give a **Reason**. The supervisor is told your reason, and the job stays on record as cancelled.

You cannot approve your own expense, and you cannot verify a payment or cash handover you recorded yourself.

### 7. Investigations and insights

- **Risk & review → Investigations**: signals from automatic checks, grouped into cases. Assign, annotate, resolve with an outcome, or reopen. See the [Manager manual, Task 12](02-manager-dispatcher.md#12-investigations).
- **Risk & review → Insights**: each machine compared with its own history, plus manual overrides and model status. See the [Manager manual, Task 13](02-manager-dispatcher.md#13-insights).

### 8. Finance

- **Hire finance**: hire invoices and customer payments.
- **Cash custody**: cash held by every custodian, transfers, floats, remittances, overdue remittances, variances, retentions, adjustments, the reconciliation and the cash reason lists.
- **Expenses & fuel**: all expenses and fuel events, and expense categories.
- **Profitability**: by machine, job or customer.

All of these are described in the [Accountant manual](04-accountant.md). Customer hours are described in the [Manager manual](02-manager-dispatcher.md#14-customer-hours-how-it-works).

### 9. Users and roles

**Administration → Users & roles** shows who can sign in to your company's account and which roles they hold:

- owner
- manager
- supervisor
- accountant
- operator

To remove a role from someone:

1. Find the user and click **Revoke** on the role.
2. Confirm in the **Revoke role** dialog.

Asseta will not remove the **last owner**. Roles granted under a managed-service mandate end with the mandate.

**Adding a new login:** the web console does not yet have an "invite user" button. Ask the Platform Owner to create the login with the right role. The person receives a temporary password and sets their own at first sign-in.

**Linking a supervisor:** after the login exists, link it to their staff record (**Operations → Staff**, **Login subject**). Their jobs and cash then appear under their name.

**Roles at a glance:**

| Role | Typical person | Main place of work |
|---|---|---|
| Tenant Owner | Owner / director | Web + Owner app |
| Manager / Dispatcher | Operations manager | Web (+ Owner app) |
| Supervisor | Site supervisor | Supervisor app (+ web Field work) |
| Accountant / Finance | Accountant, cashier | Web |
| Operator | Machine operator | Notifications only |

### 10. Notifications for the whole company

1. Go to **Administration → Notifications → Preferences**.
2. The **Tenant defaults** tab sets which notifications go by **In-app** and **SMS** for everyone who has not chosen their own settings. Some are marked **Required** and cannot be switched off.
3. The **Push and e-mail** routing sets defaults by category and severity. Click **Save routing**.
4. **Delivery log** shows SMS, push and e-mail delivery results.

**Notifications open the exact record.** Clicking a notification about a cash transfer, float, remittance, overdue remittance, variance, retention, custody adjustment, hours discount, credit arrangement, hours transfer or cancellation, meter baseline, reading correction or engine-hour explanation opens that record's own page, where you can see it and decide it. Notifications about missing daily reports or unexplained engine hours open the machine's engine-hours page. The Owner app does the same.

SMS uses credits from your **SMS wallet**, which is shown on the **Subscription** page. Buy SMS bundles from the Platform Owner. You are warned when credits run low or run out.

### 11. Subscription

**Administration → Subscription** shows:

- **Agreement** status and **Current period**.
- **Billable / enrolled assets**, **Price per asset**, **Minimum billable assets**, **Payment terms** and **Billing start**.
- Asseta's **Invoices** to you (**View**).
- Your **SMS wallet**.

Pricing is agreed with the Platform Owner and is read-only here.

If a payment is overdue, your account may become **read-only**. A banner says: "…is read-only. You can view data, but changes are disabled until the subscription is restored." **Your data is never deleted.** Field work recorded offline during that time is held and applied after reactivation.

### 12. Managed service

If you have agreed that the Platform Owner helps run your account, **Administration → Managed service** shows:

- The **Mandate** (reference, scope, term and your consent reference).
- **Staff with access**.
- **Recent actions under this mandate**.

Everything done under the mandate is recorded in your audit log, marked "By Asseta staff under {mandate}".

To end it, use **Revoke mandate** with a **Reason for revoking**. If there is no mandate, the page says "No managed-service mandate". The Platform Owner then has no access to your account.

### 13. Audit log

**Administration → Audit log** ("Who changed what in this tenant, and when") lists every change with **When**, **Actor**, **Action**, **Record** and **Reason**. Filter by actor, action, record type or date. Expand a row to see the before and after values.

### 14. Accountability dashboard

**Overview → Accountability** answers three questions at a glance: what happened to every customer hour, every engine hour and every amount of cash. The page shows "As of <time>", has a **Refresh** button and refreshes itself every 5 minutes. Click a tile or one of its lines to open the matching list.

| Tile | What it shows |
|---|---|
| **Customer hours** | Hours remaining across customers and machines, with **Activated**, **Consumed**, **Awaiting activation**, **Expired** and **Open overruns** |
| **Hours awaiting activation** | Purchased hours waiting for confirmed payment or approved credit: **Purchases awaiting payment**, **Purchases partly active** |
| **Engine-hour reconciliation** | Machines by reconciliation status |
| **Unexplained engine hours** | Machines with hours not yet explained, oldest first |
| **Missing daily reports** | Working machines without the daily report by the cut-off |
| **Open investigations** | **Open** and **In review** cases |
| **Cash per custodian** | Outstanding cash held, per custodian |
| **Cash awaiting acknowledgement or confirmation** | Transfers and floats not yet acknowledged, remittances not yet confirmed, partial remittances, and **Remittances overdue today** (only when a remittance cut-off is set) |
| **Payments awaiting confirmation** | Customer payments still claimed, per currency |
| **Open discrepancies** | **Open variances**, **Write-offs proposed**, **Offline operations to review** |
| **Refused attempts** | For the last few days (your **Refused-attempts window**): **Missing permission** and **Own record (segregation of duties)** |
| **Outstanding approvals** | **Approval requests**, **Payments to confirm**, **Remittances to confirm**, **Cash retentions**, **Custody adjustments**, **Write-offs** |

You can hide tiles you do not use with the **Oversight** policy (**Hidden dashboard tiles**). The page then says "Hidden by your organisation's oversight policy: …". When customer hours are switched off, their tiles are not shown at all. The same summary is in the Owner app under **More → Accountability**.

The figures are never typed in. Each one is worked out from the records behind it, and you can follow it down to those records and their evidence.

### 15. Engine-hour reconciliation

Asseta accounts for every engine hour of each machine. Between two accepted readings, the hours are split into:

- **Customer work**: hours inside a job (from its opening to its closing reading).
- **Not yet explained**: every other hour, until someone explains it as **Non-customer activity** (maintenance, relocation, testing and so on) or an **Identified variance**.

No hour is ever counted twice. If two jobs on one machine overlap, each hour counts once, for the earlier job, and the overlap is shown for review.

1. Go to **Engine hours → Reconciliation** ("Every engine hour of each machine accounted for: customer work, explained activity, or still to explain").
2. Each machine shows its **Status**, **Baseline**, **Last reading**, **Engine hours**, **Customer work**, **Not yet explained** and **Open items**. Filter by **Status**:

   | Status | Meaning |
   |---|---|
   | **No approved baseline** | The machine has no approved starting reading yet ([Task 16](#16-meter-baselines)) |
   | **Hours to explain** | Some hours are not yet explained ([Task 17](#17-explain-engine-hours)) |
   | **Readings under review** | Some readings are still provisional and wait for exception review |
   | **All hours explained** | Every hour is customer work or explained |
3. Click a machine to open its engine-hour page (also the **Engine hours** tab on the machine record). It shows the **Baseline**, the **Totals** and the **Engine-hour timeline**: each interval with **From**, **To**, **Hours**, a **Breakdown** into job hours and unallocated hours, and **Checks**. Use **From** and **To** to choose dates.

**Daily readings.** Hours between jobs can only be accounted for if the meter is read. Supervisors take a **daily reading** outside jobs (see [Supervisor manual](03-supervisor.md#a12-daily-readings-baselines-and-corrections)). If your policy has **Daily report required** on, a machine that worked during a day (a job ran or its tracker reported the engine on) without any reading by the **Daily report cut-off** is flagged **Daily report missing**. The machine's supervisors and the reviewers are notified.

### 16. Meter baselines

A baseline is a machine's approved starting reading. Reconciliation starts from it. If your policy has **Approved meter baseline before a job starts** on, a job on that machine cannot start until its baseline is approved ("Approve a meter baseline for this machine first.").

**Propose a baseline** (usually the supervisor does this on site):

1. Go to **Engine hours → Meter baselines** ("The approved starting reading of each machine; engine hours are reconciled from it") and click **Propose baseline**, or open the machine's engine-hour page.
2. Choose the **Machine**, enter the **Meter reading (hours)**, add a **Note** and the **Meter photo**, and let the browser try a GPS fix.
3. Click **Propose baseline**. *What you'll see:* "Baseline proposed; a second person decides it."

On a machine's engine-hour page you can instead click **Use an existing reading** to base it on an accepted reading already recorded.

**Decide a baseline:**

1. In **Meter baselines** (filtered to **Awaiting decision**), click **Decide**.
2. Check the **Reading**, **Taken**, **Proposed by**, **Source** and **Photo** (**View photo**). "Approving makes this reading the machine's starting point: engine hours are reconciled from it."
3. Choose **Approve** or **Reject**, write a **Note** (at least 5 characters) and click **Record decision**.

*What you'll see:* "Baseline approved." To change an approved baseline later, use a [meter reset](#5-decide-meter-reset-requests).

### 17. Explain engine hours

Unexplained hours are a question to answer, not a finding against anyone.

1. Go to **Engine hours → Hours to explain** ("Engine hours outside customer work, oldest first. Unexplained hours are a question to answer, not a finding."). Filter by **State**, **Machine** or **Open at least (days)**.
2. On a row, click **Explain**. The dialog is **Explain <hours> h · <machine>**.
3. Under **What were these hours?**, choose **Non-customer activity (maintenance, relocation, …)** or **Identified variance (with a reason)**.
4. Choose the **Activity category** or **Variance reason** from your [Engine-hour reasons](#19-engine-hour-reasons).
5. Write **What happened** (at least 5 characters) and click **Propose explanation**.

*What you'll see:* "Explanation proposed; a second person decides it." If your policy has **Classifications need a second person** off, a holder of the classify permission records it directly: "Hours explained."

**Decide an explanation:** go to **Engine hours → Hour explanations** ("Unallocated engine hours explained as non-customer activity or an identified variance"), click **Decide**, choose **Approve** or **Reject**, write a **Note** (at least 5 characters) and click **Record decision**. "Rejecting leaves them not yet explained, so they can be explained again."

**Aging.** Time never turns unexplained hours into anything else. When hours stay unexplained longer than your policy's **Open an investigation for unexplained hours after** (3 days unless you change it), Asseta opens an **investigation** on the machine and the row shows **Investigation opened**. The hours remain **Not yet explained** until a person records an approved explanation. Follow the case in **Risk & review → Investigations**.

### 18. Reading corrections

A meter reading is never edited. A wrong reading is replaced by a **correction**, and the original stays on record.

1. Go to **Engine hours → Reading corrections** ("Corrected meter readings: the original stays on record; a second person approves") and click **Propose correction**. Supervisors can also propose one from a reading.
2. Choose the **Machine** and the **Reading to correct**, then click **Continue**.
3. Write the **Reason for the correction** (at least 10 characters), choose the **Capture mode**, enter the corrected **Meter reading (hours)** with its **Meter photo** and location, and click **Propose correction**.

*What you'll see:* "Correction proposed; a second person decides it."

To decide, click **Decide** on a correction awaiting a decision, check **Reading (old → new)** and the **Reason**, choose **Approve** or **Reject**, write a **Note** (at least 5 characters) and click **Record decision**. "Approving supersedes the old reading with the corrected one (both stay on record) and the engine-hour ledger is recalculated." The old reading then shows **Superseded**.

### 19. Engine-hour reasons

**Engine hours → Engine-hour reasons** ("Your lists for explaining engine hours: non-customer activity categories and variance reasons") holds your company's own lists. Click **New entry**, choose the **List** (**Non-customer activity category** or **Variance reason**), enter a **Code**, **Name** and **Description**, and click **Create entry**. Deactivate an entry when you no longer use it: "It can no longer be chosen for new explanations; past explanations keep it."

Add your lists **before** people start explaining hours, for example Maintenance, Relocation, Testing and Company work.

### 20. Security events

**Risk & review → Security events** ("Attempts the system refused: a missing permission, or someone deciding their own record") lists every refused attempt with **When**, **Kind**, **Who**, **Attempted**, **Record** and **Request**. Filter by **Kind** (**Missing permission** or **Own record (segregation of duties)**) and dates. Click a row to see the details.

The page is read-only. A refused attempt is a record for oversight, often a simple mistake, not a conclusion about the person. People who manage access are also notified when someone tries to decide their own record ("Segregation-of-duties attempt blocked").

### 21. Sync conflicts

When the Supervisor app syncs, the server checks every field record again. A record that conflicts (for example the job was cancelled meanwhile, or two people used the same remaining customer hours) or is refused is kept with its evidence instead of being lost or silently overwritten.

1. Go to **Risk & review → Sync conflicts** ("Field operations recorded offline that the server did not apply, with what the device sent"). It shows **Awaiting review** by default.
2. Open a row to see **Why not applied**, **Submitted by**, the **Device**, **What the device sent (evidence)** and **Server state at the time**.
3. Click **Resolve**. Choose the **Outcome**:
   - **Dismiss (no further action)**
   - **Re-captured (recorded again correctly)**: optionally give the **Re-captured record type** and **Re-captured record id**.
4. Write the **Reason** and click **Record outcome**.

*What you'll see:* "Outcome recorded." Someone else must resolve an operation you submitted yourself.

---

## The Asseta Owner app

### Sign in and choose a company

1. Install **Asseta Owner**, tap **Sign in** and use your Asseta username and password.
2. Choose your company under **Choose a company**. A company may be marked **Full access**, **Read only** or **Blocked**.

### Overview

Tiles for:

- **Fleet**: Machines, Live now, Recent, Stale, Offline, Never reported, No tracker, Engine on (tracker verified), Open alerts.
- **Jobs and work**: jobs by status, Pending approvals, Readings needing review, Open meter exceptions.
- **Money (month from …)**: Receivables outstanding, Overdue, Verified receipts this month, Approved expenses this month, Cash with supervisors.
- **Investigations and signals**.

Each section shows when its data was last updated. Tap a tile to go to the matching list.

### Fleet and machine

- Switch between **Map** and **List**.
- Filter with **Live**, **Recent**, **Stale** or **Offline**, or search by machine, code or operator.
- On the map:
  - The marker colour shows connectivity.
  - A dashed ring means the position is not live.
  - A red badge counts open alerts.
- Tap a machine to see:
  - **Status**: connectivity, last seen, engine and motion from the tracker, reported work status, location compliance, operator, supervisor, tracker.
  - **Last 24 hours**: track, distance and stops.
  - **Current job**, **Recent alerts** and **Recent meter readings** (with evidence photo).

### Jobs

Filter by **In progress**, **Approved**, **Pending approval**, **Completed**, **Cancelled** or **All**. Open a job to see:

- **Job**: number, status, dates, rate and minimum hours.
- **Hours**:
  - Opening and closing reading
  - Meter hours
  - Non-billable and standby hours
  - **Billable hours**
- **Charges**: the lines, Subtotal, Discount, Tax and **Total**. It also shows "Ready to invoice." or "Not ready to invoice: N blocking exception(s)."
- **Readings** (with photos), **Work log**, **Expenses**, **Fuel**.
- **Customer acknowledgement**: who signed, the method, hours acknowledged, and **View signature**.

**Approve or decline a job.** A job in **Pending approval** shows a **Request** section (for a field request: "Requested from the field by <name>" and "What the customer asked for") and a **Decision** section:

1. Tap **Approve**. If no rate card applies, the app says "No rate card applies — set the price to approve": enter the **Hourly rate** first. Confirm **Approve this job?**.
2. Or tap **Decline**, write the **Reason** (required; the supervisor sees it) and confirm **Decline this job?**.

*What you'll see:* "Job approved." or "Job declined." The supervisor is notified.

**Create a job and assign a supervisor.** On the Jobs tab, tap **New job**:

1. Choose the **Customer contract**, **Machine** and **Supervisor**, and optionally the **Site (optional)**.
2. Set the **Planned start** and **Planned end (optional)**, and type the **Job number**.
3. Under **Price**, choose **Rate card** or **Negotiated rate** (then enter the **Hourly rate**). Optionally enter **Minimum hours (optional)**.
4. Leave **Approve now** on to approve it straight away, and tap **Create and approve**. *What you'll see:* "Job J-… created and assigned to <supervisor>." The supervisor is notified at once.
5. With **Approve now** off, tap **Create**: the job is sent for approval ("Job J-… created and sent for approval.").

Other job terms (standby, fees, discount, tax) take the standard defaults. Use the web console when you need to set them.

### Alerts

Filter **Open**, **Acknowledged**, **Resolved** or **All**. Open an alert to see its evidence. Then tap:

- **Acknowledge**, or
- **Resolve**. This needs a note in **Note (required to resolve)**.

### Approvals

**More → Approvals** lists expense requests, filtered **Pending**, **Approved** or **Rejected**, and these sections: **Meter resets**, **Jobs** (waiting for approval), **Cash handovers** and **Exceptions**.

For an expense:

1. Open it. Check the **Request**, then the **Expense** (description, supplier, paid from, receipts).
2. Tap **Approve**, or **Reject**. Rejecting needs a note.

For a meter reset:

1. Open it and check the old and new readings, the reason and the photo.
2. Enter a **Note (required)** and tap **Approve reset** or **Reject reset**.

For a job, see [Jobs](#jobs) above.

For a cash handover ("<supervisor> handed over <currency> <amount>", "Claimed <time>"):

1. Open it and check the amount, reference and note against the cash or deposit slip.
2. Enter the **Amount received**. It starts at the declared amount. "Count the cash. A different amount opens a cash difference for review." The card also shows the **Expected balance** and any amount **Not covered by a retention**.
3. Tap **Confirm received** (a note is optional), or **Dispute** (a **Reason** is required). Confirm **Confirm this handover?** or **Dispute this handover?**.

*What you'll see:* "Handover confirmed." or "Handover disputed." Only a confirmed handover reduces the custodian's cash, by the amount received. A disputed one shows as **Rejected** to the supervisor, with your reason.

For an exception ("<type> on <job number>"):

1. Open it to see the status, severity, evidence and **Open job**. Tap **Review**.
2. Choose the **Outcome**: **Explained — a legitimate reason was found** or **Discrepancy confirmed — evidence stands as recorded**.
3. Write the **Review note** (5 to 2000 characters) and tap **Record review**. *What you'll see:* "Exception reviewed."

The app reminds you: "The person who submitted a request can't decide it (segregation of duties)." The same applies to handovers: you cannot confirm one you recorded yourself.

**Accountability requests.** When the controls are on, Approvals also has these sections. A section appears only when something waits and your role may see it:

| Section | Row shows |
|---|---|
| **Customer discounts** | "<percent>% discount" |
| **Credit arrangements** | "Credit limit <amount>" |
| **Hours transfers** | "Move <hours> h to another machine" |
| **Hours cancellations** | "Cancel an hours purchase" |
| **Meter baselines** | "Baseline <reading> h · <machine>" |
| **Engine-hour classifications** | "<hours> h · <category>" |
| **Reading corrections** | "<old> → <new> h · <machine>" |
| **Cash write-offs** | "Write off <amount>" |
| **Cash retentions** | "Keep <amount>" |
| **Custody adjustments** | "<kind> <amount>" |

Each row shows "Proposed <time> by <name>". To decide one:

1. Tap it. The decision screen shows the **Request**: customer, machine, purchase, amounts, reason, **Proposed by** and so on, with names rather than codes.
2. Under **Decision**, write a note and tap **Approve** or **Reject**. For meter baselines, classifications and corrections the **Note (at least 5 characters)** is always required. For the others the note is optional to approve and required to reject. Rejecting asks **Reject this request?**.

*What you'll see:* "Approved." or "Rejected." On your own request both buttons are disabled: "Someone else must decide your own request". A request that was already decided shows its status and decision.

### More: other screens

- **Meter exceptions**: open and all exceptions, with **Blocking** marked. Tap one to see it and **Review** it, as in [Approvals](#approvals).
- **Field spend** (read-only): expenses and fuel recorded in the field.
- **Cash with supervisors**: per supervisor and currency, for **Today**, **7 days** or **This month**:
  - **Holding** = opening + floats + collections − approved spending − verified handovers
  - Plus amounts awaiting approval or verification, and the supervisor's claimed handovers (tap one to confirm or dispute it).
  - **Issue float**: opens **Issue a cash float**. Enter the **Amount** (in the card's currency) and a **Note (optional)**, then tap **Issue**. *What you'll see:* "Float issued." The supervisor's cash goes up.
- **Investigations**: cases and their signals and outcomes. Decisions are recorded in the web console.
- **Accountability**: the accountability summary, with the same tiles as [Task 14](#14-accountability-dashboard): **Outstanding approvals**, **Cash** (transfers and floats awaiting acknowledgement, remittances awaiting confirmation, partial remittances, cash per custodian), **Payments awaiting confirmation**, **Discrepancies**, **Investigations**, **Refused attempts**, **Customer hours**, **Hours awaiting activation**, **Engine hours**, **Unexplained engine hours** and **Missing daily reports**. The footer shows the policy version and time. If your company sets a remittance cut-off, the Cash tile shows **Remittances overdue today** with "Cut-off <hour>:00". Tap it to open **Overdue remittances**, where each row reads "Still held after the <hour>:00 cut-off on <day>."
- **Notifications**: your inbox, with **Unread only** and **Mark all read**. Tapping a notification, or its push message, opens the exact record: the decision screen of a discount, credit arrangement, hours transfer, cancellation, baseline, correction, classification, write-off, retention or custody adjustment; a **Cash transfer** or **Cash float** record; the cash handover; or an **Overdue remittance**. Notifications about missing daily reports or unexplained hours open the machine.

### Settings

- **Push priorities**: switch push on or off for each category (Needs your action, Anomalies & alerts, Reminders, Billing, Information) and severity (Critical, Warning, Info). Switches marked **(required)** stay on. Tap **Save**. Everything still arrives in the in-app inbox.
- **Push devices**: **Enable push notifications** on this phone, or **Stop push to this device**.
- **Offline data**: an explanation of how saved data works (see below).
- **Account**: **Switch company**, **Change password** (needs a connection) and **Sign out**. Signing out erases the saved data on the phone.

### Offline use (read-only)

Screens you have opened are kept encrypted on your phone for up to 7 days. With no connection you can still look at them. A banner says, for example, "Offline — data from 21 Oct 2026, 14:05 (stale)".

While you are looking at saved data, **all decisions are disabled**. Approvals, new jobs, handover decisions, reviews, floats and alert actions need a live connection. They become available again by themselves once you are back online.

---

## Statuses and what they mean

| Item | Statuses |
|---|---|
| Job | Draft → Pending approval → Approved → In progress → Completed; Cancelled |
| Meter reading | Accepted; Provisional — requires review; Rejected; Superseded |
| Meter exception | Requires review → Reviewed — explained / Reviewed — discrepancy confirmed |
| Meter reset | Pending → Approved / Rejected |
| Expense | Pending approval → Approved / Rejected |
| Payment, cash collection, handover | Claimed (unverified) → Verified / Rejected |
| Hire invoice | Draft → Issued → (Voided) |
| Alert | Open → Acknowledged → Resolved; Superseded |
| Investigation case | Open → In review → Resolved (reopen possible); outcomes: Issue confirmed, Unconfirmed, Legitimate explanation |
| Your company's access | Full; Read only (subscription restricted, nothing deleted); Blocked |
| Meter baseline, reading correction, hour explanation | Awaiting decision → Approved / Rejected |
| Engine-hour reconciliation (per machine) | No approved baseline; Hours to explain; Readings under review; All hours explained |
| Engine hours (per interval) | Customer work; Not yet explained; Non-customer activity; Identified variance |
| Sync conflict | Conflict / Rejected → Dismissed or Re-captured |
| Customer hours, cash | See the [Manager](02-manager-dispatcher.md#statuses-and-what-they-mean) and [Accountant](04-accountant.md#statuses-and-what-they-mean) manuals |

## Switching on the controls

Every accountability control is a company policy. A control that is off keeps the usual behaviour, and its menus and buttons stay hidden. Asseta starts you with safe defaults: customer hours are available, while daily reports, required baselines, float acknowledgement, full remittance and the remittance cut-off are **off** until you switch them on. Switch on only what your business needs, one step at a time.

Approvals go to **whoever holds the permission**, not to a fixed role. Before switching a control on, make sure **at least two people** hold its approval permission, so nobody is left deciding their own request.

1. **Decide who approves what.** In **Administration → Users & roles**, check that the right people have the roles (and so the permissions) for each decision: discounts, credit, hours transfers and cancellations; baselines, corrections and explanations of engine hours; write-offs, retentions and custody adjustments; verifying payments and remittances.
2. **Register every cash custodian** in **Operations → Staff**, including operators who hold cash but have no login. They do not need a login to be a custodian.
3. **Fill in your reason lists**: **Customer hours → Reason lists**, **Engine hours → Engine-hour reasons**, and **Finance → Cash custody → Reason lists**. To make people always pick a customer-hours reason, switch on **A reason from the tenant list is required**. Cash reasons become required once a list has entries; engine-hour explanations always need a category or reason.
4. **Customer hours** policy: check **Customer hours switched on**, **Walk-in customers allowed**, **Billing methods allowed on jobs** and **Default billing of new jobs**, **Hours activate from**, **Unused hours expire after**, **When a prepaid job has no hours left**, **Highest discount** and **Credit arrangements allowed**. Make sure every machine category has a rate card.
5. **Engine hours** policy: have supervisors propose a **meter baseline** for every machine and approve them ([Task 16](#16-meter-baselines)). Then switch on **Approved meter baseline before a job starts** and, if you want daily readings, **Daily report required** with its **Daily report cut-off**. Set **Open an investigation for unexplained hours after**.
6. **Cash custody** policy: choose **Recorders record for any custodian**, **Receiver acknowledges transfers**, **Receiver acknowledges floats**, **Remit the full balance**, **Daily remittance cut-off**, **Open a case for differences above**, **Write-offs need a second approver** and **Approved retentions allowed**.
7. **Oversight** policy: hide dashboard tiles you do not use and set the **Refused-attempts window**.
8. **Tell your people**, and ask supervisors to **sync their phones** so the apps pick up the new rules.
9. **Watch the Accountability dashboard** daily for the first weeks ([Task 14](#14-accountability-dashboard)).

You can switch any control off again later with a new policy version. Records made while it was on are kept.

## Good practice

- **Decide field job requests quickly.** The supervisor and the customer are waiting on site.
- **Review blocking exceptions every day.** They hold up invoicing.
- **Keep segregation of duties.** Have at least two people with approval and verification rights, so nobody decides their own records.
- **Change policies with a clear reason.** The reason is kept with the version.
- **Prefer Soft GPS enforcement** unless you need strict control. Hard enforcement rejects readings without GPS, and supervisors must retake them.
- **Link every supervisor's login** to their staff record before their first job.
- **Enable push** in the Owner app for "Needs your action" and Critical items.
- **Watch your SMS wallet** if you rely on SMS notifications.
- **Explain engine hours while memories are fresh.** Unexplained hours are a question, not a verdict, and are easiest to explain the same week.
- **Read refused attempts as signals, not accusations.** Most are people trying a button their role does not have.

## Troubleshooting and FAQ

**A completed job can't be invoiced.**
It has a blocking exception or a missing reading. Open the job: "N blocking billing" links to its exceptions. Review them.

**"You requested this reset, so someone else must decide it."**
Segregation of duties. Another approver must decide.

**A supervisor lost their phone.**
Unsent records on that phone cannot be recovered. Contact the Platform Owner to revoke the device so its local data is wiped and it can no longer sync. Then have the supervisor sign in on a new phone.

**The console says the company is read-only.**
Your Asseta subscription is past due or suspended. Pay the open Asseta invoice (**Subscription → Invoices**) or contact the Platform Owner. Access returns when the payment is verified.

**A machine shows Offline or Stale on the map.**
The tracker has not reported for longer than your Tracking policy allows. Check the tracker's power and SIM. **Fleet → Trackers → Ingestion events** shows the last messages. A machine stays billable while its tracker is offline.

**A supervisor says their machine is not in the list when requesting a job.**
Supervisors can request jobs only on machines assigned to them. Assign the machine on its **Staff assignments** tab (web console), then ask them to sync.

**"No rate card applies — set the price to approve".**
There is no rate card for this machine's category. Enter the hourly rate you agreed with the customer, then approve.

**"Approve a meter baseline for this machine first."**
Your policy requires an approved baseline before a job starts. Ask a supervisor to propose one, then approve it ([Task 16](#16-meter-baselines)).

**"This machine already has an approved baseline; use a meter reset to re-base."**
A baseline is set once. If the meter was replaced, use a meter reset.

**The Customer hours menus are missing.**
**Customer hours switched on** is No in your Customer hours policy, or your role lacks the permission.

**I can't make changes in the Owner app.**
The app shows why:

- "You're offline…"
- "Showing saved data…"
- "This company is read-only…"
- "Your role can view this but not change it."
