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

- **Get your company ready to go live** with the [go-live checklist](#getting-started-the-go-live-checklist).
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
- **Check revenue**: switch on the revenue checks, read the **Daily machine sheet**, approve **non-revenue hours** and decide **revenue differences** (never your own explanation). See [Task 22](#22-revenue-checks-how-they-work).
- **Watch engines and fuel**: one investigation per machine and day when an engine runs without work, and fuel compared with engine hours ([Task 27](#27-engine-running-without-work-and-fuel-against-engine-hours)).
- **Make sure money reaches the company**: the company **deposit accounts**, what a remittance must show, and how long cash may be held ([Task 28](#28-deposits-and-how-long-cash-may-be-held)).
- **Follow prepaid hours used over days**: daily drawdown, low-balance warnings and the customer **hours statement** ([Task 29](#29-prepaid-hours-used-over-days-and-weeks)).
- **See who and what needs a look**: the **People scorecard** ([Task 30](#30-people-scorecard)), **Unbilled work** ([Task 31](#31-unbilled-work)), **Idle machines** ([Task 32](#32-idle-machines)) and, if you switch them on, supervisors' **Site check-ins** ([Task 33](#33-site-check-ins)).

By default the owner role holds every permission, so you can also make every decision described in the other chapters (hours discounts, credit, transfers, cancellations, write-offs, retentions, custody adjustments). Your company can give any of these permissions to other roles; the person who proposed something can never decide it.

## Where you work

### Web console menus

| Group | Menus |
|---|---|
| Overview | Dashboard, Go-live checklist, Fleet map, Accountability, People scorecard |
| Field work | My jobs, Readings, Fuel, Expenses, Cash, Customer hours, Site check-in |
| Operations | Jobs, Customers, Staff, Site check-ins |
| Fleet | Machines, Trackers, Sites & geofences, Alerts, Idle machines |
| Customer hours | Hours purchases, Balances, Hours ledger, Work allocations, Transfers, Cancellations, Customer discounts, Credit arrangements, Walk-in customers, Reason lists |
| Engine hours | Reconciliation, Hours to explain, Hour explanations, Meter baselines, Reading corrections, Engine-hour reasons, Non-revenue hours, Daily machine sheet |
| Finance | Hire finance, Cash custody, Expenses & fuel, Approvals, Deposit accounts, Revenue differences, Revenue reasons, Unbilled work, Profitability |
| Risk & review | Exceptions, Meter resets, Investigations, Insights, Security events, Sync conflicts |
| Administration | Policies, Users & roles, Audit log, Subscription, Managed service, Notifications, My access |

When a control is switched off in your policies, its menus are left out. For example, with **Customer hours switched on** set to No, the whole **Customer hours** group and **Field work → Customer hours** disappear. Opening such a page by its address shows "Customer hours is not enabled for your company". **Engine-hour controls switched on** works the same way for the **Engine hours** group. With **Cash custody controls switched on** set to No, **Finance → Cash custody** stays (custodians, custody, floats, remittances and reconciliation), but its Transfers, Overdue remittances, Variances, Retentions, Adjustments and Reason lists tabs disappear. With **Revenue checks switched on** set to No, **Engine hours → Non-revenue hours**, **Engine hours → Daily machine sheet**, **Finance → Revenue differences** and **Finance → Revenue reasons** disappear. Because the first two sit in the **Engine hours** group, they also need **Engine-hour controls switched on**. The **Oversight** policy works the same way: **Overview → People scorecard** appears only with **People scorecard** switched on, **Finance → Unbilled work** only when **Completed work not invoiced after** is set, **Fleet → Idle machines** only when **Machine idle after** is set, and **Operations → Site check-ins** and **Field work → Site check-in** only with **Supervisors check in at the site** switched on.

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
| **Overview** | Your dashboard tiles (fleet, jobs, money, investigations), and the go-live banner until setup is finished |
| **Fleet** | Map or list of machines with live/last-known status; a machine's **Daily machine sheet** |
| **Jobs** | Jobs and their hours, charges, readings, work log, expenses, fuel and customer acknowledgement; **New job**; approve or decline jobs waiting for approval |
| **Alerts** | Tracking alerts to acknowledge or resolve |
| **More** | **Go-live checklist**, Approvals (expenses, meter resets, jobs, cash handovers, exceptions, the accountability requests, revenue differences and non-revenue hours), **Accountability** (with **Unbilled work** and **Idle machines**), Meter exceptions, Field spend, Cash with supervisors (with **Issue float**), **Customer hours**, **People scorecard**, Investigations, Notifications, Settings, Company |

---

## Getting started: the go-live checklist

The Platform Owner (the company that runs Asseta) onboards your company, agrees your subscription fee, and sends you a **temporary password** through a secure channel. Then:

1. **Sign in** at <https://asseta.co.tz> and set your own password. You may also be asked to set up an authenticator app. See [Signing in](README.md#signing-in).
2. **Install the Asseta Owner app** and enable push notifications.
3. **Work through the go-live checklist** below. It lists, in order, everything your company needs before the team relies on Asseta, and opens the screen for each step.

### Where you find it

- **On the dashboard**: while setup is not finished, **Overview → Dashboard** shows the banner **Get ready to go live — N of M done** ("A few setup steps help the team start working in Asseta with confidence."). Click **Continue setup**.
- **In the menu**: **Overview → Go-live checklist** (the page is always there, even after the banner is gone).
- **In the Owner app**: the **Overview** tab shows the same banner (tap it), and **More → Go-live checklist** is the first entry. The app shows the same steps; most of them are done on the web, so a step's button either opens the matching app screen (**Open …**) or **Open on the web**.

Managers hold the checklist permission too, so an office manager can follow and finish the setup with you.

### How it works

- **It ticks itself.** You never tick a step by hand. Asseta checks each step against your company's real records (machines, rates, logins, contracts and so on) and marks it **Done** as soon as the work is saved. Click **Refresh** (pull down in the app) to check again.
- **N of M done** at the top counts the steps that are done or marked not needed (N) out of the steps that apply to your company (M), with a progress bar. With every control switched on there are 13 steps.
- **Steps that do not apply disappear.** A step that sets up a control your company has switched off in its policies is left out of the count. On the web it is listed at the bottom: "Not used by your company, so left out: …". In the Owner app it stays in its place, muted, marked **Does not apply**.
- **Each step** shows its number, its status (**To do**, **Done**, **Not needed**), what it asks for, a count where one helps (for example "3 of 5 machines") and its parts, each ticked separately with its own **Open …** link. The main button, **Go to …**, opens the screen for the first part still to do.
- If your role cannot open that screen, the step says "Someone with access to that screen may need to finish this step."
- When every step is done, the page shows "Everything is in place. You are ready to go live." and **the banner goes away** from the dashboard and the Owner app.

### The 13 steps

| # | Step | Done when | Button goes to |
|---|---|---|---|
| 1 | **Company settings** | Your company's time zone and currency are set. Every day, report and amount uses them. | **Go to Subscription and settings** (**Administration → Subscription**) |
| 2 | **People and logins** | At least one person who records work in the field has a login (a supervisor login); at least **2 people can approve**, so nobody approves their own request; and every supervisor login is linked to a staff record. | **Go to People and access** (**Administration → Users & roles**); the linking part opens **Operations → Staff** |
| 3 | **Machine types and rates** | You have at least one machine type (category), and every active machine type has a current hourly rate. | **Go to Machines** (**Fleet → Machines**); the rates part opens the rate cards in **Operations → Customers** |
| 4 | **Machines** | At least one active machine is registered. | **Go to Machines** (**Fleet → Machines**) |
| 5 | **Trackers** | Every active machine has a tracker fitted as its main tracker **and** is enrolled for tracking on your subscription. | **Go to Trackers** (**Fleet → Trackers**); the parts open **Fleet → Machines** filtered to the machines still missing a tracker or enrolment ([Task 2](#2-enroll-machines-as-billable-assets)) |
| 6 | **Job sites** | At least one job site exists. A boundary (geofence) around a site is **optional**: it is shown as advice and never holds the step back. | **Go to Sites and geofences** (**Fleet → Sites & geofences**) |
| 7 | **Customers and contracts** | At least one active customer has an active contract, so jobs can be priced and billed. | **Go to Customers** (**Operations → Customers**) |
| 8 | **Choose your controls** | Your company has saved its own policy version, **or** someone clicked **Our default controls are fine**. | **Go to Policies** (**Administration → Policies**); see [Set company policies](#3-set-company-policies) and [Switching on the controls](#switching-on-the-controls) |
| 9 | **Reason lists** | Each reason list used by a control you switched on has at least one reason: customer-hours reasons, engine-hour reasons, cash reasons and revenue reasons. Only the lists of switched-on controls count ("2 of 4 lists"). | The first list still empty: **Customer hours → Reason lists**, **Engine hours → Engine-hour reasons**, **Finance → Cash custody → Reason lists** or **Finance → Revenue reasons**. Left out when none of those controls is on. |
| 10 | **Deposit accounts** | At least one bank or mobile-money account that field cash is paid into is added. | **Go to Deposit accounts** (**Finance → Deposit accounts**). Left out when cash custody controls are off. |
| 11 | **Hour-meter starting readings** | Every active machine has an **approved** starting hour-meter reading (meter baseline), so engine hours can be checked from day one. | **Go to Meter baselines** (**Engine hours → Meter baselines**), showing the machines still missing one ([Task 16](#16-meter-baselines)). Left out when engine-hour controls are off. |
| 12 | **Field app signed in** | At least one supervisor has installed the Asseta Supervisor app and signed in on their phone. | **Go to People and access** (**Administration → Users & roles**) |
| 13 | **First job** | At least one job is approved, in progress or completed. From then on Asseta checks work, hours and money every day. | **Go to Jobs** (**Operations → Jobs**) |

Steps 2 to 7 and 13 are described in detail in the [Manager / Dispatcher manual](02-manager-dispatcher.md). While you set up, also assign staff to machines on each machine's **Staff assignments** tab: a supervisor can request jobs only on machines assigned to them (or already on their jobs).

### Mark as not needed

Some steps may not fit your business, for example **Trackers** if you do not use trackers. On a step that is still to do, click **Mark as not needed**, write **Why it is not needed** (at least 3 characters) and confirm. The step then counts as done and shows who marked it, when, and the reason. You can **Undo** it at any time, and if the step's work is later done it shows **Done** anyway.

**Company settings**, **Machine types and rates**, **Machines**, **Choose your controls** and **First job** cannot be marked as not needed: every company needs them.

### Keep the default controls

On **Choose your controls**, if Asseta's default rules suit you, click **Our default controls are fine** (you may add a note). The step is done and shows who confirmed it and when. You can still change any control later under **Administration → Policies**.

### Hide the banner

To hide the dashboard banner before the checklist is finished, click **Hide checklist banner** on the checklist page (**Show banner again** brings it back). The page stays available under **Overview → Go-live checklist**.

Marking steps as not needed, confirming the default controls and hiding the banner need the permission to manage the checklist; by default the Owner and Manager roles hold it. Every choice is recorded in the audit log.

---

## Tasks in the web console

### 1. Read the dashboard

**Overview → Dashboard** ("Fleet, work, money and risk at a glance") has four sections. Until setup is finished, a **Get ready to go live — N of M done** banner sits above them; click **Continue setup** to open the [go-live checklist](#getting-started-the-go-live-checklist).

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
   - **Machine category override**: applies to every machine of one category (only for **Fuel norm per engine hour** in Risk signals).
   - **Machine override**: applies to one machine.
   - **Site override**: applies to one site.
   - **Staff member override**: applies to one person (only for **Days a custodian may hold unremitted cash** in Cash custody).

   On the Policies page itself, the scope buttons **Tenant**, **Machine category**, **Machine**, **Site** and **Staff member** show what applies to one category, machine, site or person. The most specific setting wins.
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
| | **Engine running without work (one case per machine and day)** | Minutes of engine time without work in a day that add a day summary to the machine-day investigation. Empty = off. See [Task 27](#27-engine-running-without-work-and-fuel-against-engine-hours) |
| | **Fuel against engine hours: check period** | **Off**, **Per day** or **Per week**: how often all fuel put into each machine is compared with its engine hours |
| | **Fuel norm per engine hour** | The most litres per engine hour expected. Set it for the company, a **machine category** or one machine (the most specific applies). Empty = off |
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
| | **Take prepaid hours from the balance** | **When the job is completed** (the usual way), or **Every day from the readings (final at completion)**. See [Task 29](#29-prepaid-hours-used-over-days-and-weeks) |
| | **Warn the office when hours left fall to** | The hours level that triggers a low-balance warning. Empty = no warning |
| | **Also send the customer an SMS (uses SMS credits)** | Whether the customer's contact also gets the low-balance warning by SMS |
| Engine hours | **Engine-hour controls switched on** | The master switch for engine-hour accountability. Off: engine-hour pages, baselines, corrections, daily readings and flags are hidden; job meter readings work as before |
| | **Approved meter baseline before a job starts** | Off: jobs start without an approved baseline (reconciliation still begins at the baseline) |
| | **Daily report required**, **Daily report cut-off** | A working machine needs a meter reading every day by the cut-off hour (local time) |
| | **Open an investigation for unexplained hours after** | Days after which unexplained hours open an investigation (empty = never). Time never changes how the hours are classified |
| | **Flag unexplained hours above** | Ignore very small unexplained amounts |
| | **Classifications need a second person**, **Reading corrections need a second person** | Whether explanations of engine hours and meter corrections wait for a second person |
| | **Count readings still under review** | Whether provisional readings count in the engine-hour ledger |
| | **Refuse overlapping job intervals**, **Refuse overlapping work-log entries** | Stop the same engine hour being counted twice |
| Cash custody | **Cash custody controls switched on** | The master switch for the cash controls. Off: transfers, acknowledgements, variances, retentions, adjustments, cash reasons and the remittance cut-off are hidden; collections, floats, remittances and reconciliation stay |
| | **Recorders record for any custodian** | Field recorders may record cash for staff without a login (otherwise own custody only) |
| | **Receiver acknowledges transfers**, **Recording a transfer you receive acknowledges it** | Whether a cash transfer waits for the receiver to confirm the amount |
| | **Receiver acknowledges floats** | Whether a float waits for the receiver to confirm it |
| | **Remit the full balance** | A remittance leaving unretained cash with the custodian is flagged |
| | **Daily remittance cut-off** | Local hour by which cash should be remitted; leave empty for no daily cut-off |
| | **Open a case for differences above** | Cash differences above this amount open an investigation (empty = never automatically) |
| | **Write-offs need a second approver**, **Approved retentions allowed** | Write-off and retention rules |
| | **Require a transaction reference for bank / mobile-money remittances** | A bank or mobile-money remittance needs its transaction reference. Cash handed to the office never needs one |
| | **Require a photo of the deposit slip or payment confirmation** | Every remittance needs at least one photo of the slip or payment message |
| | **Require the company account the money was paid into** | Every remittance must name one of your [deposit accounts](04-accountant.md#23-deposit-accounts) |
| | **Days a custodian may hold unremitted cash** | Empty = no limit. Cash covered by an approved retention does not count. Can be set per site or per staff member |
| Oversight | **Hidden dashboard tiles** | Ticked tiles are hidden from the accountability dashboard |
| | **Refused-attempts window** | How many days of refused attempts the dashboard counts |
| | **People scorecard** | Shows **Overview → People scorecard** and the Owner app's **People scorecard** ([Task 30](#30-people-scorecard)). Off by default |
| | **Cash difference counted as just under the case threshold from** | The share (%) of the cash case threshold from which a difference counts as just under it (90 % by default). Empty = not counted |
| | **Repeated items that open a case**, **Repeated items window**, **Kinds of item counted for repeats** | This many items of one kind for one person within the window raise "Repeated items to look at for one person" for review. Empty = off. The window is 30 days by default |
| | **Completed work not invoiced after** | Days after which a completed, billing-ready job not on an issued invoice is listed and notified ([Task 31](#31-unbilled-work)). Empty = off |
| | **Machine idle after** | Days without a job or engine hours after which an active machine is listed ([Task 32](#32-idle-machines)). Empty = off |
| | **Supervisors check in at the site** | GPS check-ins by supervisors running a job, at the times below ([Task 33](#33-site-check-ins)). Off by default; needs at least one time |
| | **Check-in times**, **Check-in window (before or after)** | Your local times of day (24 h; add as many as you need), and how many minutes before or after each time a check-in counts (60 by default) |
| | **Check-in distance from the site** | Check-ins farther than this from the site centre are marked. Empty = the distance is only shown |
| Revenue checks | **Revenue checks switched on** | The master switch. Off: no daily machine sheet, no revenue differences, and movement inside a job counts as customer work (the usual behaviour) |
| | **Work-log types that are not revenue** | **Movement (mobilization)**, **Standby** and/or **Downtime**: non-billable time of these types inside a job. Standby billing still follows the contract |
| | **Show that time apart from customer work** | On: that time is its own line on the engine-hour ledger and the daily sheet, and is not billed on invoice jobs |
| | **Do not take that time from prepaid hours** | On: prepaid jobs do not draw these hours from the customer's balance |
| | **Non-revenue time needs approval** | On (the default): the time counts as revenue until one person explains it and a second person approves it |
| | **Unexplained hours outside jobs** | **Expected as revenue until approved** (the default) or **Shown only** |
| | **Rate for unexplained hours**, **Tenant rate for unexplained hours** | **The machine category rate card**, or **A tenant rate** that you enter |
| | **Check period** | **Each day**, **Each week (Monday to Sunday)** or **Each completed job**: when hours are matched with money |
| | **Tolerance**, **Tolerance amount** | A shortfall above this percentage of the expected revenue, or above this amount, is a difference to explain |
| | **Open a case for differences above** | Larger differences also open an investigation. Empty = never automatically |
| | **Money counted** | **Issued invoices and prepaid hours used** |
| | **Re-check closed periods for** | Days during which money that arrives later still clears an open difference |

Hire billing, Device sync, Expense capture, Customer hours, Oversight and Revenue checks are company-wide only. They cannot be overridden per machine or site. In Engine hours, only **Approved meter baseline before a job starts** and **Daily report required** can be set per machine. In Cash custody, only **Days a custodian may hold unremitted cash** can be set per site or per staff member. In Risk signals, **Fuel norm per engine hour** can also be set per machine category.

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
- **Deposit accounts**: the company accounts remittances are paid into ([Task 28](#28-deposits-and-how-long-cash-may-be-held)).
- **Revenue differences** and **Revenue reasons**: engine hours that did not turn into the expected money ([Task 25](#25-revenue-differences)).
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

**Notifications open the exact record.** Clicking a notification about a cash transfer, float, remittance, overdue remittance, variance, retention, custody adjustment, hours discount, credit arrangement, hours transfer or cancellation, meter baseline, reading correction or engine-hour explanation opens that record's own page, where you can see it and decide it. Notifications about missing daily reports or unexplained engine hours open the machine's engine-hours page. "Revenue difference to explain" and "Revenue explanation to decide" open the difference, "Non-revenue hours to approve" opens the explanation waiting for a decision, and "Hours running low", "Hours expiring" and "Hours expired" open the hours purchase. The Owner app does the same.

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
| **Revenue differences** | "Engine hours not matched by money, to explain" (or "Oldest open N days"): **To explain**, **Explanations awaiting decision**, the amounts per currency, and how many were **Explained** and **Confirmed** in the last days. Shown only when revenue checks are on |
| **Unbilled work** | Completed jobs not yet invoiced ("Oldest N days", or "Completed jobs not invoiced after N days"): **Jobs**, their worth per currency and the oldest jobs (job, customer, machine, worth and days), each opening the job. The tile title opens [Unbilled work](#31-unbilled-work). Shown only when **Completed work not invoiced after** is set |
| **Idle machines** | Machines without work ("Longest idle N days", or "No job or engine hours for N days"): **Idle**, **With a planned job** and the longest-idle machines, each opening the machine. The tile title opens [Idle machines](#32-idle-machines). Shown only when **Machine idle after** is set |

You can hide tiles you do not use with the **Oversight** policy (**Hidden dashboard tiles**). The page then says "Hidden by your organisation's oversight policy: …". When customer hours are switched off, their tiles are not shown at all. The same summary is in the Owner app under **More → Accountability**.

The figures are never typed in. Each one is worked out from the records behind it, and you can follow it down to those records and their evidence.

### 15. Engine-hour reconciliation

Asseta accounts for every engine hour of each machine. Between two accepted readings, the hours are split into:

- **Customer work**: hours inside a job (from its opening to its closing reading).
- **Not yet explained**: every other hour, until someone explains it as **Non-customer activity** (maintenance, relocation, testing and so on) or an **Identified variance**.

With revenue checks on and **Show that time apart from customer work** set, movement and other non-revenue time inside a job (once approved, if your policy requires approval) appears as its own **Non-revenue** part of the job hours ([Task 22](#22-revenue-checks-how-they-work)).

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

### 22. Revenue checks: how they work

Revenue checks answer one question: **did the machines' work turn into money?** They follow the way a manager reconciles by hand: today's reading minus the last reading, minus movement hours, gives the real working hours; then the hours are matched with the money. The checks are off until you switch them on (**Revenue checks switched on** in the **Revenue checks** policy, [Task 3](#3-set-company-policies)). Every rule below is a setting of your company.

The rules Asseta applies:

- **Movement and other non-revenue time inside a job counts as revenue until approved.** Your policy lists the **Work-log types that are not revenue** (by default **Movement (mobilization)**). With **Non-revenue time needs approval** on (the default), such a work-log entry stays customer work, billable and expected revenue until one person explains it and **a second person approves it** ([Task 24](#24-non-revenue-hours)). With the setting off, the time is non-revenue as soon as it is logged.
- **Engine hours outside jobs are expected revenue until explained.** With **Unexplained hours outside jobs** set to **Expected as revenue until approved** (the default), every engine hour outside a job is expected to bring in money, at **The machine category rate card** or at **A tenant rate**. Only an approved explanation as **non-customer activity** ([Task 17](#17-explain-engine-hours)) removes it. Hours explained as an identified variance stay expected revenue.
- **Expected revenue mirrors billing.** Customer-work hours (less downtime, standby and approved non-revenue time) × the job's approved hourly price, plus standby and the mobilization fee where the contract charges them, less the job's discount. Tax is never revenue.
- **Money attributed** is what was billed for that work: issued invoice lines of the job, plus prepaid hours used × the purchase's price.
- **A difference is opened only for a shortfall.** After each **Check period** (**Each day**, **Each week (Monday to Sunday)** or **Each completed job**) has closed, a shortfall above the **Tolerance** (or the **Tolerance amount**) opens a **revenue difference** ([Task 25](#25-revenue-differences)). More money than expected is never a difference. Work of jobs still running is shown as **Work still in progress**, never as a difference.
- **Late money clears it.** For the **Re-check closed periods for** days (28 unless you change it), an open difference whose money arrives later becomes **Cleared (money arrived)** by itself.
- **Approvals by permission.** Explaining needs the explain permission, deciding needs the decide permission, and the person who explained something can never decide it. In the example roles, owners and managers hold all three revenue permissions; accountants can read and explain.

A revenue difference is a question to answer, not a finding against anyone.

### 23. Daily machine sheet

**Engine hours → Daily machine sheet** ("Each machine's day: engine hours, customer work, non-revenue time, fuel, money and flags") shows one line per machine per day. It shows the last 7 days unless you choose a range.

1. Filter by **Machine**, **Site**, **From day** and **To day** (at most 93 days at a time), or search by machine code or name.
2. Each line shows the **Day**, **Machine**, **Readings** (first → last and how many), **Engine h**, **Customer work h**, **Non-revenue h** (with any hours "awaiting approval"), **Revenue h**, **Non-customer h**, **Unexplained h**, **Jobs**, **Fuel L** (with litres per engine hour), **Money** and **Flags**.
3. Click a line to open the machine's day. It shows:
   - **Hours**: **Engine hours**, **Customer work**, **Revenue hours**, **Non-revenue time** by type, **Non-revenue awaiting approval** ("counted as revenue"), **Non-customer activity**, **Identified variance**, **Not yet explained** and **Readings under review**.
   - **Readings**, **Fuel into the machine** and **Fuel per engine hour**.
   - **Money** per currency: **Expected**, **Of which unexplained hours**, **Work in progress**, **Attributed** and **Difference**.
   - **Flags**, **Jobs** (with **Open job**), **Money sources** (each invoice line or prepaid hours used), **Engine-hour segments**, **Readings** and **Fuel**.
4. Click **Export CSV** to download the sheet with the current filters.

The flags are **Daily report missing**, **Hours to explain**, **Engine on without a job**, **Fuel above the norm** and **Revenue difference**. Each links to the record behind it, such as the investigation of an engine running without work. Nothing on the sheet is typed in: it is worked out from the readings, jobs, invoices, prepaid hours and fuel of the day.

### 24. Non-revenue hours

**Engine hours → Non-revenue hours** ("Time inside jobs that is not customer work, explained by one person and approved by another") reminds you: "Until approved, this time counts as customer work and expected revenue."

**Explain the time** (holders of the explain permission; also from the job's **Work log** tab, in the **Non-revenue approval** column):

1. On the **To explain** tab, filter by **Status** and **Machine**. Each row shows the **Machine**, **Job**, **Type**, **When**, **Hours** and **Status** (for example **Counts as revenue (not explained)**).
2. Click **Explain** on the row. The dialog is **Explain movement (mobilization) · <hours> h**: "Until someone else approves it, this time counts as customer work and expected revenue."
3. Choose the **Reason** from your [revenue reasons](#26-revenue-reasons), write **What happened** (at least 5 characters) and click **Propose explanation**.

*What you'll see:* "Explanation proposed; someone else approves it." The holders of the decide permission get a "Non-revenue hours to approve" notification.

**Approve or reject it** (holders of the decide permission, never the person who explained it):

1. On the **Approvals** tab (it shows **Awaiting decision** by default), click **Decide**, or open the row with **View details**.
2. Check the **Machine**, **Job**, **Type**, **Hours**, **When**, **Reason**, **What happened** and **Explained by**. "Approving removes this time from customer work and expected revenue. Rejecting keeps it as revenue; it can be explained again."
3. Choose **Approve as non-revenue** or **Reject (keep as revenue)**, write a **Note** (at least 5 characters) and click **Record decision**.

*What you'll see:* "Approved as non-revenue time." or "Rejected; the time counts as revenue." Revenue differences of the same days are worked out again straight away.

### 25. Revenue differences

**Finance → Revenue differences** ("Engine hours that did not turn into the expected money: differences to explain") shows **To explain** differences by default. Filter by **Status**, **Machine**, **From day** and **To day**. Each row shows the **Machine**, **Period**, **Expected**, **Attributed**, **Difference**, **Reason** and **Status**.

Open a difference to see its figures: **Expected revenue**, **Of which unexplained hours expected as revenue**, **Work still in progress**, **Money attributed**, **Difference to explain**, **Customer-work hours** and **Non-revenue hours (approved)**, plus its **Jobs**, **Money sources**, any **Investigation** and the **Adjustments**.

**Explain a difference** (holders of the explain permission):

1. Click **Explain**. The dialog is **Explain difference · <machine>**: "Engine hours that did not turn into money are a difference to explain, not a finding against anyone. Your explanation is decided by someone else."
2. Choose the **Reason**, write **What happened** (at least 5 characters) and click **Propose explanation**.

*What you'll see:* "Explanation proposed; someone else decides it." The status becomes **Explanation awaiting decision**.

**Decide a difference** (holders of the decide permission, never the person who explained it):

1. Click **Decide** (or **Confirm difference** on a difference nobody has explained yet).
2. In **Decide difference · <machine>**, choose the **Decision**:
   - **Approve the explanation**: the difference becomes **Explained**.
   - **Reject the explanation (back to open)**: it goes back to **To explain**.
   - **Confirm the difference (money to recover)**: it stays recorded as money to recover (**Confirmed (money to recover)**).
3. Write a **Note** (at least 5 characters) and click **Record decision**.

If your policy sets **Open a case for differences above**, larger differences also open an investigation. When engine hours or non-revenue time are approved later, the figures are worked out again: an open difference is refreshed (and cleared when it is back within tolerance); an explained or confirmed one keeps its figures and gets an **Adjustments** line, with the **Difference after later changes**.

### 26. Revenue reasons

**Finance → Revenue reasons** ("Your list of reasons for explaining revenue differences and non-revenue time") holds your company's own reasons. Holders of the decide permission manage it. Click **New reason**, enter a **Code**, **Name** and **Description**, and click **Create reason**. Deactivate a reason when you no longer use it: "It can no longer be chosen for new explanations; past explanations keep it."

Add your reasons **before** switching revenue checks on, for example Movement to site, Customer delay, Rate agreed lower or Invoice still to issue. Without reasons, nobody can explain anything.

### 27. Engine running without work and fuel against engine hours

Two **Risk signals** settings protect the machines and their fuel. Both are off until you set them ([Task 3](#3-set-company-policies)).

**Engine running without work.** With **Engine running without work (one case per machine and day)** set (in minutes; it can be set per machine), everything that shows one machine working without a job on one day is reviewed together in **one investigation**: tracker engine-on time with no running job, unexplained meter hours outside jobs, and movement outside working hours. The case is titled "Engine running without work: <machine> on <day>". After the day closes, a day summary ("Engine running without work during the day") is added when the engine time without work reaches your minutes. Unexplained meter hours alone can open the case, so it works for machines without a tracker too. Follow it in **Risk & review → Investigations**; the daily machine sheet flags the day as **Engine on without a job** and links to the case.

**Fuel against engine hours.** Choose the **Fuel against engine hours: check period** (**Per day** or **Per week**) and set the **Fuel norm per engine hour**. All fuel issued or bought into each machine is compared with its engine hours in the period, inside or outside jobs. A machine above the norm gets the signal "Fuel above the norm for the engine hours", with the litres, the hours and where the norm was set, and it joins an investigation as usual. A period is judged only when the readings cover it.

Set the norm where it fits best: for the whole company, then per **machine category** (scope **Machine category override**: an excavator uses more than a roller), and per machine where one machine is different. The most specific setting applies. The daily machine sheet shows the litres and the litres per engine hour of each day. The older per-job **Fuel allowance** check works as before.

A signal or an investigation is a prompt to look, not a conclusion about anyone.

### 28. Deposits and how long cash may be held

These settings make sure cash collected in the field reaches the company and can be checked against the bank or mobile-money statement. Finance keeps the details; see the [Accountant manual](04-accountant.md#23-deposit-accounts).

1. **Add your deposit accounts** in **Finance → Deposit accounts**: every bank account, mobile-money wallet and cash office that remittances are paid into. Supervisors pick one when they remit.
2. **Choose what a remittance must show** in the **Cash custody** policy: **Require the company account the money was paid into**, **Require a transaction reference for bank / mobile-money remittances** and **Require a photo of the deposit slip or payment confirmation**.
3. **Set how long cash may be held** with **Days a custodian may hold unremitted cash**. Remote sites may need longer: add a **Site override** for a site, or a **Staff member override** for one person. Cash covered by an approved retention does not count.

Cash held longer than allowed is flagged as an overdue remittance with the reason **Held longer than allowed**, and a "Remittance overdue" notification goes to the custodian and the people who confirm remittances ("… has held … since …, longer than the allowed N days. Please remit or explain."). This works alongside the **Daily remittance cut-off**, which is flagged as **Not remitted by the cut-off**.

When you confirm a remittance, check the **Paid by**, **Company account**, **Reference** and **Photos** against your statement before entering the **Amount received**. If the statement shows more than was declared, the difference opens as **Surplus to explain**.

### 29. Prepaid hours used over days and weeks

Customers who buy hours in advance often use them over days or weeks. Three settings in the **Customer hours** policy keep you and the customer informed. They are described in the [Manager manual](02-manager-dispatcher.md#25-prepaid-hours-used-over-days):

- **Take prepaid hours from the balance**: **Every day from the readings (final at completion)** lowers the balance each day the machine works. Those hours show as **In use by running jobs** until the job is completed. A job that runs out of hours is flagged the same day, not at the end.
- **Warn the office when hours left fall to** and **Also send the customer an SMS (uses SMS credits)**: a low-balance warning so you can offer a top-up before the work stops.
- The customer **Hours statement** (customer page, **Hours statement** tab) with **Download PDF**, to share with the customer.

### 30. People scorecard

**Overview → People scorecard** ("Per person, the items to look at on the machines and cash they were responsible for (default: the last 30 days)") shows, for each person, how many things on their machines and in their cash may need a look. It appears when **People scorecard** is switched on in the **Oversight** policy. By default the owner and manager roles can read it.

The scorecard counts items and links to each record. **A count is not a verdict.** A person with many machines or much cash naturally has more items; open the person and read the records before drawing any conclusion.

**Whose items are whose.** A person's machines are the machines they were assigned to (in any role, on the machine's **Staff assignments** tab) or whose job they supervised, **at the time of the item**. An item on a machine counts for everyone responsible for that machine at that moment. Cash items count for the custodian who held the cash. Refused attempts count for the person whose login made them.

**Read the list.**

1. Choose the period with **From** and **To** (empty = the last 30 days; at most 93 days). Narrow it with **Person** or **Site**, or search by name.
2. People with the most items come first. Active staff with nothing to look at are dimmed; inactive people appear only when they have items in the period.
3. Click a person to open their scorecard.

| Column | What it counts in the period |
|---|---|
| **Person** | The name, employee code and staff kind ("inactive" when the person left) |
| **Machines** | Machines the person was responsible for |
| **Daily reports missing / late** | Days a working machine had no daily report and nobody explained it / days the reading came after the cut-off |
| **Unexplained engine h** | Engine hours on their machines not yet explained, and how many items |
| **Alerts** | Tracking alerts on their machines, how many are still open, and the average hours to acknowledge them |
| **Cash held now** | Cash the person holds and has not remitted, per currency, with the age of the oldest amount |
| **Cash held too long** | Overdue-remittance flags (not remitted by the cut-off, or held longer than allowed) |
| **Cash differences** | Cash differences the person stays accountable for, with the totals per currency and how many were **just under the case threshold** |
| **Revenue differences** | Revenue differences on their machines not cleared, with the totals |
| **Refused attempts** | Actions the person's login tried without the permission, or on their own request |
| **Check-ins missed** | Site check-ins missed, with how many were made (— when check-ins were not required) |
| **Repeats raised** | Times Asseta raised "Repeated items to look at for one person" |
| **Items to look at** | The total |

**Just under the case threshold.** A cash difference is counted here when it is at least the percentage you set (**Cash difference counted as just under the case threshold from**, 90 % unless you change it) of the **Open a case for differences above** amount in the Cash custody policy, without going above it. Several of these for one person are worth a look, because they stay below the amount that opens an investigation.

**One person's scorecard.** The page shows the person's name, staff kind and period, with **Open staff record**. You can change **From**, **To** and choose one **Item** (or **All items**).

- **Figures for the period**: **Machines responsible for**, **Daily reports missing**, **Daily reports late**, **Unexplained engine hours**, **Tracking alerts** (open and acknowledged), **Hours to acknowledge (average / longest)**, **Cash held now**, **Cash held too long (flags)**, **Cash differences**, **Just under the case threshold**, **Revenue differences**, **Refused attempts**, **Site check-ins missed / made** ("Not required in the period" when check-ins were off), **Repeats raised for review** and **Items to look at**.
- One section per item (**Missing daily reports**, **Late daily reports**, **Unexplained engine hours**, **Tracking alerts**, **Cash held too long**, **Cash differences**, **Revenue differences**, **Refused attempts**, **Missed site check-ins**, **Repeated items raised for review**), each listing its records: **When**, **Day**, **Machine**, **Job**, **Amount / hours**, **Status** (with **Just under the case threshold** where it applies) and **Record**.
- The **Record** link opens the record itself: **Open exceptions**, **Open engine-hour ledger**, **Open alerts**, **Open the flag**, **Open difference**, **Open security events**, **Check-ins that day** or **Open investigation**. Links to a control your company has switched off are not shown.

With nothing to look at, the page says "No records to look at in this period."

**Repeated items.** If you set **Repeated items that open a case** in the Oversight policy, Asseta watches for one person having that many items of one kind within the **Repeated items window** (30 days unless you change it). Only the kinds ticked in **Kinds of item counted for repeats** count (cash differences, revenue differences and missing daily reports unless you change it). When it happens, Asseta raises the signal "Repeated items to look at for one person", listing the records, and it joins an investigation in **Risk & review → Investigations** with the person as an involved party. It is raised at most once per person and kind in each window. Like every signal, it asks someone to look; the outcome is decided by people after review.

### 31. Unbilled work

**Finance → Unbilled work** ("Completed, billing-ready jobs not yet on an issued invoice after the company's set days") lists finished work that has not turned into an invoice. It appears when **Completed work not invoiced after** is set in the Oversight policy. By default the owner, manager and accountant roles can read it.

A job is listed when it is **completed**, billed by invoice (not prepaid hours), **billing-ready** (no blocking exceptions, as for invoicing), not on an issued invoice, and was completed at least your set number of days ago. Oldest first.

| Column | What it shows |
|---|---|
| **Job**, **Customer**, **Machine** | Each opens its page |
| **Site**, **Supervisor** | Where and under whom the work was done |
| **Completed** | When the job was completed |
| **Days not invoiced** | Days since completion |
| **Billable h**, **Worth** | The billable hours and the job's total |
| **Invoice** | **Open draft invoice** ("Not issued yet") when a draft already holds the job, otherwise **Create invoice** |

Filter by **Customer**, **Machine** or **Site**, or search by job number or customer. Click a row to open the job.

**Create invoice.** With the invoice permission, click **Create invoice** on a row. The usual new-invoice dialog opens with the customer and that job filled in. After you create it, "Draft invoice created." and the draft opens; issue it as usual (see the [Accountant manual](04-accountant.md#1-create-and-issue-a-hire-invoice)). A job on a draft invoice stays on this list until the invoice is **issued**.

**Notification.** Once per job, the people who make invoices (the invoice permission) receive "Work not yet invoiced: job J-…": "Job J-… for <customer> was completed N days ago and is ready to bill …, but it is not on an issued invoice yet." It opens the job, on the web and in the Owner app.

### 32. Idle machines

**Fleet → Idle machines** ("Active machines with no running job and no engine hours for the company's set days") appears when **Machine idle after** is set in the Oversight policy. By default the owner, manager and accountant roles can read it.

A machine is idle when it is active, has no job in progress, and its latest sign of work (the last completed job, the last meter increase or the last tracker engine-on) is at least your set number of days ago. Longest idle first.

| Column | What it shows |
|---|---|
| **Machine** | Opens the machine |
| **Idle days**, **Idle since** | How long and since when |
| **Last job**, **Completed** | The last job and when it was completed |
| **Last engine activity** | The last meter increase or tracker engine-on |
| **Planned job** | An approved job that has not started yet |

Filter by **Category** or search by asset code or name. Click a row to open the machine. An idle machine is a question about the business (can it be hired, moved or sold?), not about any person. A machine whose engine runs without a job is not idle; that is covered by [Task 27](#27-engine-running-without-work-and-fuel-against-engine-hours).

### 33. Site check-ins

Site check-ins are **optional and off by default**. Only your company can switch them on (**Supervisors check in at the site** in the Oversight policy). They are the only person-location record Asseta keeps on purpose, and each supervisor sees their own check-ins.

**How it works.**

1. You set the **Check-in times** (your company's local times of day, as many as you need), the **Check-in window (before or after)** (60 minutes unless you change it) and, optionally, the **Check-in distance from the site**.
2. At each time, every supervisor **running a job** owes a check-in. They check in from the **Supervisor app** (it works offline and is sent later) or from the web (**Field work → Site check-in**). See the [Supervisor manual](03-supervisor.md#a15-site-check-in).
3. A check-in inside the window counts as **Made**. When the window ends without one, the check-in is **Missed**, and it shows on the [People scorecard](#30-people-scorecard).

**What is recorded.** The time on the phone, the GPS position and its accuracy when there is a fix (a check-in without a fix is still recorded, without coordinates; none are ever substituted), the person, who recorded it, and where it came from (**Web** or **Supervisor app**). The site and job are taken from the job the person is running. With a position, Asseta works out the **distance from the site** centre. If you set a distance, check-ins farther away are marked **Farther than set**; otherwise the distance is only shown.

**See everyone's check-ins.** **Operations → Site check-ins** ("GPS check-ins supervisors made at their sites at the company's set times") lists them newest first, for the owner, manager and accountant roles by default. Columns: **When**, **Person**, **Site**, **Job**, **GPS**, **Distance**, **Distance check** (**Within the distance**, **Farther than set**, **Distance only** or **No distance**) and **From**. Filter by **From** and **To**, **Person** or **Site**. Check-ins farther than set are dimmed so you can find them.

Click one to open it: **Person**, **Recorded by**, **Site**, **Job**, **GPS**, **Coordinates**, **Accuracy**, **Distance from the site** and **Recorded from**, a **Location** map, the history (**Checked in**, **Received by the server**) and **Open the job**. Check-ins are never edited or deleted.

A missed check-in or one far from the site is a prompt to ask, not a conclusion: the supervisor may have had no signal, been between sites or been at the yard.

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

Until your company's setup is finished, a banner above the tiles reads **Get ready to go live — N of M done** ("Open the go-live checklist to see what is left."). Tap it to open the **Go-live checklist**; see [Getting started](#getting-started-the-go-live-checklist).

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
  - **Daily machine sheet** (when revenue checks are on and your role may read them).

**Daily machine sheet.** Tap **Daily machine sheet** on a machine to see its last 14 days, newest first. Each day shows "Engine <hours> h · Revenue <hours> h", any "Difference <amount>" and its flags (**Daily report missing**, **Unexplained hours**, **Engine on without a job**, **Fuel above norm**, **Revenue difference**). Tap a day to open it:

- **Hours**: **Engine hours**, **Customer work**, **Non-revenue** (per type), **Non-revenue awaiting approval**, **Revenue hours**, **Approved non-customer**, **Identified difference**, **Unexplained** and **Awaiting review**.
- **Readings**: **First reading**, **Last reading**, **Readings taken** and each reading.
- **Jobs**, and one **Money** card per currency: **Expected revenue**, **Work still in progress**, **Money attributed**, **Difference** and **Unexplained hours expected as revenue**.
- **Fuel**: the litres and **Litres per engine hour**.
- **Flags** (or "No flags."). A day with an engine running without work shows **Open investigation**.

"Read-only. Figures come from the readings, jobs, invoices and prepaid hours of the day."

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

1. Open it and check the amount, reference and note against the cash or deposit slip. When the supervisor recorded them, the **Handover** card also shows the **Method** (**Cash to the office**, **Bank deposit** or **Mobile money**), **Paid into** (the company account), the **Reference** and one **View deposit slip photo** button per photo (online only). A bank or mobile-money handover without a photo says "No deposit slip photo". The confirm dialog repeats the method, account and reference above the amount.
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
| **Cash write-offs** | "Write off <amount>" ("Surplus to explain: <amount>" when more was received than declared) |
| **Cash retentions** | "Keep <amount>" |
| **Custody adjustments** | "<kind> <amount>" |

Each row shows "Proposed <time> by <name>". To decide one:

1. Tap it. The decision screen shows the **Request**: customer, machine, purchase, amounts, reason, **Proposed by** and so on, with names rather than codes.
2. Under **Decision**, write a note and tap **Approve** or **Reject**. For meter baselines, classifications and corrections the **Note (at least 5 characters)** is always required. For the others the note is optional to approve and required to reject. Rejecting asks **Reject this request?**.

*What you'll see:* "Approved." or "Rejected." On your own request both buttons are disabled: "Someone else must decide your own request". A request that was already decided shows its status and decision.

**Revenue differences and non-revenue hours.** When revenue checks are on, Approvals also has these two sections (needs a connection):

| Section | Row shows |
|---|---|
| **Revenue differences** | "<amount> to explain · <machine>", with the period and status (**To explain** or **Explanation waiting for a decision**) |
| **Non-revenue hours** | "<hours> h <type> · <machine>", with the reason and "Proposed <time> by <name>" |

To handle a revenue difference, tap it. The **Revenue difference** screen shows the **Figures** (**Machine**, **Period**, **Job**, **Status**, **Expected revenue**, **Work still in progress**, **Money attributed**, **Difference**, **Difference after adjustments**, **Customer-work hours**, **Non-revenue hours**, **Unexplained hours**, **Unexplained hours expected as revenue** and any **Investigation**), the **Jobs** with "Expected … · Attributed …", the **Explanation** and any **Adjustments**. Then:

1. **Explain this difference** (with the explain permission, while it is **To explain**): **Choose a reason**, write the **Note (at least 5 characters)** and tap **Send explanation**. *What you'll see:* "Explanation sent. Someone else will decide." If your company has no reasons yet: "Your company has no revenue reasons yet. Add them on the web."
2. **Decision** (with the decide permission): "Approve or reject the explanation, or confirm the difference as money to recover. The person who explained it can't decide." Write a note and tap **Approve explanation**, **Reject explanation** ("Reject this explanation? The difference goes back to "To explain".") or **Confirm difference** ("Confirm this difference? It stays recorded as money to recover."). A difference nobody has explained yet can only be confirmed.

*What you'll see:* "Explanation approved.", "Explanation rejected." or "Difference confirmed." On your own explanation the buttons are disabled: "Someone else must decide on your explanation".

To decide non-revenue hours, tap the row. The decision screen shows the **Machine**, **Job**, **Type**, **Time**, **Hours**, **Reason**, **Note** and **Proposed by**: "Approved time stops counting as revenue. The person who explained it can't approve it." Write a note (at least 5 characters) and tap **Approve** or **Reject**.

### More: other screens

- **Meter exceptions**: open and all exceptions, with **Blocking** marked. Tap one to see it and **Review** it, as in [Approvals](#approvals).
- **Field spend** (read-only): expenses and fuel recorded in the field.
- **Cash with supervisors**: per supervisor and currency, for **Today**, **7 days** or **This month**:
  - **Holding** = opening + floats + collections − approved spending − verified handovers
  - Plus amounts awaiting approval or verification, and the supervisor's claimed handovers (tap one to confirm or dispute it).
  - **Issue float**: opens **Issue a cash float**. Enter the **Amount** (in the card's currency) and a **Note (optional)**, then tap **Issue**. *What you'll see:* "Float issued." The supervisor's cash goes up.
- **Customer hours** (when your company sells prepaid hours): "Prepaid hours with hours left or in use by running jobs. Selling and moving hours is done in the field app or on the web." Each row shows "<purchase> · <customer>", the machine, "<hours> h left" and, while jobs are running, "<hours> h in use by running jobs". Tap one to open the **Hours purchase** (read-only): **Customer**, **Machine**, **Status**, **Bought**, **Activated**, **Used**, **In use by running jobs**, **Moved to other machines**, **Expired**, **Left** and **Awaiting activation**, with a **Machines** card when hours were moved. "Hours in use by running jobs are drawn day by day and become final when the job is completed."
- **Hours statement**: tap **Hours statement** on a purchase to see that customer's statement. Choose **This month**, **Last month**, **Last 3 months** or **This year**. The **Totals** card shows the **Opening balance**, **Bought**, **Activated**, **Used**, **Of which in use by running jobs**, **Moved in**, **Moved out**, **Expired**, **Cancelled**, **Closing balance** and **Awaiting activation (now)**. **Hours used** lists each day and job, marked **Drawn day by day** or **Final**, and "Job still running". Tap **Open PDF** to open the statement in your phone's PDF viewer and share it with the customer (needs a connection).
- **Investigations**: cases and their signals and outcomes. Decisions are recorded in the web console. The new signals read "Engine running without work during the day", "Fuel above the norm for the engine hours" and "Repeated items to look at for one person".
- **People scorecard** (when switched on and your role may read it; after **Customer hours**): choose **Last 7 days**, **Last 30 days** (the default), **This month** or **Last month**. People with the most items come first. Each row shows the name, "N items to look at" (or "Nothing to look at", and **Inactive** for people who left) and up to three of the figures, for example "2 missing reports · 3.5 h unexplained · 2 cash differences". "Counts of items to look at for each person, most first. A count is not a verdict: open the person to see each record." Tap a person (read-only) to see:
  - **Figures**: **Period**, **Machines responsible for**, **Daily reports missing**, **Daily reports late**, **Unexplained engine hours**, **Alerts** ("N · N open"), **Time to acknowledge** ("average … h · longest … h"), **Cash held too long**, **Cash differences**, **Near the case threshold**, **Revenue differences**, **Refused attempts**, **Site check-ins** ("N made · N missed") and **Repeated patterns**.
  - **Cash held now** (when any), with "since <date> (<days>)".
  - **Records**, newest first, for example **Daily report missing**, **Cash difference** or **Missed site check-in** ("Scheduled 14:00"). Tapping a record opens its screen in the app (meter exception, alert, overdue remittance, write-off decision, revenue difference, investigation or machine) when there is one and your role may open it.
- **Unbilled work** and **Idle machines** (read-only): open from their tiles on **Accountability**. Unbilled work shows "<job> · <customer>", the machine and site, "Completed <date> · <days> unbilled", **On a draft invoice** where it applies, and the worth: "Completed jobs not on an issued invoice yet. Invoices are made on the web." Tap a job to open it. Idle machines shows each machine with "Idle since <date> (<days>)", "Last job <job> completed <date>" and "Planned job <job>"; tap one to open the machine.
- **Accountability**: the accountability summary, with the same tiles as [Task 14](#14-accountability-dashboard): **Outstanding approvals**, **Cash** (transfers and floats awaiting acknowledgement, remittances awaiting confirmation, partial remittances, cash per custodian), **Payments awaiting confirmation**, **Discrepancies**, **Investigations**, **Refused attempts**, **Customer hours**, **Hours awaiting activation**, **Engine hours**, **Unexplained engine hours** and **Missing daily reports**. The footer shows the policy version and time. If your company sets a remittance cut-off, the Cash tile shows **Remittances overdue today** with "Cut-off <hour>:00". Tap it to open **Overdue remittances**, where each row reads "Still held after the <hour>:00 cut-off on <day>." Each row also shows its reason: **Not remitted by the daily cut-off** or **Held longer than allowed**. An overdue remittance held too long shows **Held since** and **Allowed** instead of the cut-off, with "Held since <date>, longer than the allowed <days>." When revenue checks are on, the summary also has a **Revenue differences** tile: **To explain**, **Awaiting a decision**, **Amount**, **Oldest open**, **Explained**, **Confirmed** and **Cleared** for the last days, and the machines concerned. Tap it to open Approvals. When set, the **Unbilled work** tile shows **Jobs**, **Value** and **Oldest** ("Completed jobs not on an issued invoice after <days>."), and the **Idle machines** tile shows **Machines** and **Longest idle** ("Machines with no running job and no engine hours for <days>."). Tap either to open its list (when your role may read it).
- **Notifications**: your inbox, with **Unread only** and **Mark all read**. Tapping a notification, or its push message, opens the exact record: the decision screen of a discount, credit arrangement, hours transfer, cancellation, baseline, correction, classification, write-off, retention or custody adjustment; a **Cash transfer** or **Cash float** record; the cash handover; an **Overdue remittance**; a **Revenue difference** or the **Non-revenue hours** decision; or the **Hours purchase** for "Hours running low", expiring or expired hours. Notifications about missing daily reports or unexplained hours open the machine. "Work not yet invoiced" opens the job.

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
| Revenue difference | To explain → Explanation awaiting decision → Explained (or back to To explain); Confirmed (money to recover); Cleared (money arrived) |
| Non-revenue time | Counts as revenue (not explained) → Explanation awaiting decision → Approved as non-revenue / Rejected (counts as revenue) |
| Overdue remittance (reason) | Not remitted by the cut-off; Held longer than allowed |
| Site check-in (each set time) | Upcoming → Due now → Made / Missed |
| Site check-in (distance) | Within the distance; Farther than set; Distance only; No distance |
| Customer hours, cash | See the [Manager](02-manager-dispatcher.md#statuses-and-what-they-mean) and [Accountant](04-accountant.md#statuses-and-what-they-mean) manuals |

## Switching on the controls

This section is the detailed guide behind step 8, **Choose your controls**, of the [go-live checklist](#getting-started-the-go-live-checklist). Do the checklist first: it already covers the people who approve, the reason lists, the deposit accounts and the hour-meter starting readings, and ticks them as they are done. Come back here to decide which controls to switch on and how to set each one; the checklist adds or removes the matching steps as you switch controls on or off.

Every accountability control is a company policy. A control that is off keeps the usual behaviour, and its menus and buttons stay hidden. Asseta starts you with safe defaults: customer hours are available, while daily reports, required baselines, float acknowledgement, full remittance, the remittance cut-off, revenue checks, the engine and fuel checks, remittance requirements, the holding allowance, daily drawdown, low-balance warnings, the people scorecard, repeated items, unbilled work, idle machines and site check-ins are **off** until you switch them on. Switch on only what your business needs, one step at a time.

Approvals go to **whoever holds the permission**, not to a fixed role. Before switching a control on, make sure **at least two people** hold its approval permission, so nobody is left deciding their own request.

1. **Decide who approves what.** In **Administration → Users & roles**, check that the right people have the roles (and so the permissions) for each decision: discounts, credit, hours transfers and cancellations; baselines, corrections and explanations of engine hours; write-offs, retentions and custody adjustments; verifying payments and remittances.
2. **Register every cash custodian** in **Operations → Staff**, including operators who hold cash but have no login. They do not need a login to be a custodian.
3. **Fill in your reason lists**: **Customer hours → Reason lists**, **Engine hours → Engine-hour reasons**, and **Finance → Cash custody → Reason lists**. To make people always pick a customer-hours reason, switch on **A reason from the tenant list is required**. Cash reasons become required once a list has entries; engine-hour explanations always need a category or reason.
4. **Customer hours** policy: check **Customer hours switched on**, **Walk-in customers allowed**, **Billing methods allowed on jobs** and **Default billing of new jobs**, **Hours activate from**, **Unused hours expire after**, **When a prepaid job has no hours left**, **Highest discount** and **Credit arrangements allowed**. Make sure every machine category has a rate card.
5. **Engine hours** policy: check **Engine-hour controls switched on**. Have supervisors propose a **meter baseline** for every machine and approve them ([Task 16](#16-meter-baselines)). Then switch on **Approved meter baseline before a job starts** and, if you want daily readings, **Daily report required** with its **Daily report cut-off**. Set **Open an investigation for unexplained hours after**.
6. **Cash custody** policy: check **Cash custody controls switched on**, then choose **Recorders record for any custodian**, **Receiver acknowledges transfers**, **Receiver acknowledges floats**, **Remit the full balance**, **Daily remittance cut-off**, **Open a case for differences above**, **Write-offs need a second approver** and **Approved retentions allowed**.
7. **Oversight** policy: hide dashboard tiles you do not use and set the **Refused-attempts window**.
8. **Revenue checks** policy: first switch on **Engine-hour controls switched on** and approve the baselines (the daily machine sheet needs them), fill in **Finance → Revenue reasons** ([Task 26](#26-revenue-reasons)), and make sure at least two people hold the revenue decide permission. Then set **Revenue checks switched on**, the **Work-log types that are not revenue**, **Non-revenue time needs approval**, **Unexplained hours outside jobs** and its rate, the **Check period**, **Tolerance** / **Tolerance amount** and **Open a case for differences above**.
9. **Risk signals** policy: set **Engine running without work (one case per machine and day)**, the **Fuel against engine hours: check period** and the **Fuel norm per engine hour**, first for the company and then per machine category (scope **Machine category override**) and per machine where needed ([Task 27](#27-engine-running-without-work-and-fuel-against-engine-hours)).
10. **Deposits**: add every company account in **Finance → Deposit accounts**, then in the **Cash custody** policy choose **Require the company account the money was paid into**, **Require a transaction reference for bank / mobile-money remittances**, **Require a photo of the deposit slip or payment confirmation** and **Days a custodian may hold unremitted cash**, with site or staff member overrides for remote sites ([Task 28](#28-deposits-and-how-long-cash-may-be-held)).
11. **Prepaid hours over days**: in the **Customer hours** policy choose **Take prepaid hours from the balance**, **Warn the office when hours left fall to** and, if customers should be told, **Also send the customer an SMS (uses SMS credits)** (check your SMS wallet). Make sure customers' contact phone numbers are filled in.
12. **Oversight of people and machines** (Oversight policy): switch on **People scorecard** and check **Cash difference counted as just under the case threshold from** ([Task 30](#30-people-scorecard)). If you want repeated items reviewed, set **Repeated items that open a case**, the **Repeated items window** and the **Kinds of item counted for repeats**. Set **Completed work not invoiced after** ([Task 31](#31-unbilled-work)) and **Machine idle after** ([Task 32](#32-idle-machines)). Only if you want site check-ins: tell your supervisors first, then switch on **Supervisors check in at the site** with the **Check-in times**, the **Check-in window (before or after)** and, if you like, the **Check-in distance from the site** ([Task 33](#33-site-check-ins)). Check-ins need each supervisor's login linked to their staff record.
13. **Tell your people**, and ask supervisors to **sync their phones** so the apps pick up the new rules.
14. **Watch the Accountability dashboard** daily for the first weeks ([Task 14](#14-accountability-dashboard)), the **Daily machine sheet** and **Revenue differences** when revenue checks are on, and the **People scorecard** once a week.

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
- **Look at the daily machine sheet every morning** when revenue checks are on. A flag on yesterday's line is easiest to explain today.
- **Decide non-revenue hours promptly.** Until approved, movement time counts as revenue and can open a revenue difference.
- **Set fuel norms per machine category**, not one figure for every machine.
- **Read the scorecard as a list of questions.** Open the person and the records before talking to them; a high count often just means many machines or much cash.
- **Clear unbilled work weekly.** Every job on the list is money the customer has not been asked for yet.
- **Tell supervisors before switching site check-ins on**, and why. They see every check-in they make.
- **Check remittances against the statement.** Compare the account, reference and slip photo with your bank or mobile-money statement before confirming.

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

**The Engine hours menus, or some Cash custody tabs, are missing.**
**Engine-hour controls switched on** or **Cash custody controls switched on** is No in that policy, or your role lacks the permission.

**The Daily machine sheet, Non-revenue hours or Revenue differences menus are missing.**
**Revenue checks switched on** is No in your Revenue checks policy, or your role lacks the revenue permission. The two Engine hours menus also need **Engine-hour controls switched on**.

**"Revenue checks are switched off for your company (Policies → Revenue checks)."**
Switch them on in the Revenue checks policy, or ask the owner.

**"You explained this, so someone else must decide it."**
Segregation of duties. Another person with the decide permission must decide.

**"No active reasons; add them under Revenue reasons".**
Add your reasons in **Finance → Revenue reasons** ([Task 26](#26-revenue-reasons)).

**A movement entry still counts as revenue.**
It has not been approved yet. Explain it ([Task 24](#24-non-revenue-hours)) and have someone else approve it.

**The People scorecard, Unbilled work, Idle machines or Site check-ins menus are missing.**
The matching setting in the **Oversight** policy is off or empty, or your role lacks the permission ([Switching on the controls](#switching-on-the-controls), step 12).

**A person's scorecard shows items on a machine they never drove.**
Items count for everyone responsible for the machine at that time: its assigned staff and the supervisor of its job. Open the record to see the machine and job.

**The Oversight policy will not save with site check-ins switched on.**
Check-ins need at least one time. Add at least one **Check-in time** before switching on **Supervisors check in at the site**.

**I can't make changes in the Owner app.**
The app shows why:

- "You're offline…"
- "Showing saved data…"
- "This company is read-only…"
- "Your role can view this but not change it."
