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
- **Jobs**: create jobs, submit them, approve them (including the hourly price), approve or decline jobs supervisors request from the field, cancel them, and follow them through to completion.
- **Field work**: start and complete jobs, log work and record customer acknowledgements from **My jobs**. Meter readings are taken by supervisors.
- **Fleet**: register and edit machines, assign supervisors and operators to machines, register and assign GPS trackers, draw job sites and geofences.
- **Monitoring**: watch the fleet map and history, and acknowledge and resolve tracking alerts.
- **Approvals**: approve or reject expenses that are above the auto-approval limit.
- **Investigations**: assign, annotate, resolve and reopen investigation cases.
- **Insights**: review machine utilisation, fuel efficiency and model observations.
- **Customer hours** (if your company uses prepaid hours): record walk-in customers and hours purchases, link payments, propose and decide customer discounts, credit arrangements, hours transfers and cancellations (never your own), and keep the reason lists.
- **Cash on behalf of staff**: record cash collections, transfers and remittances for custodians who have no login, such as operators (if your company allows it).
- **Oversight**: the **Accountability** dashboard, **Security events** (refused attempts) and **Sync conflicts** (field records the server could not apply).
- **Read-only**: Policies and the Audit log.

What the Manager role does **not** include, by default:

- Meter exception reviews and meter reset decisions (if your company adds them to your role, you also get **Risk & review → Meter resets**).
- Hire invoices, payments and cash.
- Users and roles, policies changes, and the company's Asseta subscription.

The **Tenant Owner** handles these. Your company may customise roles.

## Where you work

| Menu group | Menus |
|---|---|
| Overview | Dashboard, Fleet map, Accountability |
| Field work | My jobs, Cash, Customer hours |
| Operations | Jobs, Customers, Staff |
| Fleet | Machines, Trackers, Sites & geofences, Alerts |
| Customer hours | Hours purchases, Balances, Hours ledger, Work allocations, Transfers, Cancellations, Customer discounts, Credit arrangements, Walk-in customers, Reason lists |
| Risk & review | Investigations, Insights, Security events, Sync conflicts |
| Finance | Approvals |
| Administration | Policies (read-only), Audit log, Notifications, My access |

The **Customer hours** menus appear only when your company has switched customer hours on in its policies. The decisions you see depend on the permissions your role holds; the role setup above is an example your company can change.

The **Asseta Owner** phone app can also be used by managers whose company gives them access. It covers the fleet map, jobs (including **New job** and approving or declining jobs), alerts and approvals on the go; see the [Tenant Owner manual](01-tenant-owner.md#the-asseta-owner-app). The buttons shown there depend on your role's permissions.

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

A job starts in one of two ways:

- **The office creates it and assigns a supervisor**, as described below (or with **New job** in the Owner app).
- **A supervisor requests it from the field** when a customer on site asks for work. It arrives as **Pending approval** for you to price and approve (see [Task 3](#3-submit-and-approve-a-job)).

To create one:

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
   5. If your company uses customer hours, choose the **Billing**: **Invoice after the work**, or **Prepaid customer hours** ("Prepaid jobs draw on the customer's activated hours for this machine."). The first option, **Company default (…)**, follows your company policy. See [Task 18](#18-prepaid-jobs-and-work-allocations).
5. Review the summary and click **Create job**.

   *What you'll see:* "Job J-… created as draft."

You can **Edit** a job while it is Draft or Pending approval. Approved, running and finished jobs can no longer be edited.

### 3. Submit and approve a job

The hourly price is fixed when the job is approved. The supervisor can then take the opening reading.

1. Open the job (**View details**).
2. Click **Submit for approval**. This sends the job and its price for approval.
3. An approver then clicks **Approve**. This approves the job and its price snapshot.

   *What you'll see:* the status changes to **Approved**. The job appears under **Ready to start** on the supervisor's phone after their next sync, and owners and approvers receive a "Job awaiting approval" notification while it waits.

**Jobs requested from the field.** In **Operations → Jobs** these carry a **Field request** chip. They are already in **Pending approval**, with the requesting supervisor as the job's supervisor.

1. Open the job. The approval dialog shows "Requested from the field by <supervisor>" and what the customer asked for.
2. Check the price. If no rate card applies, the job shows "No price yet (set on approval)" and the **Hourly rate** is required: "No rate card applies; the job is approved at this price." Otherwise you may change the rate to approve at a different price.
3. Click **Approve**. The supervisor is notified ("Job J-… approved") and the job moves to their **Ready to start**.
4. To refuse it, click **Decline request** and enter the **Reason**. The supervisor is told your reason, and the job stays on record as cancelled.

When an office-created job is approved, its supervisor is notified "New job J-… assigned to you".

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

Assign each supervisor to the machines they look after. A supervisor can request jobs from the field only on machines assigned to them or already on their jobs.

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

### 14. Customer hours: how it works

Some customers buy machine hours **in advance** and use them over several days. Asseta keeps a chain of accountability for every such hour. This applies only if your company has switched **Customer hours** on (owner: [Set company policies](01-tenant-owner.md#3-set-company-policies)). If it is off, the **Customer hours** menus are hidden and jobs are invoiced as usual.

The rules Asseta applies:

- **One purchase, one machine.** Every purchase gets a unique number (HP-…) and names the customer, the hours and the specific machine.
- **The price is never typed.** It comes from the rate card, less any **approved** customer discount in effect.
- **The purchase and its payment are separate records.** A receipt photo or mobile-money screenshot is kept as evidence only. The payment stays **Claimed (unverified)** until someone else verifies it.
- **Hours activate only from verified money or approved credit.** Nobody can activate hours any other way.
- **Hours are used through work allocations.** A completed prepaid job draws on the customer's activated hours for that machine. Hours beyond what is available are never used silently: they are flagged for review.
- **Every change is a ledger entry.** Balances are always worked out from the [Hours ledger](#19-balances-and-the-hours-ledger), never typed in.
- **Decisions go to whoever holds the permission**, and the person who proposed or requested something can never decide it ("Someone else must decide your own request").

### 15. Walk-in customers

**Customer hours → Walk-in customers** ("Customers recorded with just a name and phone; register them when they become regulars") lists customers served without full registration. This needs **Walk-in customers allowed** in your company policy.

1. Click **New walk-in**. Enter the **Name** and **Phone (optional)**, then click **Create walk-in**.

   *What you'll see:* "Walk-in customer created." Asseta gives them a WALK-… **Code**.
2. When a walk-in becomes a regular, open the row menu and choose **Register as customer**. Fill in **Customer code**, **Name**, **Contact name**, **Contact email**, **Tax ID** and **Payment terms (days)**, then click **Register customer**.

   *What you'll see:* "<name> is now a registered customer (<code>)." Their history stays with them.

You can also create a walk-in while recording a purchase (next task).

### 16. Record an hours purchase and link its payment

1. Go to **Customer hours → Hours purchases** ("Prepaid hours bought per customer and machine; they activate from verified money or approved credit") and click **New purchase**. The **New hours purchase** dialog has three steps.
2. **Customer**: choose **Existing customer** and pick the **Customer**, or **New walk-in customer** and enter the **Walk-in customer name** and **Phone (optional)**.
3. **Hours**: choose the **Machine**, enter the **Hours bought**, and optionally the **Job site (optional)** and **Note (optional)**. "The price comes from your rate card and any approved discount for this customer."
4. **Payment**: choose **No payment now**, **Cash**, **Bank transfer** or **Mobile money**. For a payment, fill in:
   - **Amount received** (leave empty when the full purchase amount was paid)
   - **Reference (receipt or transaction no.)**
   - **Received at**
   - **Cash held by (empty = me)**: the staff member who holds the cash until it is handed over
   - **Evidence photo (receipt or mobile-money screenshot)**: "Kept as evidence only; the payment stays claimed until someone else verifies it."
5. Check the review and click **Record purchase**.

   *What you'll see:* "Hours purchase HP-… recorded." The purchase opens with status **Awaiting payment**.

**Link a payment later.** On the purchase page, click **Allocate payment**, choose the **Customer payment** and the **Amount to allocate**, and click **Allocate payment**. *What you'll see:* "Payment allocated; hours activate when it is verified." A payment can never be allocated twice beyond its amount. Use **Evidence** on a payment row to view or add a receipt photo (**Add evidence photo**, **Attach to payment**).

**The purchase page** shows the **Purchase** (rate card rate, approved discount, effective rate, amount, who recorded it), the **Hours** (purchased, activated, from verified payments, on credit, awaiting activation, used on jobs, transferred, expired, reversed, remaining, also per machine), the **Payments**, **Transfers between machines** and **Cancellation requests**. **Open the hours ledger** shows every movement.

### 17. Activate hours on credit, transfer them, or cancel a purchase

All three start on the purchase page. The buttons appear only when the action is possible.

**Activate on credit** (needs an approved credit arrangement and the credit-activation permission, usually the accountant):

1. Click **Activate on credit**. Enter the **Hours to activate** and a **Reason**.
2. Click **Activate on credit**. "Allowed only within the customer's approved, available credit. Who and why are recorded."

   *What you'll see:* "Hours activated on credit."

**Request a transfer** when the original machine cannot do the work:

1. Click **Request transfer** (or **Customer hours → Transfers → Request transfer**).
2. Check **From machine** (empty = the purchase's machine), choose the **To machine**, enter the **Hours**, pick a **Reason from your list** if your company requires one, and write the **Reason**.
3. Click **Request transfer**. *What you'll see:* "Transfer requested; someone else decides it."

Only hours not yet used can move. The purchase always keeps its original machine and shows the full transfer history.

**Request a cancellation**: click **Request cancellation**, give the **Reason** and confirm. "Only hours not yet used can be cancelled; someone else decides the request."

Depending on your company policy, transfers and cancellations either wait for a second person (**Transfers between machines need a second person**, **Cancellations need a second person**) or take effect at once.

### 18. Prepaid jobs and work allocations

A job with **Billing** set to **Prepaid customer hours** draws on the customer's activated hours **for that machine**.

- Depending on your policy (**When a prepaid job has no hours left**), a prepaid job without remaining activated hours either **cannot start**, or starts and the excess is flagged.
- When the job is completed, its billable hours are taken from the customer's oldest active purchases first. The job page shows **Customer hours used by this job**.
- **Customer hours → Work allocations** ("Hours each completed prepaid job used, drawn from the customer's oldest active purchases") lists each job's **Billable**, **Covered** and **Not covered** hours. Use **Show purchases used** to see which purchases were drawn on.
- Hours **not covered** appear as the exception **Hours beyond what the customer has active** (the apps say **Hours beyond purchase**), with **Requires review**. "Hours beyond what the customer had active are never used silently: they are flagged for review until new hours cover them." Depending on your policy it may block invoicing until reviewed. The office reviews it in **Risk & review → Exceptions**.

If two supervisors offline use the same remaining hours, Asseta applies them one after the other when they sync. The second job gets what is left, and the rest is flagged as hours beyond purchase. Nothing is lost or double-counted.

### 19. Balances and the hours ledger

- **Customer hours → Balances** ("Activated, used and remaining prepaid hours, derived from the hours ledger"): choose **By customer** or **By machine**. Columns show **Purchases**, **Awaiting activation**, **Activated**, **Transferred in**, **Transferred out**, **Used**, **Expired**, **Reversed** and **Remaining**. By customer, the **Credit** panel shows the **Approved limit**, **Used on credit, not yet paid** and **Available**.
- **Customer hours → Hours ledger** ("Every change to customer hours, in order; balances are always derived from it"): filter by **Customer**, **Machine** or **Entry**. Each row shows **When**, **Entry**, **Hours**, **Customer**, **Machine**, **Purchase**, **Job**, **Source** (Credit or Verified payment), **Reason** and **By**.

**Expiry.** If your company sets **Unused hours expire after**, activated hours not used within that many days (counted from activation) expire. A warning is sent beforehand (**Warn before expiry**). Expired hours appear as **Expired** in the ledger and balances. If the setting is empty, hours never expire.

### 20. Customer discounts and credit arrangements

Discounts and credit are **proposed** by one person and **approved** by another holding the approval permission. Only approved records in effect apply. Nobody types a discount on a sale.

**Propose a discount:**

1. Go to **Customer hours → Customer discounts** ("Approved discounts apply automatically to new hours purchases; nobody types a price") and click **Propose discount**.
2. Fill in **Customer**, **Discount (%)** (at most your company's **Highest discount**), **Effective from**, **Effective to (optional)**, **Reason from your list** and **Reason**.
3. Click **Propose discount**. *What you'll see:* "discount proposed." It shows **Awaiting decision**.

**Propose credit:** in **Customer hours → Credit arrangements** ("How much prepaid hours a customer may use before paying, within approved limits"), click **Propose credit** and fill in **Customer**, **Credit limit**, **Currency**, **Effective from**, **Effective to (optional)**, **Terms (optional)** and the reason. Credit appears only when your policy has **Credit arrangements allowed** on.

While a proposal awaits a decision, the proposer can **Edit** or **Withdraw** it. An approved one can later be **Revoke**d with a reason.

### 21. Decide hours requests

Discounts, credit arrangements, transfers and cancellations wait for a decision on their own pages (**Customer hours → Customer discounts**, **Credit arrangements**, **Transfers**, **Cancellations**), filtered to **Awaiting decision**. They can also be decided in the Owner app (**More → Approvals**).

1. Click **Decide** on the row.
2. Read the summary (for a transfer: "Approving moves these remaining hours to the other machine; the purchase keeps its history.").
3. Choose the **Decision**: **Approve** or **Reject**. Write a **Note / reason** ("Required when rejecting; kept on the record for audit.").
4. Click **Record decision**.

*What you'll see:* for example "Transfer of 5 h approved." or "Cancellation request approved." Each record keeps its own page with **Requested by**, **Decided by**, **Decision note** and history. Notifications about a request open that exact record.

On your own request the **Decide** button is disabled: "Someone else must decide your own request".

### 22. Hours reason lists

**Customer hours → Reason lists** ("Your company's reasons for discounts, credit, transfers and cancellations") holds your own reasons. Click **New reason**, choose what it is **Used for** (**Discount**, **Credit**, **Transfer** or **Cancellation**), enter a **Code** and **Label**, and click **Create reason**. A deactivated reason "can no longer be chosen; records that cite it keep it." If your policy has **A reason from the tenant list is required** on, requests must pick one.

### 23. Record cash for staff without a login

Operators and other staff may hold company cash without having an Asseta login. If your company's policy allows **Recorders record for any custodian**, you can record their cash in **Field work → Cash**:

- **Record cash collection**: choose who it was **Collected by (custodian)**.
- **Remit cash**: choose who it was **Handed over by (custodian)**.
- **Transfers** tab → record a transfer between two custodians (**Handed over by (sender)**, **Received by (receiver)**).

The steps are the same as for a supervisor (see [Supervisor manual, B3](03-supervisor.md#b3-readings-fuel-expenses-cash-pages)). Leave the custodian empty for your own cash. When you are the receiver, recording a transfer counts as your acknowledgement (if your company allows it), with the **Amount actually received**.

### 24. Oversight: accountability dashboard, security events and sync conflicts

These are described in the [Tenant Owner manual](01-tenant-owner.md#14-accountability-dashboard). Your role can see them by default:

- **Overview → Accountability**: the accountability dashboard.
- **Risk & review → Security events**: refused attempts.
- **Risk & review → Sync conflicts**: field records the server could not apply, which you can resolve.

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
| Hours purchase | Awaiting payment → Partly active → Active → Used up; Expired; Cancelled |
| Hours ledger entry | Activated, Used on a job, Transferred out, Transferred in, Expired, Reversed |
| Hours transfer, cancellation | Awaiting decision → Approved / Rejected; Withdrawn |
| Customer discount, credit arrangement | Awaiting decision → Approved / Rejected; Withdrawn; Revoked |

## Good practice

- **Approve jobs only with the right price.** The approved price is what the customer is billed.
- **Decide field job requests quickly.** The supervisor and the customer are waiting on site.
- **Keep one active job per machine** and complete jobs promptly so the next one can start.
- **Link every supervisor's staff record to their login** before their first job.
- **Write useful notes** when resolving alerts and cases. They form the audit trail.
- **Check Alerts and Approvals daily.** Reminders are sent when approvals wait too long.
- **Decide hours requests promptly**, but never your own. Keep at least two people with each approval permission.
- **Record sales for the right machine.** Hours belong to the machine named on the purchase; moving them needs a transfer.

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

**A supervisor can't find a machine when requesting a job.**
Assign the supervisor to the machine on its **Staff assignments** tab ([Task 6](#6-register-and-maintain-machines)), then ask them to sync.

**"No rate card applies to this job; enter the hourly rate to approve it at that price."**
The job was requested from the field and has no rate card. Enter the agreed hourly rate in the approval dialog.

**"Someone else must decide your own request."**
You proposed or requested this. Another person with the approval permission must decide it.

**"No rate card covers this machine; add a rate card first."**
An hours purchase needs a rate card for the machine's category. Add one in **Operations → Customers**.

**"Customer hours are switched off in your company policy."**
Your company has not switched customer hours on. Existing records stay readable. Ask the owner.

**"Hours were already used from this purchase, so it cannot be cancelled."**
Your policy does not allow cancelling the rest of a partly used purchase. Ask the owner whether it should.

**I can't review exceptions or decide meter resets.**
These belong to the owner by default. Ask the owner, or ask them to adjust your role.
