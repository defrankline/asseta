# Your data

> **DRAFT for the Platform Owner to review. Not yet approved. Do not give this to the company until it has been reviewed.**
>
> This draft describes what the system does today. It makes no legal promise. The proposed statements below are suggestions for the Platform Owner to accept, change or remove, and should be reviewed by a lawyer before they are given to the company. Anything still to be filled in is shown in **[bold brackets]**.

## What data the company has in Asseta

| Kind | Examples |
|---|---|
| **Business records and ledgers** | Customers, contracts, rate cards, jobs, readings, work allocations, customer hours, cash, remittances, invoices, payments, expenses, fuel, adjustments |
| **Evidence files** | Meter photos, receipts, deposit slips, machines' photos, customer signatures |
| **Tracking data** | Machine positions and engine data reported by trackers |
| **Configuration** | Company policies and their versions, reason lists, deposit accounts, notification settings |
| **History** | The audit log, security events, investigations and sync records |
| **People** | Staff records and the roles they hold |

**Proposed statement on ownership** *(draft wording, Platform Owner to confirm; have a lawyer review it before signing)*:

> The company owns all data it records in Asseta, including its business records, ledgers, evidence files, tracking data, configuration and history. The Platform Owner holds and processes this data only to provide the service. The Platform Owner does not sell it, and does not use it for any other company. The Asseta software itself remains the property of the Platform Owner. The company can export its data at any time during the agreement using **Administration → Data export**.

## How to export it

Someone with the data export permission does this. By default only the **Tenant Owner** has it.

1. Open **Administration → Data export**.
2. Choose the **Format**: CSV or JSON.
3. Click **Request export**. The file is prepared in the background. Only one export can be in preparation at a time.
4. When it is complete, download it before the time shown under **Available until**. The download link itself lasts only a few minutes; request another if it runs out.

**What is in the file.** One ZIP, built from a single consistent moment in time, with:

- A file for each kind of record, covering every ledger and business record belonging to the company.
- A list of contents, with the number of rows and a checksum for each file.
- A list of every evidence file with its checksum.

**What is not in the file.**

- **The evidence files themselves.** The list says how to fetch each one, and each is fetched individually with a short-lived link. There is no single button today that downloads every photo. Ask the Platform Owner for help with a full evidence copy.
- Passwords, phone notification tokens and tracker credentials.
- A few internal items that are not business records: the export jobs themselves, undelivered internal system messages, upload fragments in transit, and the copies of policies sent to phones.

**Keep the file safe.** The ZIP has no password and contains the company's records. Keep it on encrypted storage.

Every export request and every download is recorded in the audit log.

**If the subscription is restricted.** A company in read-only status can view its records, and it can still request an export and download it. These are the only two changes allowed in read-only status, and each is recorded in the audit log as made during it. A cancelled subscription is read-only under the standard setting, so these exports stay available after cancellation. A blocked company cannot sign in, so nobody there can export. Take regular exports while the account is active. How long access continues after an agreement ends is covered in the proposed position below.

## Accounts

| Account | Who holds it today |
|---|---|
| The company's logins | Held in the sign-in service run by the Platform Owner. New logins are created by the Platform Owner on request. The company can remove roles itself |
| Company owner role | Held by the company. Asseta will not let the last owner be removed |
| Servers, domain, app store listings | Held by the Platform Owner |

**Proposed position** *(draft, Platform Owner to confirm)*: Asseta is a shared service, so the servers, domain and app store listings stay with the Platform Owner and are not transferred. The company holds its own owner role, controls who has which role, and can take its data out at any time. If the company has its own SIM cards and trackers, those remain the company's property.

## How long data is kept

| Data | How long | Notes |
|---|---|---|
| Business records, ledgers, audit log | Kept. The system has no setting that deletes them over time | Cancelling a subscription does not delete data |
| Evidence files | Kept. The system has no setting that deletes them over time | |
| Data export files | Deleted automatically after 7 days | The company can set 1 to 90 days in its data protection policy |
| Backups | Older than 30 days are removed | Default setting on the server, set by the Platform Owner. See limit 19 in [What the technology cannot fully enforce](04-what-the-technology-cannot-fully-enforce.md) |
| Saved screens on the Owner app | Up to 7 days | Erased on sign-out |
| Unsent records on the Supervisor app | Until they sync | Erased if the phone is revoked. See limit 16 |

**Proposed position after a contract ends** *(draft, Platform Owner to confirm; the periods are suggestions)*:

| Step | Proposed |
|---|---|
| Access to export | The company keeps access to export its data for **90 days** after the agreement ends |
| Deletion | After that, the company's records and evidence files are erased on the company's written request, or after **[period to confirm]** if no request is made |
| Backups | Erased copies leave the backups as those age out (30 days by default) |
| Legal minimums | Tanzanian tax, accounting and personal-data rules may require records to be kept for a minimum time or handled in a set way. **Confirm these with an accountant and a lawyer**; the system has no legal minimums built in |

**Removal tools.** The Platform Owner holds administrative tools that can erase a company's records. They are for test companies and for clearing trial data before go-live, and they need a recent backup. Once the Platform Owner marks a company as live, the reset tool refuses it unless a deliberate override is used, which is recorded.

**Employee data.** The system holds staff names, phone numbers, photos of work, and locations recorded with readings. If site check-ins are switched on, it also records supervisors' positions at those times. The company is responsible for telling its employees and for any consent or notices that the law requires.

## Access by the Platform Owner

**The rule.** Platform staff have no access to a company's business data through the system unless the company has granted a **managed-service mandate**.

| Point | What the system does |
|---|---|
| Consent | A mandate records the company's written consent reference, for example a signed agreement number |
| Scope | **Full** (any of the company's roles) or **Operations** (no roles that manage users or the mandate) |
| Time | A start date and an optional end date. Before or after those dates it gives no access |
| One at a time | One active mandate per company |
| Visibility | The company sees it in **Administration → Managed service**: the mandate, the staff, and the recent actions under it. A banner shows when staff are acting for the company |
| Record | Every action under a mandate appears in the company's audit log, marked as done by Asseta staff under that mandate |
| Ending | The company can click **Revoke mandate** at any time. Access stops at the next request |
| Second-person rules | Still apply. Staff under a mandate cannot revoke it, and cannot decide their own requests |

**Without a mandate**, the Platform Owner can see subscription and billing information for each company, and per-company counts from balance verification, but not the records behind them.

**What this does not cover.** The people who run the servers have technical access below the level of these rules. Direct actions at that level would not appear in the company's audit log. See limit 18 in [What the technology cannot fully enforce](04-what-the-technology-cannot-fully-enforce.md). **Proposed commitment** *(draft, Platform Owner to confirm)*: server-level access is limited to the people who run the service, is used only to operate, secure or repair the service, and is not used to read or change the company's records except where needed for a repair the company has been told about.

**Proposed backup statement** *(draft; fill in the facts before giving this to the company)*:

| Item | Statement |
|---|---|
| Frequency | Daily |
| Kept for | 30 days |
| Off-site copy | **[Confirm: in place at (location) / not yet in place]** |
| Last restore test | **[Date of the last successful restore test]** |
