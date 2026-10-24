# Asseta user manual: Manager / Dispatcher

> Part of the [Asseta user manual](README.md). Read the README first for signing in and the glossary.

## Who this is for

This manual is for operations managers and dispatchers. You plan the work and keep the fleet moving:

- You set up customers, contracts and jobs.
- You approve jobs and decide expense approvals.
- You manage machines, trackers, staff and job sites.
- You watch alerts and investigations.

You work mainly in the **web console** at <https://asseta.co.tz>.

## What you can do

- **Customers and contracts**: create and edit customers, contracts and rental rate cards.
- **Jobs**: create jobs, submit them, approve them (including the hourly price), cancel them, and follow them through to completion.
- **Field work**: start and complete jobs, log work and record customer acknowledgements from **My jobs**. Meter readings are taken by supervisors.
- **Fleet**: register and edit machines, assign supervisors and operators to machines, register and assign GPS trackers, draw job sites and geofences.
- **Monitoring**: watch the fleet map and history, and acknowledge and resolve tracking alerts.
- **Approvals**: approve or reject expenses that are above the auto-approval limit.
- **Investigations**: assign, annotate, resolve and reopen investigation cases.
- **Insights**: review machine utilisation, fuel efficiency and model observations.
- **Read-only**: Policies and the Audit log.

What the Manager role does **not** include, by default:

- Meter exception reviews and meter reset decisions.
- Hire invoices, payments and cash.
- Users and roles, policies changes, and the company's Asseta subscription.

The **Tenant Owner** handles these. Your company may customise roles.

## Where you work

| Menu group | Menus |
|---|---|
| Overview | Dashboard, Fleet map |
| Field work | My jobs |
| Operations | Jobs, Customers, Staff |
| Fleet | Machines, Trackers, Sites & geofences, Alerts |
| Risk & review | Investigations, Insights |
| Finance | Approvals |
| Administration | Policies (read-only), Audit log, Notifications, My access |

The **Asseta Owner** phone app can also be used by managers whose company gives them access. It covers the fleet map, jobs, alerts and approvals on the go; see the [Tenant Owner manual](01-tenant-owner.md#the-asseta-owner-app). The buttons shown there depend on your role's permissions.

---

## Tasks

### 1. Add a customer, a contract and rate cards

**Customer**

1. Go to **Operations → Customers** and create a **New customer**.
2. Fill in **Code**, **Name**, **Tax ID**, **Payment terms (days)**, and the contact (**Contact name**, **Contact phone**, **Contact email**).
3. Click **Create customer**.

**Contract**

1. Open the customer. On the **Contracts** tab, start a **New contract**.
2. Fill in:
   - **Contract number**
   - **Customer reference**
   - **Default job site** (jobs under the contract default to it)
   - **Starts**
   - **Ends (optional)** (leave empty for an open-ended contract)
   - **Notes**
3. Click **Create contract**.

**Rate cards**

Rate cards hold your standard hourly price per machine category.

1. On the Customers page, open the rate-card section and create a **New rate-card version**.
2. Choose the **Machine category**, then enter the **Hourly rate**, **Minimum hours**, **Effective from (empty = now)** and a **Reason**.
3. Click **Create version**.

Rate cards cannot be backdated. Saving creates a new version, and jobs already created keep the price they were created with.

Without a rate card, every job needs a negotiated hourly rate.

**Closing things down:** a contract can be closed with **Close contract**. A customer can be deactivated. Both need open jobs completed or cancelled first. History, balances and statements are kept.

### 2. Create a job

1. Go to **Operations → Jobs** and open **New job**. The dialog has three steps: **Assignment**, **Schedule** and **Pricing**.
2. **Assignment**:
   - **Job number**
   - **Contract** (must be active)
   - **Machine** (must be active)
   - **Job site**
   - **Supervisor** (searches staff of kind Supervisor)
3. **Schedule**: **Planned start** and **Planned end (optional)**.
4. **Pricing**:
   1. Under **Hourly rate source**, choose **Use the rate card** or **Negotiated rate**. For a negotiated rate, enter the **Negotiated hourly rate**.
   2. Enter **Minimum hours**.
   3. Choose the **Standby treatment**:
      - **Excluded (standby not billed)**
      - **Included (billed at the hourly rate)**
      - **Separate standby rate**, with a **Standby rate (per hour)**
   4. Optionally enter **Mobilization fee**, **Discount (%)** and **Tax rate (%)**.
5. Review the summary and click **Create job**.

   *What you'll see:* "Job J-… created as draft."

You can **Edit** a job while it is Draft or Pending approval. Approved, running and finished jobs can no longer be edited.

### 3. Submit and approve a job

The hourly price is fixed when the job is approved. The supervisor can then take the opening reading.

1. Open the job (**View details**).
2. Click **Submit for approval**. This sends the job and its price for approval.
3. An approver then clicks **Approve**. This approves the job and its price snapshot.

   *What you'll see:* the status changes to **Approved**. The job appears under **Ready to start** on the supervisor's phone after their next sync, and owners and approvers receive a "Job awaiting approval" notification while it waits.

**One active job per machine:** a machine can have only one approved or running job at a time. Otherwise Asseta says: "This machine already has an approved or running job; complete or cancel that job first."

### 4. Cancel a job

1. Open the job and click **Cancel job**. This is possible while it is Draft, Pending approval or Approved.
2. Enter the **Reason** (required; it is kept in the audit trail) and confirm.

A job that has already started cannot be cancelled. It must be completed.

### 5. Follow a job and help in the field

**Operations → Jobs** lists all jobs with status, machine, planned start and hourly rate. Filter by **Status** or machine. Open a job to see:

- The summary: rate, minimum hours, standby terms, opening and closing readings, **Billing ready** or **Not billing ready**, and how many exceptions are open or blocking.
- The tabs **Readings & evidence**, **Work log**, **Acknowledgement** and **Meter resets**.

From **Field work → My jobs** you can do the supervisor's job steps from your laptop. Use the toggle **Assigned to me / All jobs**. On a job page you can:

- **Start job** (once the supervisor's opening reading is in)
- **Log work**
- **Record customer acknowledgement**
- **Complete job**

See the [Supervisor manual, Part B](03-supervisor.md#working-from-a-laptop-web-console). By default the Manager role cannot record meter readings or expenses.

### 6. Register and maintain machines

1. Go to **Fleet → Machines** and create a **New machine**. The dialog has three steps:
   - **Identity**: **Asset code**, **Name**, **Status**.
   - **Classification**: **Category**, **Operating area**, **Ownership**, **Manufacturer**, **Model**, **Serial number**, **Year of manufacture**.
   - **Metering & capacity**: **Hour-meter decimal places** (0, 1 or 2; this is the precision supervisors capture), **Capacity** and **Capacity unit**.
2. Click **Create machine**.

The **Categories** and **Operating areas** tabs on the Machines page hold the lookup lists.

Machine actions:

- **Take out of service**: for example, under repair. Use **Return to service** to bring it back.
- **Retire (dispose)**: for machines sold, scrapped or returned. History is kept, and **Reinstate** is available.
- **Enroll as billable asset**: adds the machine to your Asseta subscription. This is normally an owner action.

**Assign staff to a machine:**

1. Open the machine and go to the **Staff assignments** tab.
2. Click **Assign**. Choose the **Staff member**, the **Role** (**Supervisor** or **Operator**) and **Effective from**.
3. To finish an assignment, use **End assignment** with the **Ends at** time.

### 7. Manage staff

1. Go to **Operations → Staff** and create a **New staff member**.
2. Fill in **Full name**, **Employee code**, **Kind** (Supervisor or Operator) and **Phone**.
3. To link the person to their Asseta login, fill in **Login subject (optional)**. The **App login** column then shows **Linked**.

Linking matters. A supervisor's phone shows their jobs, and cash is credited to the right person, only when their staff record is linked to their login.

Before you deactivate someone, Asseta asks you to:

- Reassign or finish the jobs they supervise.
- End their machine assignments.
- Make sure they hold no cash (record a cash handover first).

### 8. Register and assign GPS trackers

1. Go to **Fleet → Trackers** and click **Register tracker**.
2. Fill in:
   - **Approved tracker model** (only models approved by Asseta are listed)
   - **Label**
   - **External device id** (for example the IMEI)
   - **SIM ICCID**, **SIM MSISDN**, **Carrier**
   - **Credentials reference** (a reference to where the secret is stored, never the secret itself)
3. Click **Register tracker**.
4. To fit it to a machine, use **Assign / swap**:
   1. Choose the **Machine**.
   2. Tick **Primary tracker for this machine**.
   3. Set **Effective from** and a **Reason**.
   4. When replacing a tracker, tick **Replace existing primary (swap)**.

The machine must be an **enrolled billable asset** before it can be tracked.

Other tracker actions:

- **Unassign**.
- **Suspend**: its data is quarantined while suspended. **Reactivate** brings it back.
- **Retire (decommission)**: permanent.

The **Ingestion events** view shows the messages received from trackers, and why any were quarantined.

### 9. Job sites and geofences

1. Go to **Fleet → Sites & geofences**.
2. **Job sites**: click **New job site** and enter **Code**, **Name** and **Address**. Click the map to set the site centre.
3. **Geofences**: click **New geofence**.
   1. Give it a **Name**.
   2. Choose its **Kind**:
      - **Allowed area**: alerts when a machine leaves.
      - **Restricted area**: alerts when a machine enters.
      - **Site boundary**: informational, for time-in-location.
   3. Choose the **Shape**: **Polygon** (click points and close the ring) or **Corridor (route + width)**, with **Corridor width (m)**.
   4. Optionally link a **Job site**.
   5. Under **Applies to**, choose **All machines** or **Selected machines**.

An inactive geofence raises no alerts, but its history is kept.

### 10. Watch the fleet and handle alerts

**Fleet map**

**Overview → Fleet map** shows live and last-known positions. Each machine has a connectivity state: **Live**, **Recent**, **Stale**, **Offline**, **Never reported** or **No tracker**. Select a machine to see:

- **Last message**, **Position age**, **Accuracy**, **Source**
- **Tracker state**, **Machine status**
- **Operator** and **Supervisor**
- **Open alerts**

**Machine history**

Open a machine and go to **History**. Choose a time range (up to 31 days) to replay the route with stops and geofence visits. Points marked **Late (buffered/replayed)** arrived after a delay. **Low quality** points are shown but excluded from decisions.

**Alerts**

**Fleet → Alerts** lists tracking alerts:

- Geofence exit
- Restricted area entry
- Unauthorized movement (outside approved hours)
- GPS anomaly
- Tracker stale or offline
- Low power
- Tamper

Filter by **Type**, **Severity**, **Status** or **Machine**. Open an alert and:

- **Acknowledge alert**: you are looking at it. A **Note (optional)** can be added.
- **Resolve**: requires a **Resolution note**, which is kept with the alert for audit.

### 11. Decide expense approvals

1. Go to **Finance → Approvals**. Expenses above the auto-approval limit wait here.
2. Each request shows **Subject**, **Amount**, **Requested by** and **Why approval is needed**.
3. Click **Approve / reject**. The **Decide expense approval** dialog shows the expense and its receipts.
4. Approve it, or reject it with a note. The supervisor sees your note.

You cannot decide your own request. The button shows **Approve / reject (not allowed: your own request)**.

### 12. Investigations

**Risk & review → Investigations** has two tabs:

- **Signals**: findings from automatic checks, for example engine running without a job, duplicate receipts, fuel above allowance, cash not handed over, or work without authorisation.
- **Cases**: signals grouped for human review.

Open a case to:

- **Assign** it to a reviewer.
- **Add note**.
- **Resolve** it with an outcome and an **Explanation**. The outcomes are **Issue confirmed**, **Unconfirmed** and **Legitimate explanation**.
- **Reopen** it with a reason.

People whose own records are part of a case cannot review it. A colleague must do it.

### 13. Insights

**Risk & review → Insights** compares each machine with its own history: weekly hours, hours per available day, and litres per meter hour. Each value is marked **Within usual range**, **Outside usual range** or **Not enough history**.

The page also shows:

- **Manual overrides**: readings typed in although the camera read a value.
- The status of the automatic model (for example **Learning (shadow)**).
- Any **Model observations** for review.

A value outside the usual range is a prompt to look, not a conclusion about anyone.

---

## Statuses and what they mean

| Item | Statuses |
|---|---|
| Job | Draft → Pending approval → Approved → In progress → Completed; or Cancelled (from Draft, Pending approval or Approved) |
| Alert | Open → Acknowledged → Resolved; Superseded (replaced when late data changed the evidence) |
| Alert severity | Info, Warning, Critical |
| Machine connectivity | Live, Recent, Stale, Offline, Never reported, No tracker |
| Approval | Pending, Approved, Rejected |
| Investigation case | Open → In review → Resolved (can be reopened) |
| Signal | Open, Linked (on a case), Dismissed |

## Good practice

- **Approve jobs only with the right price.** The approved price is what the customer is billed.
- **Keep one active job per machine** and complete jobs promptly so the next one can start.
- **Link every supervisor's staff record to their login** before their first job.
- **Write useful notes** when resolving alerts and cases. They form the audit trail.
- **Check Alerts and Approvals daily.** Reminders are sent when approvals wait too long.

## Troubleshooting and FAQ

**"There is no rate card for this machine category…"**
Enter a negotiated hourly rate on the job, or add a rate card for the category.

**"Approved, running and finished jobs can no longer be edited."**
Cancel the job (if not started) and create a new one.

**The supervisor can't see the job.**
Check that the job is **Approved**, the **Supervisor** field is correct, and the supervisor's staff record is **Linked** to their login. Then ask them to sync their phone.

**"Complete or cancel the open job on this machine first."**
A machine with an open job cannot be retired or taken out of service.

**"The machine must be an enrolled billable asset before it can be tracked."**
Ask the owner to **Enroll as billable asset** on the machine.

**I can't review exceptions or decide meter resets.**
These belong to the owner by default. Ask the owner, or ask them to adjust your role.
