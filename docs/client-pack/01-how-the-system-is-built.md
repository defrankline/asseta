# How the system is built

## The short version

Asseta has **one central system** and **three ways of reaching it**. Phones can work without internet and catch up later. The central system makes every final decision about money, hours and permissions. A phone can only submit a record; it can never approve one.

```
   Field sites (often no internet)             Office / anywhere (internet needed)

   +--------------------------+               +-----------------+  +-----------------+
   | Asseta Supervisor app    |               |   Web console   |  | Asseta Owner app|
   | Android and iPhone       |               | laptop / desktop|  | Android, iPhone |
   | Works offline            |               | The full system |  | Approvals, view |
   +------------+-------------+               +--------+--------+  +--------+--------+
                | sends when connected                 |                    |
                v                                      v                    v
   +--------------------------------------------------------------------------------+
   |                              CENTRAL SYSTEM                                    |
   |  Checks who you are and what you may do. Applies every rule again.             |
   |  Keeps the ledgers, the evidence files and the audit history.                  |
   +--------------------------------------------------------------------------------+
                ^
                | machine positions and engine data
   +------------+-------------+
   | GPS trackers on machines |
   | (where fitted)           |
   +--------------------------+
```

## The parts

| Part | Who uses it | What it does |
|---|---|---|
| **Web console** | Everyone with a login | The full system on a laptop or desktop. Needs internet. Supervisors can also do their field work here, under **Field work**, but only while connected. |
| **Asseta Supervisor app** | Field supervisors, and anyone else given field permissions | Records jobs, meter readings with photos, cash, hours sales, fuel and expenses. Works offline and saves everything encrypted on the phone until it can sync. |
| **Asseta Owner app** | Owner and managers | Dashboard, fleet map, approvals and confirmations from anywhere. Decisions need a live connection. With no connection you can only look at saved screens, and those are marked as old. |
| **GPS trackers** | Fitted to machines, where the company chooses | Report location and, depending on the tracker model, engine on/off and engine hours. |
| **Central system** | Runs on servers operated by the Platform Owner | Holds the ledgers, applies the rules and keeps the audit history. |
| **Evidence store** | Part of the central system | Holds meter photos, receipts, deposit slips and signatures in private storage. A stored file can never be overwritten. |
| **Sign-in service** | Everyone | Handles logins and passwords, and locks accounts under repeated failed attempts. |
| **Background workers** | Nobody directly | Do the routine work: raising alerts, sending notifications, checking for overdue items and building data exports. |
| **Backups** | Platform Owner | Copies of the central system, taken on a schedule. See [Your data](06-your-data.md). |

## The rules that shape the design

1. **Ledgers, not balances.** Every balance is worked out from a list of entries that are only ever added to. See [The six ledgers](02-ledgers.md).
2. **Claimed is not confirmed.** Anything a field person says happened starts as a claim. Only a different, authorized person can confirm it.
3. **Nobody decides their own request.** The person who proposed or recorded something cannot approve it. This is checked by the central system, and refused attempts are recorded.
4. **Offline never skips a control.** When a phone syncs, its records go through the same checks as a record typed in the office. A phone can never activate hours, confirm money or approve anything.
5. **Rules are your company's settings.** Prices, limits, cut-off times, who approves what, and which controls are on are all company settings in **Administration → Policies**. Each change creates a new version with a date and a reason, and old records keep the version that applied at the time.

## Who can do what

Access is by **permission**, and permissions are grouped into roles. The system ships with these roles as starting points:

| Role | Main purpose |
|---|---|
| **Tenant Owner** | Everything. The only role that can give someone a role that approves things |
| **Administrator** | System configuration and user access. No business approvals |
| **Manager / Dispatcher** | Runs operations, records field cash for staff without logins, approves operational exceptions |
| **Supervisor** | Records field work. Approves nothing |
| **Accountant / Finance** | Independently confirms money and does the reconciliation |
| **Operator** | Reads notifications. An operator can also be allowed to submit their own meter readings (a separate add-on role) |

Staff who hold cash do not need a login. A supervisor or manager records the cash on their behalf.

## Keeping companies apart

Each company's records are separated from every other company's at three levels: the login, the permission check on every action, and the database itself, which filters every record by company. Testing on 22 October 2026 tried to reach one company's records from another across all the system's functions, and every attempt was refused.

The Platform Owner cannot see a company's business data through the system unless the company has granted a written mandate. See [Your data](06-your-data.md) and limit 18 in [What the technology cannot fully enforce](04-what-the-technology-cannot-fully-enforce.md).

## What happens when a reading is taken at a site with no signal

1. The supervisor photographs the hour meter in the app. The app has no way to pick an existing picture from the phone; the camera must be used.
2. The phone reads the digits by itself (if the company uses automatic reading) and records the GPS position and the time.
3. The record and the photo are saved encrypted on the phone. The app shows **Waiting to sync**.
4. When a connection returns, the photo is uploaded first and its contents are checked. Then the reading is sent.
5. The central system applies the checks: is the reading lower than the last one, is the jump impossible for the time elapsed, is the photo one already used, is the phone clock wrong, does the position match the site and the tracker.
6. The reading becomes **Accepted**, or **Provisional** with a note for review, or **Rejected** and kept as evidence. The phone shows **Synced** only after the central system has confirmed that it has the record.

## For your IT adviser

| Topic | What is used |
|---|---|
| Central application | A modular application with separate background workers |
| Database | PostgreSQL with PostGIS, with row-level security enforced by the database |
| Sign-in | Keycloak (authentication and role groups) |
| Evidence files | S3-compatible private object storage; files are stored under their own checksum and cannot be overwritten |
| Internal messaging | Kafka, written from a transactional outbox so a messaging outage never blocks a business transaction |
| GPS gateway | Traccar |
| Phones | Native Android and iOS apps; local data encrypted (SQLCipher) with keys held in the phone's secure key store; no cloud backup of app data |
| Connection | HTTPS through a reverse proxy; login and request-rate limits |
| Security testing | Automated penetration test suite run on 22 October 2026 across 301 routes. No critical, high or medium findings remain open |
