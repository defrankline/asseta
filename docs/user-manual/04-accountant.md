# Asseta user manual: Accountant / Finance

> Part of the [Asseta user manual](README.md). Read the README first for signing in and the glossary.

## Who this is for

This manual is for the people who look after the money side of an equipment-hire company in Asseta. That covers bookkeepers, accountants, finance officers and office cashiers. In Asseta this role is called **Accountant / Finance**.

You work in the **web console** at <https://asseta.co.tz> on a laptop or desktop. You do not need a mobile app.

## What you can do

- **Bill customers.** Turn completed, billing-ready jobs into hire invoices. Issue them, print them and void them if needed.
- **Record customer payments** and allocate them to invoices. Payments can be cash, bank transfer or mobile money, and can be partial or advance.
- **Verify or reject** payments and cash handovers that other people recorded.
- **Manage supervisor cash.** Issue cash floats, record opening balances, and run the daily cash reconciliation for each supervisor.
- **Track expenses and fuel.** See every field expense and fuel event, manage expense categories, and record your own expenses and fuel purchases.
- **Report on profitability** by machine, job or customer for any period.
- **Look up** jobs, machines, customers and staff (read-only) so invoices and cash records show real names.
- **Read investigations** (read-only) when a case concerns money.
- **View the company's Asseta subscription** and its invoices.

What you cannot do as an accountant:

- You cannot approve expenses. Expenses above the approval limit go to an owner or manager in **Approvals**.
- You cannot create or approve jobs, change machines, or review meter exceptions.
- You cannot verify a payment or handover that you recorded yourself (see [Segregation of duties](#segregation-of-duties)).

## Where you work

These are your side-menu groups in the web console. The exact menus depend on your company's role setup.

| Menu group | Menus | Used for |
|---|---|---|
| Field work | Fuel, Expenses, Cash | Your own fuel events, expenses and cash collections, the same screens a supervisor uses |
| Operations | Jobs, Customers, Staff | Looking up jobs, customers (balances, statements) and staff (read-only) |
| Fleet | Machines | Looking up machines (read-only) |
| Finance | Hire finance, Expenses & fuel, Profitability | Your main daily work |
| Risk & review | Investigations | Reading investigation cases (read-only) |
| Administration | Subscription, Notifications, My access | Your company's Asseta subscription, your inbox, your sign-in settings |

**Tip:** Many lists have an **Export** button that downloads CSV or PDF. You will find it on the Jobs list, Expenses, Machines, Cash custody and Reconciliation, among others.

---

## Key ideas for finance users

### Claimed money and verified money

Asseta keeps two kinds of money record apart:

- **Claimed (unverified).** Someone has recorded that money was received or handed over, but nobody has confirmed it yet. Claimed money does not reduce a customer's balance or a supervisor's cash accountability.
- **Verified.** A second person has confirmed the money really arrived. Only verified money settles balances.
- **Rejected.** The money was not received. Any allocations to invoices are released.

The Customer payments tab explains this on screen: *"Claimed: recorded but not yet verified. These do NOT reduce customer balances or supervisor accountability yet."*

### Segregation of duties

The person who records or requests something cannot also decide it:

- If you recorded a payment, someone else must verify or reject it. The button then reads **Verify / reject (not allowed: you recorded it)**.
- If you recorded a cash handover, someone else must verify it.
- If you submitted an expense, someone else must approve it.

If you try anyway, Asseta shows: *"The person who recorded or requested this cannot decide it. Ask another authorised colleague."*

### Hire finance is separate from your Asseta subscription

**Hire finance** is the money your customers owe *your company* for hiring machines. **Subscription** is what your company pays *Asseta* for the software. They have separate invoices and payments and never mix.

### Billing-ready jobs

A job can be invoiced only when it is **Completed** and **billing-ready**. A completed job is *not* billing-ready while it has a **blocking exception**, meaning a meter or GPS finding that someone must review first, such as a meter reading that went down. The office (normally the owner) reviews these in **Risk & review → Exceptions**. When the review is recorded, the job becomes billing-ready.

---

## Tasks

### 1. Create and issue a hire invoice

1. Go to **Finance → Hire finance** and stay on the **Hire invoices** tab.
2. Click **New invoice**. The **New hire invoice (draft)** dialog opens.
3. Choose the **Customer**.
4. Under **Jobs to invoice**, tick the jobs to bill. Only that customer's completed jobs are listed. Each one shows **Billable hours**, **Charges (server)** and a **Billing** status. A job marked **Not billable (N blocking)** cannot be selected until its exceptions are reviewed.
5. Add **Notes (optional)** and click **Create draft**.

   *What you'll see:* "Draft invoice created." The invoice appears with status **Draft**.
6. Open the draft (**View details**) and check the lines, which show **Kind**, **Description**, **Quantity**, **Unit price** and **Amount**, and the totals.
7. Click **Issue invoice**. You can set a **Due date (optional)**. It defaults to the issue date plus the customer's payment terms.
8. Click **Issue invoice** to confirm.

   *What you'll see:* the invoice gets a number and status **Issued**.

**Good to know**

- An issued invoice is fixed. To correct it, **Void (reverse)** it and create a new one. Voiding cannot be undone. The voided invoice is kept unchanged for audit.
- A draft you no longer want can be thrown away with **Discard draft (void)**. Its jobs are released so they can be invoiced again.
- If a job's charges changed after you drafted the invoice, Asseta refuses to issue it: *"Job charges changed since drafting. Void this draft and create a new one from the current charges."*
- **Print view** opens a printable invoice with **Bill to**, **Tax ID** and **Payment terms**. Use your browser's print or "Save as PDF".
- Filters on the Hire invoices tab: **Customer**, **Status**, **Overdue only**. The **Balance (verified)** column counts only verified payments.

### 2. Record a customer payment

Use this when a customer pays by bank transfer, mobile money or cash at the office.

1. Go to **Finance → Hire finance → Customer payments**. You can also click **Record payment** on an invoice's detail page.
2. Click **Record payment**. The **Record customer payment** dialog opens.
3. Fill in **Customer**, **Amount**, **Currency**, **Method** (Cash, Bank transfer or Mobile money) and **Received at**.
4. For bank and mobile money, enter the **Transaction reference**. A method plus reference pair can only be used once, which prevents double entry.
5. Optionally fill in **Received by**, the staff member who received the money.
6. Under **Allocations**, choose the issued invoice or invoices this payment pays, and how much goes to each. You can leave allocations empty. Unallocated money becomes customer credit (a deposit or advance) once verified, and can be allocated later.
7. Click **Record payment**.

   *What you'll see:* "Payment recorded as CLAIMED; it counts once verified."

### 3. Verify or reject a payment

1. Go to **Finance → Hire finance → Customer payments**.
2. Use the status toggle **Claimed (unverified)** to see what is waiting.
3. On a payment, click **Verify / reject**. The **Verify customer payment** dialog opens.
4. Check the amount, method and reference against your bank statement, mobile-money record or cash.
5. Choose verify or reject and add a note, then confirm.

   *What you'll see:* "Payment verified." or "Payment rejected."

If you recorded the payment yourself, the button is disabled. Ask a colleague.

### 4. Allocate a payment (or customer credit) to invoices later

1. On the **Customer payments** tab, find a verified payment that still has an **Unallocated** amount.
2. Click **Allocate to invoices**. The **Allocate payment to invoices** dialog opens.
3. Add each invoice and the amount for it, then click **Allocate**.

Rules Asseta checks for you:

- You cannot allocate more than the invoice's open amount.
- All allocations together cannot exceed the payment amount.
- Every invoice must be in the payment's currency.
- A rejected payment cannot be allocated.

### 5. Look at a customer's balance and statement

1. Go to **Operations → Customers** and open a customer.
2. The **Balance** tab shows, per currency:
   - **Invoiced**
   - **Verified payments**
   - **Reversed (voided invoices)**
   - **Unallocated credit (deposits / advances)**
   - **Open invoices**
   - **Balance due**
3. The **Statement** tab shows a period's **Opening balance**, each debit and credit, and the **Closing balance**. Choose the period with **From** and **To**, and the **Statement currency**.

### 6. Issue a cash float to a supervisor

1. Go to **Finance → Hire finance → Cash custody**.
2. Choose the **Supervisor**.
3. Click **Record float**. The **Record cash float** dialog opens.
4. Choose the **Entry** type:
   - **Float issued**: cash the office gives the supervisor.
   - **Opening balance**: cash the supervisor already held when tracking started.
5. Enter **Amount**, **Currency**, **Issued at**, and optionally a **Reference** and **Note**.
6. Click **Record float**.

   *What you'll see:* "Float recorded." The supervisor's custody card updates.

Each supervisor's custody card (one per currency) shows:

- **Outstanding accountability**: what the supervisor should be holding.
- **Claimed handovers (not yet verified)**
- **Expenses pending approval**

### 7. Verify a cash handover

When a supervisor hands cash to the office, they record a handover in their app or the web console. It arrives as **Claimed (unverified)**.

1. Count the cash, or check the bank deposit slip.
2. Go to **Finance → Hire finance → Handovers**. Filter **Handover status** to Claimed.
3. Click **Verify / reject** on the handover. The **Verify cash handover** dialog opens.
4. Verify it if the money matches. Reject it with a note if it does not.

   *What you'll see:* "Handover verified." or "Handover rejected." The supervisor sees your note in their **Office note** column.

You can also record a handover on someone's behalf (**Record handover** on the Cash custody tab, with **Handed over by (custodian)**). This needs office cash permission. Another person must then verify it.

### 8. Run the daily cash reconciliation

1. Go to **Finance → Hire finance → Reconciliation**.
2. Choose the **Supervisor**, the **Currency** and the period (**From** / **To**).
3. Each day shows the calculation:

   **Opening + floats + collections − approved cash expenses − verified handovers = outstanding**

4. Below the main figure, Asseta lists what is still uncertain:
   - **Unverified collections** (included above)
   - **Claimed handovers** awaiting verification
   - **Pending expenses** (cash expenses pending approval)
   - **Outstanding if claims verified**: what the outstanding would be once the claims are confirmed.

**How to read it:** if **Outstanding** is higher than the supervisor says they hold, first verify any pending handovers and ask an approver to decide pending expenses. Then compare again. Use **Export** to keep a CSV or PDF copy.

### 9. Review expenses and fuel

1. Go to **Finance → Expenses & fuel**.
2. The **Expenses** tab lists every expense with **Category**, **Description**, **Machine**, **Paid from**, **Amount** and **Status** (Pending approval, Approved, Rejected). Filter by **Status**, **Machine** or **Custodian**.
3. Click **View details** to see:
   - **Submitted by**, **Source**, **Supplier**, **Policy version**, and whether a receipt was required.
   - The receipts (**View receipt**) and the **GPS at capture**.
   - Any **Open approvals**, plus **Decided** and **Decision note** once decided.
4. The **Fuel events** tab lists fuel purchases, issues to machines and usage, with **Litres**, **Meter**, **Supplier** and **Attributed cost**.

**Paid from** matters for cash:

- **Supervisor cash custody**: the supervisor paid from cash in hand. Once approved, it reduces their outstanding cash.
- **Company (office / bank)**: paid by the office. It does not affect custody.

### 10. Manage expense categories

1. In **Expenses & fuel**, open **Expense categories**.
2. **New expense category** needs a **Code** and a **Name**.
3. To retire a category, deactivate it with a reason. New expenses can no longer use it, but past expenses keep it. You can reactivate it later.

### 11. Record your own expense, fuel or cash collection

You have the same **Field work** screens as a supervisor:

- **Field work → Expenses → Submit expense**
- **Field work → Fuel → Record fuel**
- **Field work → Cash → Record cash collection** / **Hand over cash**

The steps are described in the [Supervisor manual](03-supervisor.md#working-from-a-laptop-web-console). The same rules apply: your own submissions must be approved or verified by someone else.

### 12. Profitability report

1. Go to **Finance → Profitability**.
2. Choose the period (**From** / **To**) and **Group by**: **By machine**, **By job** or **By customer**.
3. The report shows recognised hire revenue against approved direct costs, per currency, plus **Costs by category**.

Revenue means **issued invoices, excluding tax**. Voided invoices reverse their revenue. Costs are **approved, categorised** expenses and fuel only. Pending or rejected expenses are not counted.

### 13. Check the company's Asseta subscription

Go to **Administration → Subscription** to see your company's subscription with the Platform Owner, the billable machines and the Platform Owner's invoices to your company. This is read-only for you.

---

## Statuses and what they mean

| Where | Status | Meaning |
|---|---|---|
| Hire invoice | Draft | Being prepared; can be issued or discarded |
| | Issued | Numbered and fixed; can only be corrected by voiding |
| | Voided | Reversed (if issued) or discarded (if draft); kept for audit |
| Invoice payment state | Unpaid / Partially paid / Paid | Based on **verified** payments only |
| Payment, collection, handover | Claimed (unverified) | Recorded, waiting for a second person to confirm |
| | Verified | Confirmed; settles balances or reduces custody |
| | Rejected | Not received; allocations released |
| Expense | Pending approval | Above the auto-approval limit; waiting in Approvals |
| | Approved | Counts as cost (and against custody if paid from cash) |
| | Rejected | Kept as evidence; never counts as cost or custody |
| Job (for billing) | Billing ready / Not billing ready | Not ready means readings are missing or blocking exceptions are not yet reviewed |

## Good practice

- **Verify daily.** Supervisors' cash stays "claimed" until you verify it. Late verification makes the reconciliation look worse than reality.
- **Always enter references** (bank transaction ID, mobile-money code, receipt book number). They prevent double entry and help audits.
- **Never edit around a mistake.** Void the invoice or reject the payment, and record it again correctly. Asseta keeps the full trail.
- **Keep different currencies apart.** Asseta never adds TZS and USD together, so check the currency before saving.
- **Export month-end reports** (Reconciliation, Cash custody, Expenses) for your records.

## Troubleshooting and FAQ

**A completed job does not appear when I create an invoice.**
It is not billing-ready yet. Open the job in **Operations → Jobs** and look for "N blocking billing". Ask the owner to review the exceptions in **Risk & review → Exceptions**. Also check the job belongs to the customer you chose and is not already on another invoice.

**"Verify / reject (not allowed: you recorded it)".**
You recorded this item. A colleague with verify permission must decide it.

**"A payment with this method and reference already exists."**
This payment was already recorded. Search the Customer payments list for the reference.

**"Allocate no more than the invoice's open amount."**
Part of the invoice is already paid. Reduce the allocation, and leave the rest as unallocated credit.

**"Issued invoices are immutable; correct them by voiding."**
Void (reverse) the invoice, then create a new draft from the jobs.

**The reconciliation shows a large outstanding amount for a supervisor.**
Check the **Claimed handovers** and **Pending expenses** lines. Verify the handovers, ask an approver to decide the expenses, then re-check. If a real gap remains, talk to the supervisor. Asseta may also raise a "Cash not handed over" reminder or signal for review.

**"Your login is not linked to a staff record; pick the staff member explicitly."**
To record cash in your own custody, your login must be linked to a staff record. Ask the owner to link it in **Operations → Staff** (App login), or choose the staff member explicitly.

**The page says the company is read-only.**
Your company's Asseta subscription is restricted. You can view everything but cannot make changes. Contact your account owner.
