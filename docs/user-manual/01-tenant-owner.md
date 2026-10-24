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

## Where you work

### Web console menus

| Group | Menus |
|---|---|
| Overview | Dashboard, Fleet map |
| Field work | My jobs, Readings, Fuel, Expenses, Cash |
| Operations | Jobs, Customers, Staff |
| Fleet | Machines, Trackers, Sites & geofences, Alerts |
| Risk & review | Exceptions, Meter resets, Investigations, Insights |
| Finance | Hire finance, Expenses & fuel, Approvals, Profitability |
| Administration | Policies, Users & roles, Audit log, Subscription, Managed service, Notifications, My access |

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
| **More** | Approvals (expenses, meter resets, jobs, cash handovers, exceptions), Meter exceptions, Field spend, Cash with supervisors (with **Issue float**), Investigations, Notifications, Settings, Company |

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

Hire billing, Device sync and Expense capture are company-wide only. They cannot be overridden per machine or site.

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

- **Hire finance**: hire invoices, customer payments, the **All supervisors** cash summary, cash custody, handovers and the daily reconciliation.
- **Expenses & fuel**: all expenses and fuel events, and expense categories.
- **Profitability**: by machine, job or customer.

All three are described in the [Accountant manual](04-accountant.md).

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
2. Tap **Confirm received** (a note is optional), or **Dispute** (a **Reason** is required). Confirm **Confirm this handover?** or **Dispute this handover?**.

*What you'll see:* "Handover confirmed." or "Handover disputed." Only a confirmed handover reduces the supervisor's cash. A disputed one shows as **Rejected** to the supervisor, with your reason.

For an exception ("<type> on <job number>"):

1. Open it to see the status, severity, evidence and **Open job**. Tap **Review**.
2. Choose the **Outcome**: **Explained — a legitimate reason was found** or **Discrepancy confirmed — evidence stands as recorded**.
3. Write the **Review note** (5 to 2000 characters) and tap **Record review**. *What you'll see:* "Exception reviewed."

The app reminds you: "The person who submitted a request can't decide it (segregation of duties)." The same applies to handovers: you cannot confirm one you recorded yourself.

### More: other screens

- **Meter exceptions**: open and all exceptions, with **Blocking** marked. Tap one to see it and **Review** it, as in [Approvals](#approvals).
- **Field spend** (read-only): expenses and fuel recorded in the field.
- **Cash with supervisors**: per supervisor and currency, for **Today**, **7 days** or **This month**:
  - **Holding** = opening + floats + collections − approved spending − verified handovers
  - Plus amounts awaiting approval or verification, and the supervisor's claimed handovers (tap one to confirm or dispute it).
  - **Issue float**: opens **Issue a cash float**. Enter the **Amount** (in the card's currency) and a **Note (optional)**, then tap **Issue**. *What you'll see:* "Float issued." The supervisor's cash goes up.
- **Investigations**: cases and their signals and outcomes. Decisions are recorded in the web console.
- **Notifications**: your inbox, with **Unread only** and **Mark all read**.

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

## Good practice

- **Decide field job requests quickly.** The supervisor and the customer are waiting on site.
- **Review blocking exceptions every day.** They hold up invoicing.
- **Keep segregation of duties.** Have at least two people with approval and verification rights, so nobody decides their own records.
- **Change policies with a clear reason.** The reason is kept with the version.
- **Prefer Soft GPS enforcement** unless you need strict control. Hard enforcement rejects readings without GPS, and supervisors must retake them.
- **Link every supervisor's login** to their staff record before their first job.
- **Enable push** in the Owner app for "Needs your action" and Critical items.
- **Watch your SMS wallet** if you rely on SMS notifications.

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

**I can't make changes in the Owner app.**
The app shows why:

- "You're offline…"
- "Showing saved data…"
- "This company is read-only…"
- "Your role can view this but not change it."
