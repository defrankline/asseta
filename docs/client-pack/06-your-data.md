# Your data

> **DRAFT for the Platform Owner to review. Not yet approved. Do not give this to the company until it has been reviewed.**
>
> This draft describes what the system does today. It makes no legal promise. Any ownership statement, contract term or legal commitment is for the Platform Owner to add. Items the Platform Owner must decide are marked **[To decide]**.

## What data the company has in Asseta

| Kind | Examples |
|---|---|
| **Business records and ledgers** | Customers, contracts, rate cards, jobs, readings, work allocations, customer hours, cash, remittances, invoices, payments, expenses, fuel, adjustments |
| **Evidence files** | Meter photos, receipts, deposit slips, machines' photos, customer signatures |
| **Tracking data** | Machine positions and engine data reported by trackers |
| **Configuration** | Company policies and their versions, reason lists, deposit accounts, notification settings |
| **History** | The audit log, security events, investigations and sync records |
| **People** | Staff records and the roles they hold |

**[To decide]** Proposed statement on ownership, for the Platform Owner and the company to agree. Your guideline asks for confirmation that the company will own and have access to its data, system configuration and necessary accounts.

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

**If the subscription is restricted.** A company in read-only status can view its records but cannot request a new export or download link. A blocked company cannot sign in. Take regular exports while the account is active. **[To decide]** How the company obtains its data if the subscription ends.

## Accounts

| Account | Who holds it today |
|---|---|
| The company's logins | Held in the sign-in service run by the Platform Owner. New logins are created by the Platform Owner on request. The company can remove roles itself |
| Company owner role | Held by the company. Asseta will not let the last owner be removed |
| Servers, domain, app store listings | Held by the Platform Owner |

**[To decide]** Whether any of these accounts are to be transferred or shared with the company. The system has no feature for this.

## How long data is kept

| Data | How long | Notes |
|---|---|---|
| Business records, ledgers, audit log | Kept. The system has no setting that deletes them over time | Cancelling a subscription does not delete data |
| Evidence files | Kept. The system has no setting that deletes them over time | |
| Data export files | Deleted automatically after 7 days | The company can set 1 to 90 days in its data protection policy |
| Backups | Older than 30 days are removed | Default setting on the server, set by the Platform Owner. See limit 19 in [What the technology cannot fully enforce](04-what-the-technology-cannot-fully-enforce.md) |
| Saved screens on the Owner app | Up to 7 days | Erased on sign-out |
| Unsent records on the Supervisor app | Until they sync | Erased if the phone is revoked. See limit 16 |

**[To decide]** Retention period and deletion after the end of a contract. Any legal minimum retention. The system has no legal minimums built in.

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

**What this does not cover.** The people who run the servers have technical access below the level of these rules. Direct actions at that level would not appear in the company's audit log. See limit 18 in [What the technology cannot fully enforce](04-what-the-technology-cannot-fully-enforce.md). **[To decide]** What the Platform Owner commits to in the agreement about such access.

**[To decide]** Backup arrangements to be confirmed to the company: whether the off-site copy is in place, and when a restore was last tested.
