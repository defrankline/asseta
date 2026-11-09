# The six ledgers

The system is built around six ledgers. A ledger is a permanent list of entries. Entries are added; they are never changed or removed. A mistake is corrected by adding a new entry, and the old one stays visible.

**Every balance you see is worked out from the entries.** Nobody can type a balance in.

| # | Ledger | The question it answers | Where to find it |
|---|---|---|---|
| 1 | Customer hours | How many hours has each customer bought, used and got left? | **Customer hours → Hours ledger** and **Balances** |
| 2 | Excavator engine hours | Has every hour on each machine's meter been accounted for? | **Engine hours → Reconciliation** |
| 3 | Work allocation | Which customer or activity was each engine hour for? | **Engine hours → Work allocations** |
| 4 | Cash collection and custody | Who holds the money right now? | **Finance → Cash custody** |
| 5 | Company cash remittance | How much has actually reached the company? | **Finance → Cash custody → Remittances** |
| 6 | Adjustments and exceptions | What was corrected, by whom, and who approved it? | **Finance → Adjustments ledger** |

---

## Ledger 1: Customer hours

**What it records.** Every purchase is its own batch (a "lot") with a unique number starting HP-. It names the customer, the one excavator the hours were bought for, the hours, the rate from the rate card, any approved discount, and who recorded it. Its payment is a separate record.

Each movement of hours is an entry: activated, used on a job, moved between machines, expired, reversed, corrected, refunded.

**How the balance is worked out.**

> Opening hours + hours activated − hours used ± transfers between machines ± approved corrections − refunds − expired = hours remaining

It is calculated separately for each lot and each machine, and added up for each customer.

**Rules.**

- Hours activate only from a payment confirmed by someone else, or on approved credit within the customer's limit. Nobody can activate hours any other way.
- If part of the price is confirmed, the matching part of the hours activates (a company setting).
- A prepaid job draws on the customer's oldest activated hours for that machine first.
- Hours are taken off when the job is completed, or each day if your company chooses **Every day from the readings**.
- If a job needs more hours than are active, the extra hours are **not** taken. They are flagged as **Hours beyond what the customer has active** for review.
- A correction cannot take a lot below zero or above what was activated.

---

## Ledger 2: Excavator engine hours

**What it records.** Each machine starts from an approved **baseline** (a starting reading, proposed by one person and approved by another). Every accepted reading after that forms an interval with the reading before it.

**How the balance is worked out.**

> Closing meter reading − opening meter reading = total engine hours
>
> Total engine hours = customer work + other authorized hours + hours not yet explained

**Rules.**

- Every hour between two readings is customer work, explained non-customer activity, an identified difference, or **Not yet explained**. There is no other place for an hour to go.
- Time alone never changes what an hour is. After a set number of days (3 unless you change it) an investigation opens, and the hours remain unexplained until a person explains them and a second person approves.
- Readings with open questions (**Provisional**) are left out until reviewed, unless your company chooses to count them.
- A lower reading is flagged, and labelled as a possible meter reset. It only becomes a reset through a request approved by a second person.

---

## Ledger 3: Work allocation

**What it records.** One entry for each unbroken stretch of the meter, per machine, per day: the start and end readings, the hours, what kind they were, who they were for, which purchase lot paid for them, who recorded it, and any approval.

**The kinds of entry.** **Customer work**, **Authorized activity** or **Unexplained**.

**Your guideline's example.** A machine records 10 engine hours in a day:

| Allocation | Hours |
|---|---|
| Customer A | 6 |
| Customer B | 3 |
| Unexplained | 1 |
| **Total** | **10** |

**Engine hours → Work allocations → Per-day reconciliation** shows this for each machine and day: total engine hours, customer, authorized, unexplained, and the **Difference**.

**Rules.**

- **The same engine hours cannot be allocated twice.** The database itself refuses two entries covering the same stretch of the meter.
- A correction never edits an entry. A new entry replaces it, a second person approves, and the original stays visible.
- These entries are written automatically from the readings, jobs and work log, so they cover invoiced and prepaid work alike.

**Things you should know.**

- By default, all time inside a job counts as customer work. If you want every in-job hour backed by a work-log entry, switch off **Time inside a job counts as customer work**. Uncovered hours then show as unexplained.
- A meter does not say what order things happened in. Within one interval, the system lists customer work first, then non-revenue activity, then unexplained hours.
- An interval that runs past midnight is split between the two days in proportion to the clock time.

---

## Ledger 4: Cash collection and custody

**What it records.** Every collection has a unique number (COL- for cash, PAY- for other methods) and records the amount, customer, method, time, who collected it, who holds it, what it pays for, and any evidence. Every transfer between people, float and approved adjustment is also an entry.

**How the balance is worked out, for each person and currency.**

> Opening balance + floats + collections + transfers received − transfers sent − approved cash expenses − remittances confirmed by the company ± approved adjustments − amounts written off = outstanding cash

**Rules.**

- A transfer between two employees **only changes who is responsible**. The company's total outstanding cash does not fall.
- Until the receiver acknowledges a transfer, the cash stays with the sender and shows as in transit.
- Payments a customer makes directly into a company account are recorded separately and never count as cash held by staff.
- **Finance → Cash custody → Reconciliation** shows the sum above for each person and each day. Items still uncertain (claimed remittances, transfers not acknowledged, adjustments awaiting a decision) are listed beside it and are not mixed in.

---

## Ledger 5: Company cash remittance

**What it records.** Every remittance has a unique number starting RMT-. It records the person remitting, the amount declared, the date, how it was paid, the company account, the bank or mobile-money reference, photos of the slip, the amount the company confirmed, who confirmed it and when, and any difference still open.

**The three stages.**

| Stage | Shown as | Meaning |
|---|---|---|
| 1 | **Declared** | A field person says they remitted the money |
| 2 | **Supported** | At least one piece of evidence is attached. Evidence alone never confirms money |
| 3 | **Confirmed** | Someone else recorded the amount actually received |

**How the balance is affected.**

> Custodian's balance goes down by the **amount confirmed**, never by the amount declared.
>
> Amount declared − amount confirmed = difference, which stays open as a **variance** until investigated and closed.

**Rules.**

- The person who holds the cash can never confirm their own remittance, even if someone else recorded it. The person who recorded it cannot confirm it either.
- If your company requires the full balance to be remitted, a partial remittance needs a reason, and a second person decides that reason. That decision is separate from confirming the money.
- A difference is closed only through the variance process. By default a second person must approve the closure.

---

## Ledger 6: Adjustments and exceptions

**What it records.** One entry for each decided correction: the original record, the type, the original value, the new value or amount, the reason, the evidence, who asked, who decided, when, and the **resulting balance**.

**What goes into it.** Hours transfers and cancellations, hours corrections and refunds, credit arrangements, meter corrections, work allocation corrections, explanations of engine hours, non-revenue approvals, cash differences and write-offs, custody adjustments, invoice voids, and reversals of payments, collections and purchases.

Rejected and revoked decisions are recorded too. A proposal still waiting is not an entry yet; it waits on **Finance → Adjustments ledger → Adjustment requests** or on its own approval list. **Overview → Accountability → Pending adjustments** shows them all in one place.

Approved cash **retentions** are not in this ledger. A retention changes how much must be remitted, not how much the person holds.

**Rules.**

- No user can edit or delete a posted record. The database refuses it.
- Nobody can decide their own proposal, and no company setting can change that for these requests.
- Decisions made before this ledger was introduced appear without a resulting balance.

**Reversing a payment that bounced.** The original payment stays on record, marked as reversed. Unused hours it paid for come off. Hours already used become money owed, as an invoice or an investigation (your company's choice). If cash was involved, the custodian's balance falls by that amount.

---

## If a figure and the ledger disagree, the ledger wins

Any summary figure can be rebuilt from its records. **Administration → Balance verification** does this on request: click **Verify now**. It recomputes customer hours per lot, engine hours per machine, cash per custodian, customer receivables, daily report figures and invoice totals, and lists any difference under **From the records**, **Stored figure** and **Difference**.

**It corrects nothing.** The records prevail, and a difference is a question for a person. You can have it run on a schedule by setting that in the policies (off until you switch it on).

---

## How to trace a balance

**To find any record quickly:** type its number or outside reference (for example HP-, COL-, RMT- or a bank reference) in the **Find a reference** box at the top of the web console. The result shows what it is, who recorded it, who decided it and what balance remains. The Owner app has the same search under **More → Find a reference**.

**Start from the dashboard:** every figure on **Overview → Accountability** can be clicked to open the records behind it.

### A customer's hours

1. **Customer hours → Balances**, choose **By customer**, and find the customer.
2. Open **Hours statement** for a period: opening balance, bought, activated, used per day and per job, moved, expired, closing balance.
3. Open **Customer hours → Hours purchases** and the purchase: its hours, payments and history.
4. Click **Open the hours ledger** to see every movement.
5. From a used-hours entry, open the job. It shows the readings with their photos and the customer's acknowledgement.
6. From an activation entry, open the payment. It shows who recorded it and who confirmed it.

### An excavator's hours

1. **Engine hours → Reconciliation** and click the machine.
2. The **Engine-hour timeline** lists each interval with **From**, **To** and **Hours**, and how they split.
3. Open a reading to see its photo, GPS position, device time and the time the central system received it.
4. **Engine hours → Work allocations** shows which customer each hour was allocated to, and from which purchase.
5. **Engine hours → Hours to explain** lists what remains unexplained.

### A person's cash

1. **Finance → Cash custody → All custodians** and click the person.
2. **Reconciliation**: choose the person and period. Each figure can be clicked to open the transactions behind it for that day.
3. Open a remittance to see the declared and received amounts, the slip photos and who confirmed it.
4. **Operations → Staff**, open the person, click **Accountability** for everything they collected, transferred, remitted and approved.

### Who did what, and when

**Administration → Audit log** lists every change with who, when, what, the reason, and the values before and after.

---

## How the records are stored (for your IT adviser)

| Point | How it works |
|---|---|
| Separation between companies | Every record carries its company, and the database enforces the filter |
| Protection from change | Ledger tables are protected in the database itself: the application has no right to rewrite or remove their entries, and triggers refuse attempts |
| Duplicates | Each offline transaction has a unique identifier created on the phone, and the database refuses a second copy |
| Double allocation | A database rule refuses overlapping meter ranges on the same machine |
| Numbers | Unique per company and generated centrally. HP- purchases are gap-free |
| Money and times | Exact decimal amounts; all times stored in UTC and shown in your local time |
| Evidence | Stored separately, under a checksum of the file, and write-once |
