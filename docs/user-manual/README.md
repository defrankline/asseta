# Asseta user manual

Welcome to Asseta. This manual explains how to use Asseta day to day, one chapter per role. Find your role in the table below and open its chapter. Read this page first: it covers signing in and the words Asseta uses.

## What Asseta is

Asseta is an online service for companies that hire out heavy equipment, such as excavators, loaders, graders and trucks. It helps the company:

- Know **where every machine is**, using GPS trackers fitted to the machines.
- Run **hire jobs** from start to finish, with hour-meter readings photographed in the field, a work log, and the customer's acknowledgement.
- **Bill customers** for the right hours and follow their payments.
- Control **fuel, field expenses and cash** held by supervisors.
- Spot readings, movements and money that **need review**, with the evidence attached.

Asseta works in three places:

| Where | Who uses it | Notes |
|---|---|---|
| **Web console**, <https://asseta.co.tz> | Everyone with a login | The full system, on a laptop or desktop. Needs an internet connection. |
| **Asseta Supervisor** app (Android and iPhone) | Field supervisors | Works **offline** and syncs when a connection is available. |
| **Asseta Owner** app (Android and iPhone) | Owners and managers | Dashboard, fleet map, jobs, alerts and approvals on the go. Keeps read-only copies for offline viewing. |

The Android and iPhone versions of each app look and work the same.

Each company using Asseta has its own private account. In Asseta that account is called a **tenant**. Nobody from another company can see your data.

## Roles

| Role | Who it is for | Works mainly in | Chapter |
|---|---|---|---|
| **Tenant Owner** | Owner or top administrator of the hire company | Web console + Owner app | [01-tenant-owner.md](01-tenant-owner.md) |
| **Manager / Dispatcher** | Operations manager, dispatcher | Web console (+ Owner app) | [02-manager-dispatcher.md](02-manager-dispatcher.md) |
| **Supervisor** | Field supervisor on site | Supervisor app (+ web **Field work**) | [03-supervisor.md](03-supervisor.md) |
| **Accountant / Finance** | Accountant, bookkeeper, cashier | Web console | [04-accountant.md](04-accountant.md) |
| **Operator** | Machine operator | Web console (notifications only) | [05-operator.md](05-operator.md) |
| **Platform Owner** | Asseta's own staff running the service | Web console (platform) | [06-platform-owner.md](06-platform-owner.md) |
| **Platform Auditor** | Auditors of the Asseta platform | Web console (platform, read-only) | [07-platform-auditor.md](07-platform-auditor.md) |

The two most important users are the **Supervisor**, who records the field work, and the **Tenant Owner**, who runs the business.

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

**Forgotten password:** ask your company's administrator (normally the owner) or Asseta support to reset it.

### Switch company

Some people work for more than one company. Asseta staff working under a managed-service mandate are one example.

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
| **Reading** | A photo-backed hour-meter value. A job needs an **opening reading** before it can start, and a **closing reading** and a **customer acknowledgement** before it can be completed. Each reading also records a GPS location. |
| **Customer acknowledgement** | The customer's representative confirming the work: a signature on screen or their name. |
| **Work log** | Entries for **Work**, **Standby**, **Downtime**, **Mobilization** and **Notes**. Meter hours are not automatically billable hours; the work log and the contract decide. |
| **Exception** | A note Asseta records when evidence looks unusual, for example a reading lower than before, no GPS fix, or a reused photo. An exception is **not an accusation**; it needs review. **Blocking** exceptions stop a job from being invoiced until reviewed. |
| **Reading status** | **Accepted**; **Provisional** (kept and counted, but needs review); **Rejected** (kept as evidence, not used; take it again); **Superseded** (replaced by an approved correction). |
| **Meter reset** | A documented change of the hour meter (replaced or rolled over). It must be approved by someone other than the person who requested it. |
| **Approval** | A decision by a second person. Examples: an expense above the auto-approval limit, or a job's price. |
| **Segregation of duties** | Nobody decides their own request. The person who records a payment, handover or expense cannot verify or approve it. |
| **Custody / cash in hand** | Cash a supervisor is accountable for. **Opening + floats + collections − approved cash expenses − verified handovers = outstanding.** |
| **Claimed vs verified** | Money recorded by one person is **Claimed (unverified)** until a second person confirms it. Only **Verified** money changes balances. |
| **Policy** | Your company's rules, for example reading mode (Automatic photo + on-device reading, or Manual), GPS strictness, expense limits and tracking thresholds. Policies are versioned; old records keep the version that applied. |
| **Offline and sync** | The Supervisor app saves everything on the phone, encrypted, and **syncs** when a connection returns. Nothing is marked synced until the server confirms it, and retries never create duplicates. The Owner app keeps **read-only** copies, clearly marked stale. |
| **Investigation** | A case grouping related signals for human review. Possible outcomes are **Issue confirmed**, **Unconfirmed** and **Legitimate explanation**. |
| **Alert** | A tracking event, such as leaving a geofence, moving outside working hours, or a tracker going offline or losing power. Alerts are **Open**, then **Acknowledged**, then **Resolved**. |
| **Notifications** | Messages in your in-app **inbox** (the bell). Depending on settings and severity, they can also reach you by phone **push**, **SMS** (uses your company's SMS credits) or **e-mail**. Some important ones are required and cannot be switched off. |
| **Audit log** | A permanent record of who changed what, and when. |
| **Managed service** | An arrangement, with your written consent, under which Asseta staff operate your account for you. Everything they do is recorded and visible to you, and you can revoke it. |

## Getting help

- If something does not work, note the **Reference** code shown with the error message and give it to your administrator or Asseta support.
- If a menu or button is missing, your role probably does not include it. Ask your company's owner.
