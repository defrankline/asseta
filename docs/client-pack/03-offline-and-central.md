# Offline work and central confirmation

Machines work where there is no internet. This document says exactly what can be done without a connection and what must wait for the central system or a second person.

**The principle: a phone records. The central system decides.** Whatever is entered offline arrives as a claim and goes through the same checks as if it had been typed in the office.

Only the **Asseta Supervisor app** works offline. The **web console** always needs a connection. The **Asseta Owner app** can show saved screens offline, for up to 7 days and marked as old, but every decision needs a live connection.

An activity appears on a phone only if the person's role allows it and the company has that control switched on. The phone must also have connected at least once to load the customers, machines and company rules.

## Field activities (Asseta Supervisor app)

| Activity (as shown in the app) | Can be done offline? | What needs central confirmation or approval |
|---|---|---|
| **Jobs** | | |
| Request a job | Yes | The job must be approved and priced by an authorized person, online, before work starts |
| Capture opening or closing reading (photo, automatic reading, GPS) | Yes | Checked centrally on arrival. Unusual readings wait for office review |
| Start job, Complete job | Yes | Only on a job already approved and already on the phone. Checked again centrally on arrival. A prepaid job's remaining hours are checked centrally |
| Work log (work, standby, downtime, mobilization, note) | Yes | None. Explaining non-revenue time needs a connection |
| Customer acknowledgement (signature or name) | Yes | None |
| Record changeover (machine moves to next customer during a job) | Yes | Checked centrally. If billing is split, the next job must be approved online |
| **Meter** | | |
| Record daily reading | Yes | Checked centrally. Unusual readings wait for review |
| Daily report for this machine | Yes | Reviewed by someone other than the sender, online |
| Propose meter baseline | Yes | Counts only after someone else approves it, online |
| Propose a correction | Yes, once the central system already has the reading | Replaces the old reading only after someone else approves it, online |
| Request meter reset | Yes | Approved or rejected by someone else, online |
| **Cash** | | |
| Record cash collection | Yes | Stays claimed until someone else verifies it, online. It is added to the custodian's balance when the record arrives |
| Transfer cash to a colleague | Yes | The cash moves only after the receiver acknowledges it (a company setting, on by default) |
| Acknowledge or dispute a transfer or float | Yes, if it has already reached the phone | Sent at next sync. A different amount opens a difference for review |
| Hand over cash (remittance) | Yes | Reduces the balance only when someone else confirms the amount received, online |
| Ask to keep cash | Yes | Approved or rejected by someone else, online |
| **Customer hours** | | |
| Sell customer hours (registered or walk-in) | Yes | Price, purchase number and walk-in code are set centrally on arrival. **Hours stay inactive** until payment is confirmed by someone else, or credit is approved, online |
| Request hours transfer | Yes | Someone else approves it, online, before the hours move (a company setting, on by default) |
| **Other** | | |
| Record fuel event | Yes | None. It is a log |
| Record expense | Yes | Within the company's auto-approval limit: approved once it arrives. Above it: someone else approves it, online |
| Site check-in (if switched on) | Yes | None |

## Activities that need a connection

These are done in the web console or, where shown, the Owner app. Nothing in this table can be done offline.

| Activity | Web console | Owner app |
|---|---|---|
| Approve, price or decline a job | Yes | Yes |
| Create a job | Yes | Yes |
| Confirm a remittance (amount actually received) | Yes | Yes |
| Confirm or reject a customer payment | Yes | Yes |
| Record a customer payment received at the office or bank | Yes | No |
| Activate hours on credit | Yes | No |
| Issue a cash float | Yes | Yes |
| Decide discounts, credit, hours transfers, cancellations | Yes | Yes |
| Decide baselines, reading corrections, explanations of engine hours, meter resets | Yes | Yes |
| Review daily reports; decide work allocation corrections | Yes | Yes |
| Review meter exceptions | Yes | Yes |
| Decide retentions, custody adjustments, write-offs, variance closures | Yes | Yes |
| Decide corrections, refunds and reversals | Yes | Yes |
| Propose corrections, refunds and reversals | Yes | No |
| Issue and void invoices | Yes | No |
| Explain non-revenue time | Yes | No (it can decide them). The Supervisor app can explain them while connected |
| Resolve sync conflicts | Yes | No |
| Change rate cards, policies, reason lists and deposit accounts | Yes | No |
| Manage users and roles | Yes | No |
| Data export, balance verification | Yes | No |
| Revoke a lost phone | Yes | No |
| Find a reference | Yes | Yes |

## How long a phone can work offline

Your company sets two limits under **Administration → Policies → Device sync**:

| Setting | Standard value | Highest allowed |
|---|---|---|
| **Offline grant**: how long a phone may go without contacting the central system | 72 hours | 14 days |
| **Policy snapshot validity**: how long the phone's copy of the capture rules stays valid | **24 hours** | 14 days |

When either runs out, the phone **pauses new meter readings and expenses**, with a message such as "Connect to refresh rules." A brief connection and a sync opens them again. Other records (cash, hours sales, transfers) can still be entered.

**Set both limits to match your longest real time without a signal before go-live.** At the standard value, a phone with no connection for more than 24 hours stops taking readings.

Nothing already saved is lost when a limit runs out.

## Created time and synced time

The system keeps both times for offline records, so you can see the gap.

| Record | Time on the phone or entered by the person | Time the central system received it | Where you see them |
|---|---|---|---|
| Meter reading | **Device time** | **Server receive time**, and the **Clock difference** | The reading card on the job page |
| Site check-in | Time of check-in | **Received by the server** | **Operations → Site check-ins** |
| Daily report | **Created on device** | The report's sent time | The report's page |
| Hours purchase | **Recorded on the phone at** | Stored as the record's creation time | The purchase page |
| Request to keep cash | **Recorded on the phone at** | Stored as the record's creation time | The retention's page |
| Cash collection | **Received** (the time the person entered) | Stored as the record's creation time | The collection's page |
| Remittance | **Handed over** (the time the person entered) | Stored as the record's creation time | The remittance's page |
| Records held for review | **Recorded on device** | **Received** | **Risk & review → Sync conflicts** |

Every operation sent by a phone also has its device time and arrival time in the central sync log, which is included in the [data export](06-your-data.md).

Times typed by a person, or taken from a phone clock, are what that person or phone said. See limit 3 in [What the technology cannot fully enforce](04-what-the-technology-cannot-fully-enforce.md).

## How the phone syncs

- The phone tries when the app is opened and a connection returns, when someone pulls down on a list, and when someone taps **Sync now**.
- Android phones also try in the background about every 15 minutes when a network is available. **On iPhone, background sync is not guaranteed. Open the app.**
- Photos, receipts and signatures upload first, and can resume after a break. A record that needs a photo waits for it.

## Duplicates

Each offline record gets a unique identifier on the phone. If a connection drops and the phone sends again, the central system recognizes the identifier and does nothing the second time. **A record is marked Synced only after the central system confirms it has the record.**

## What happens when records conflict

The system never silently overwrites anything. Each record that arrives has one of these outcomes:

| Outcome | Meaning | What happens to the record |
|---|---|---|
| **Synced** | Accepted | Applied |
| **Waiting** | It depends on an earlier record or on a photo still uploading | Sent again automatically |
| **Conflict** | The record is real, but something changed on the central system while the phone was offline | **Kept and held for review. Not applied** |
| **Rejected** | The record could not have been valid (for example the person lacks the permission) | Kept and listed for review. Not applied |
| **Held: subscription read-only** | The company's subscription is restricted | Kept, and applied automatically after reactivation |

**Examples of conflicts held for review:**

- The job was cancelled, reassigned or changed while the phone was offline.
- Two supervisors used the same remaining customer hours, or the hours ran out.
- The machine already has a running job, or another job has the same meter hours.
- The baseline or correction was already pending, or the required baseline had not been approved.
- A cash transfer or float was already answered.
- The bank or mobile-money reference was already used on another payment.
- The company changed a rule after the phone queued the record (for example it now requires a deposit slip photo, or switched a control off).
- **Money records:** for cash collections, remittances and hours sales, a refusal caused by anything that changed since they were entered (a person left, a customer or machine was deactivated, a deposit account was closed) is held for review. Money already changed hands, so the record must not be lost.

**Where they appear.**

- On the phone: **Sync status → Needs attention: conflicts** or **Needs attention: rejected**. The original evidence stays on the phone.
- In the office: **Risk & review → Sync conflicts**. Open a row to see **Why not applied**, **Submitted by**, the **Device**, what the device sent, and the state of the central system at the time.

**How they are resolved.** Someone with the permission, and who did not submit the record, clicks **Resolve** and chooses **Dismiss** or **Re-captured** (recorded again correctly), with a reason. The conflict screen does not apply the record itself: if the record is good, a person enters it again, and it is then checked in the normal way. Every outcome is recorded.

**Two people using the same hours.** The central system applies jobs one after the other as they arrive. The second job gets what is left, and the rest is flagged as hours beyond what the customer has active. Nothing is double-counted.
