# Asseta user manual

Welcome to Asseta. This manual is for the people who work in a tenant company. It explains how to use Asseta day to day, one chapter per role. Find your role in the table below and open its chapter. Read this page first: it covers signing in and the words Asseta uses.

## What Asseta is

Asseta is a subscription service for companies that own and hire out heavy equipment, such as excavators, loaders, graders and trucks. It is provided by the **Platform Owner** (Asseta). Your company subscribes, pays a fee per billable machine, and is set up on Asseta as a **tenant**. From then on your company uses Asseta to manage its own machines, jobs, people and money.

Asseta helps your company:

- Know **where every machine is**, using GPS trackers fitted to the machines.
- Run **hire jobs** from start to finish, with hour-meter readings photographed in the field, a work log, and the customer's acknowledgement.
- **Bill customers** for the right hours and follow their payments.
- Control **fuel, field expenses and cash** held by supervisors.
- Spot readings, movements and money that **need review**, with the evidence attached.
- Keep a **chain of accountability** for every customer hour, every engine hour and every amount of cash, with the controls your company switches on (see **Accountability controls** in [Common concepts](#common-concepts)).
- Check that **every working hour turns into money** that reaches the company, and that machines and fuel are used only for work (see **Revenue checks** in [Common concepts](#common-concepts)).

Asseta works in three places:

| Where | Who uses it | Notes |
|---|---|---|
| **Web console**, <https://asseta.co.tz> | Everyone with a login | The full system, on a laptop or desktop. Needs an internet connection. |
| **Asseta Supervisor** app (Android and iPhone) | Field supervisors | Works **offline** and syncs when a connection is available. |
| **Asseta Owner** app (Android and iPhone) | Owners and managers | Dashboard, fleet map, jobs, alerts and approvals on the go. The boss can approve or create jobs, confirm cash handovers, review exceptions and issue cash floats from far away, decide accountability requests and revenue differences, follow the accountability summary, the daily machine sheet and customers' prepaid hours. Keeps read-only copies for offline viewing. |

The Android and iPhone versions of each app look and work the same.

Each company using Asseta has its own private account, called a **tenant**. Nobody from another company can see its data, and the Platform Owner does not see a tenant's business data unless the tenant grants a managed-service mandate.

## Roles

| Role | Who it is for | Works mainly in | Chapter |
|---|---|---|---|
| **Tenant Owner** | Owner or top administrator of the hire company | Web console + Owner app | [01-tenant-owner.md](01-tenant-owner.md) |
| **Manager / Dispatcher** | Operations manager, dispatcher | Web console (+ Owner app) | [02-manager-dispatcher.md](02-manager-dispatcher.md) |
| **Supervisor** | Field supervisor on site | Supervisor app (+ web **Field work**) | [03-supervisor.md](03-supervisor.md) |
| **Accountant / Finance** | Accountant, bookkeeper, cashier | Web console | [04-accountant.md](04-accountant.md) |
| **Operator** | Machine operator | Web console (notifications only) | [05-operator.md](05-operator.md) |

The two most important users are the **Supervisor**, who records the field work, and the **Tenant Owner**, who runs the company, often from far away (for example in Dar es Salaam while the machines work in Katavi).

Roles are examples set up for each company. Your company can adjust them, so you may see slightly more or fewer menus than described here. If a menu is missing, your role does not include it.

## Signing in

### Web console

1. Open <https://asseta.co.tz> and click **Sign in**.
2. The secure Asseta sign-in page opens. Its address starts with `https://asseta.co.tz/auth/`. Enter your username (usually your e-mail) and password.
3. **First sign-in:** use the temporary password you were given. You will be asked to choose a new one. Some accounts, such as platform staff, are also asked to set up an authenticator app for one-time codes.
4. If you belong to more than one company, Asseta opens the last one you used. Supervisors land on **My jobs**, and most others on the **Dashboard**.

The top bar shows:

- The company switcher
- A connection indicator
- The **notification bell**
- Your name
- A light/dark toggle
- **Sign out**

### Mobile apps

1. Install **Asseta Supervisor** or **Asseta Owner** on your phone.
2. Tap **Sign in**. The same secure sign-in page opens in your phone's browser.
3. Choose your company under **Choose a company**. If you have only one company, it opens by itself.

You stay signed in between uses, even offline. Signing out of the Supervisor app with unsent work keeps that work safely on the phone until you sign in again.

### Change your password

- **Web:** open **My access** (in the Administration menu group). Under **Sign-in & security**, click **Change password**. You may be asked for your current password first.
- **Supervisor app:** account menu (person icon) → **Change password**.
- **Owner app:** **More → Settings → Change password**.

In every case the secure Asseta sign-in page opens. You need an internet connection.

**Forgotten password:** ask your company's administrator (normally the owner) or the Platform Owner to reset it.

### Switch company

Some people work for more than one company. The Platform Owner working inside a tenant under a managed-service mandate is one example.

- **Web:** click the company name at the top left and choose another. With many companies, use the search box.
- **Apps:** account menu or **More → Settings** → **Switch company**.

A company may show **Read only**. Its Asseta subscription is restricted, and you can view but not change anything. Your data is kept, never deleted. A company may also show **Blocked**: it cannot be opened, so contact your account owner.

### See what you are allowed to do

**My access** in the web console lists your companies, your permissions and your menus.

## Common concepts

| Term | Meaning |
|---|---|
| **Tenant / company** | Your company's private Asseta account. |
| **Machine** | One piece of equipment, with a unique asset code. Machines can be active, out of service or retired. Your Asseta subscription is charged per **billable machine**. |
| **Tracker** | The GPS device fitted to a machine. It reports position and, if supported, engine on/off. |
| **Connectivity** | How fresh a machine's position is: **Live**, **Recent**, **Stale**, **Offline**, **Never reported** or **No tracker**. |
| **Geofence / job site** | A place drawn on the map. An *allowed area* alerts when a machine leaves, and a *restricted area* alerts when one enters. |
| **Customer, contract, rate card** | Who you hire to, under which agreement, and your standard hourly price per machine category. |
| **Job** | One hire of one machine to a customer under a contract. It moves through **Draft → Pending approval → Approved → In progress → Completed**, or **Cancelled**. The hourly price is fixed when the job is approved. |
| **Two ways a job starts** | The **supervisor requests it from the field** (on a machine assigned to them; it waits for approval and the owner sets the price), or the **office or owner creates it and assigns a supervisor**. Either way it is approved before work starts, in the web console or the Owner app. |
| **Reading** | A photo-backed hour-meter value. A job needs an **opening reading** before it can start, and a **closing reading** and a **customer acknowledgement** before it can be completed. Each reading also records a GPS location. |
| **Customer acknowledgement** | The customer's representative confirming the work: a signature on screen or their name. |
| **Work log** | Entries for **Work**, **Standby**, **Downtime**, **Mobilization** and **Notes**. Meter hours are not automatically billable hours; the work log and the contract decide. |
| **Exception** | A note Asseta records when evidence looks unusual, for example a reading lower than before, no GPS fix, or a reused photo. An exception is **not an accusation**; it needs review. **Blocking** exceptions stop a job from being invoiced until reviewed. |
| **Reading status** | **Accepted**; **Provisional** (kept and counted, but needs review); **Rejected** (kept as evidence, not used; take it again); **Superseded** (replaced by an approved correction). |
| **Meter reset** | A documented change of the hour meter (replaced or rolled over). It must be approved by someone other than the person who requested it. |
| **Approval** | A decision by a second person. Examples: an expense above the auto-approval limit, or a job's price. |
| **Segregation of duties** | Nobody decides their own request. The person who records a payment, handover or expense cannot verify or approve it. |
| **Custody / cash in hand** | Cash a supervisor (or any cash custodian) is accountable for. **Opening + floats + collections − approved cash expenses − verified handovers = outstanding.** With the accountability controls on, acknowledged transfers in and out, approved adjustments and the amount actually received on remittances also count. |
| **Claimed vs verified** | Money recorded by one person is **Claimed (unverified)** until a second person confirms it. Only **Verified** money changes balances. |
| **Policy** | Your company's rules, for example reading mode (Automatic photo + on-device reading, or Manual), GPS strictness, expense limits and tracking thresholds. Policies are versioned; old records keep the version that applied. |
| **Offline and sync** | The Supervisor app saves everything on the phone, encrypted, and **syncs** when a connection returns. Nothing is marked synced until the server confirms it, and retries never create duplicates. The Owner app keeps **read-only** copies, clearly marked stale. |
| **Investigation** | A case grouping related signals for human review. Possible outcomes are **Issue confirmed**, **Unconfirmed** and **Legitimate explanation**. |
| **Alert** | A tracking event, such as leaving a geofence, moving outside working hours, or a tracker going offline or losing power. Alerts are **Open**, then **Acknowledged**, then **Resolved**. |
| **Notifications** | Messages in your in-app **inbox** (the bell). Depending on settings and severity, they can also reach you by phone **push**, **SMS** (uses your company's SMS credits) or **e-mail**. Some important ones are required and cannot be switched off. Clicking a notification (or tapping it in an app) opens the exact record it is about, such as a cash transfer, a remittance or a request awaiting your decision. |
| **Audit log** | A permanent record of who changed what, and when. |
| **Accountability controls** | Extra checks that let management trace every customer hour, every engine hour and every amount of cash. Each control is **switched on or off by your company's policies** (see [Set company policies](01-tenant-owner.md#3-set-company-policies)). A control that is off keeps the usual behaviour, and its menus and buttons are hidden. |
| **Approvals by permission** | Every accountability decision (discounts, credit, transfers, baselines, corrections, write-offs, retentions and so on) goes to **whoever holds the matching permission**, whatever their role. The roles in this manual are examples. **Nobody decides their own request.** |
| **Customer hours (prepaid)** | Hours a customer buys in advance for **one specific machine**. A purchase gets a unique number (HP-…), uses the standard rate card and any approved discount, and is **separate from its payment**. Hours become usable (**activated**) only after the payment is **verified** by another person, or on **approved credit**. |
| **Walk-in customer** | A customer served without full registration: a name and, optionally, a phone number. Asseta gives them a WALK-… code. |
| **Hours ledger** | The permanent list of hour movements on each purchase: activated, consumed, moved between machines, expired, reversed. Balances are always worked out from it, never typed in. |
| **Work allocation** | When a prepaid job is completed, its billable hours are taken from the customer's activated hours for that machine. Hours beyond what is available are not taken; they are flagged as **Hours beyond purchase** for review. |
| **Meter baseline** | The approved starting hour-meter reading of a machine, proposed by one person and approved by another. Engine-hour reconciliation starts from it. |
| **Daily reading** | A meter reading taken outside a job (for example at the end of the day), so every engine hour is accounted for. |
| **Engine-hour reconciliation** | Every engine hour between two accepted readings is either **customer work** (inside a job) or **not yet explained**. Unexplained hours are later explained as approved non-customer work (maintenance, relocation and so on) or an identified difference. Time alone never changes how hours are classified; after a set number of days an investigation is opened instead. |
| **Cash custodian** | Any staff member who holds company cash, **with or without an Asseta login**. People who may record cash (recorders, such as supervisors and managers) can record collections, transfers and remittances on a custodian's behalf if your company allows it. |
| **Cash transfer** | Cash handed from one custodian to another in the field. The receiver **acknowledges** the amount actually received. A transfer is never money received by the company. |
| **Remittance** | Cash handed over to the company (shown in the apps as a **handover**). The office records the **amount actually received**. Only that confirmed amount reduces the custodian's balance. |
| **Cash difference (variance)** | Opened automatically when the amount declared and the amount received differ. It is resolved with an outcome (recovered, corrected error or written off). A difference is a fact to review, **not an accusation**. |
| **Retention** | An approved permission for a custodian to keep part of their cash instead of remitting everything. |
| **Custody adjustment** | A correcting entry on a custodian's cash (a reversal or an adjustment), with a reason, approved by a second person. Records are never edited or deleted. |
| **Security event** | A refused attempt: someone tried an action without the permission, or tried to decide their own request. Recorded for oversight, not as a verdict. |
| **Revenue checks** | A control that matches each machine's engine hours with the money they brought in. It is **switched on or off by your company's policy** (**Revenue checks switched on**), like every other control. |
| **Non-revenue time** | Time inside a job that is not customer work, such as moving the machine to or from the site. By default it **counts as revenue until one person explains it and a second person approves it**. |
| **Unexplained hours expected as revenue** | Engine hours outside any job that nobody has explained. With revenue checks on, they are **expected to bring in money** (at the rate card price, unless your company chooses otherwise) until they are approved as non-customer activity. |
| **Daily machine sheet** | One line per machine per day: readings, engine hours, customer work, non-revenue time, fuel, expected money, money received and flags. It is worked out from the records, never typed in. |
| **Revenue difference** | Opened when the money attributed to a machine's work in a period falls short of the expected revenue by more than your company's tolerance. It is **a difference to explain, not an accusation**. One person explains it with a reason; another decides. |
| **Engine running without work** | A machine's engine ran on a day without a job. Tracker signals, unexplained meter hours and after-hours movement of that machine and day are reviewed together in **one investigation**. |
| **Fuel norm per engine hour** | The most litres per engine hour your company expects. It can be set for the whole company, for a machine category or for one machine. Fuel above the norm opens a signal for review. |
| **Deposit account** | A company bank account, mobile-money wallet or cash office that remittances are paid into. |
| **Remittance details** | How a remittance was paid (**cash to the office**, **bank deposit** or **mobile money**), into which deposit account, the transaction reference and photos of the deposit slip. Your company decides which of these are required. |
| **Holding allowance** | The number of days a custodian may hold cash before remitting it. It can be different per site or per person. Cash held longer is flagged **Held longer than allowed**. |
| **Daily drawdown** | Prepaid hours taken from the customer's balance **every day** the machine works, instead of only when the job is completed. Until the job is completed these hours show as **In use by running jobs**. |
| **Low-balance warning** | A notice to the office (and, if your company chooses, an SMS to the customer) when a customer's prepaid hours fall to a set level. |
| **Hours statement** | A customer's prepaid hours for a period: opening balance, bought, activated, used per day and job, moved, expired and closing balance. It can be downloaded as a PDF. |
| **Sync conflict** | A field record sent offline that the server could not apply (for example two people using the same remaining hours). It is kept with its evidence for the office to resolve. |
| **Managed service** | An arrangement, with your written consent, under which the Platform Owner operates your account for you. Everything they do is recorded and visible to you, and you can revoke it. |

## Getting help

- If something does not work, note the **Reference** code shown with the error message and give it to your administrator or the Platform Owner.
- If a menu or button is missing, your role probably does not include it. Ask your company's owner.
