# Asseta user manual: Accountant / Finance

> Part of the [Asseta user manual](README.md). Read the README first for signing in and the glossary.

## Who this is for

This manual is for the people who look after the money side of an equipment-hire company in Asseta. That covers bookkeepers, accountants, finance officers and office cashiers. In Asseta this role is called **Accountant / Finance**.

You work in the **web console** at <https://asseta.co.tz> on a laptop or desktop. You do not need a mobile app. (If your company gives you the **Asseta Owner** app, people with the right permissions can also confirm or dispute cash handovers and issue cash floats from it. See the [Tenant Owner manual](01-tenant-owner.md#approvals).)

## What you can do

- **Bill customers.** Turn completed, billing-ready jobs into hire invoices. Issue them, print them and void them if needed.
- **Record customer payments** and allocate them to invoices. Payments can be cash, bank transfer or mobile money, and can be partial or advance.
- **Verify or reject** payments and cash handovers that other people recorded.
- **Manage custodians' cash.** Issue cash floats, record opening balances, confirm remittances with the amount actually received, and run the daily cash reconciliation for each custodian (any staff member who holds cash, with or without a login).
- **Follow the cash chain** (when your company switches it on): transfers between custodians and their acknowledgement, cash differences (variances) and write-offs, requests to keep cash (retentions), custody adjustments, overdue remittances and the cash reason lists.
- **Customer hours**: link payments to hours purchases, verify those payments (which activates the hours), and activate hours on approved credit. Follow hours **in use by running jobs**, **low-balance warnings** and the customer **hours statement**.
- **Deposit accounts**: keep the list of company bank accounts, mobile-money wallets and cash offices that remittances are paid into, and check each remittance's account, reference and slip photos against the statement.
- **Revenue checks** (when your company switches them on): read the **Daily machine sheet**, and explain **revenue differences** and **non-revenue hours**. Someone else decides them.
- **See the Accountability dashboard.**
- **Track expenses and fuel.** See every field expense and fuel event, manage expense categories, and record your own expenses and fuel purchases.
- **Report on profitability** by machine, job or customer for any period.
- **Look up** jobs, machines, customers and staff (read-only) so invoices and cash records show real names.
- **Read investigations** (read-only) when a case concerns money.
- **View the company's Asseta subscription** and its invoices.

What you cannot do as an accountant:

- You cannot approve expenses. Expenses above the approval limit go to an owner or manager in **Approvals**.
- You cannot create or approve jobs, change machines, or review meter exceptions.
- You cannot verify a payment or handover that you recorded yourself, or decide a write-off, retention or adjustment you proposed (see [Segregation of duties](#segregation-of-duties)).

Approvals follow permissions, not job titles. In the example role set-up the accountant holds the cash approval permissions (write-offs, retentions, custody adjustments); your company may give them to others.

## Where you work

These are your side-menu groups in the web console. The exact menus depend on your company's role setup.

| Menu group | Menus | Used for |
|---|---|---|
| Overview | Accountability | The accountability dashboard |
| Field work | Fuel, Expenses, Cash, Customer hours | Your own fuel events, expenses and cash collections, the same screens a supervisor uses |
| Operations | Jobs, Customers, Staff | Looking up jobs, customers (balances, statements) and staff (read-only) |
| Fleet | Machines | Looking up machines (read-only) |
| Customer hours | Hours purchases, Balances, Hours ledger, Work allocations, and the other hours pages (read) | Linking payments to purchases and activating hours on credit |
| Engine hours | Non-revenue hours, Daily machine sheet | Revenue checks: reading each machine's day and explaining non-revenue time |
| Finance | Hire finance, Cash custody, Expenses & fuel, Deposit accounts, Revenue differences, Profitability | Your main daily work |
| Risk & review | Investigations | Reading investigation cases (read-only) |
| Administration | Subscription, Notifications, My access | Your company's Asseta subscription, your inbox, your sign-in settings |

**Hire finance** holds **Hire invoices** and **Customer payments**. Everything about cash held by people is under **Finance → Cash custody** ("Cash held by custodians, transfers between them, remittances to the company and their reconciliation"). Its tabs are **All custodians**, **Custody**, **Transfers**, **Floats**, **Remittances**, **Overdue remittances**, **Variances**, **Retentions**, **Adjustments**, **Reconciliation** and **Reason lists**. Old links to the cash tabs of Hire finance open Cash custody.

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

If you try anyway, Asseta shows: *"The person who recorded or requested this cannot decide it. Ask another authorised colleague."* On your own records the menu item reads, for example, **Confirm / reject (Someone else must decide your own request)** and is disabled. The attempt is recorded as a security event for oversight.

### Field cash is not company money until confirmed

- Cash a customer pays in the field is in a **custodian's** hands, not the company's.
- A **transfer** between two custodians moves accountability between them; it is never a company receipt.
- Only a **remittance** you confirm, at the **amount actually received**, is company money. A difference opens a **variance** for review.

### Opening a record directly

Notifications about a transfer, float, remittance, overdue remittance, variance, retention or custody adjustment open that record's own page, with its history (who recorded, acknowledged, proposed and decided it, and when). From there you can act on it.

### Hire finance is separate from your Asseta subscription

**Hire finance** is the money your customers owe *your company* for hiring machines. **Subscription** is the fee your company pays the *Platform Owner* for using Asseta. They have separate invoices and payments and never mix.

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

### 6. See all custodians' cash at once

1. Go to **Finance → Cash custody → All custodians**.
2. Choose the **As of** day and, optionally, the **Currency**.
3. Each row shows the **Supervisor**, **Currency**, **Outstanding accountability**, **Claimed handovers (not yet verified)**, **Expenses pending approval** and **As of**.

Outstanding = floats + collections − approved cash expenses − verified handovers, at the end of the chosen day. Claims do not reduce it until verified. Click a row to open that person's **Custody** tab.

### 7. Issue a cash float to a supervisor

1. Go to **Finance → Cash custody → Custody**.
2. Choose the **Custodian**.
3. Click **Record float**. The **Record cash float** dialog opens. Choose the **Supervisor (custodian)**.
4. Choose the **Entry** type:
   - **Float issued**: cash the office gives the supervisor.
   - **Opening balance**: cash the supervisor already held when tracking started.
5. Enter **Amount**, **Currency**, **Issued at**, and optionally a **Reference** and **Note**.
6. Click **Record float**.

   *What you'll see:* "Float recorded." The supervisor's custody card updates.

Each custodian's custody card (one per currency) shows:

- **Outstanding accountability**: what the custodian should be holding.
- **Claimed handovers (not yet verified)**
- **Expenses pending approval**
- With the controls on: **Sent, not yet acknowledged (still held)**, **Incoming, not yet acknowledged**, **Floats awaiting acknowledgement** and **Approved to keep (retention)**.

If your company has **Receiver acknowledges floats** on, the float counts in the custodian's cash only once they acknowledge it (see [Task 15](#15-cash-transfers-and-float-acknowledgements)).

### 8. Confirm a remittance (cash handover)

When a custodian hands cash to the company, they (or a recorder on their behalf) record a **remittance**, called a handover in the apps. It arrives **Awaiting confirmation**. "Remittances awaiting confirmation do not reduce a custodian's outstanding cash until someone other than the recorder confirms the amount received."

1. Count the cash, or check the bank deposit slip or mobile-money statement.
2. Go to **Finance → Cash custody → Remittances**. It shows **Awaiting confirmation** by default; you can switch to **Confirmed**, **Rejected** or **All**, and filter by **Custodian**. The columns include **Paid by**, **Company account**, **Reference**, **Declared**, **Received** and **Short of full balance**.
3. Click **Confirm / reject** on the remittance. The **Confirm remittance** dialog opens. It shows the **Custodian**, **Amount declared**, **Handed over**, **Paid by** (**Cash handed to the office**, **Bank deposit** or **Mobile money**), **Company account**, **Reference** and **Photos** (**View photo 1** and so on). "Confirm only after counting the cash or seeing the deposit." Compare the account, reference and photos with your statement.
4. Choose the **Decision**:
   - **Confirm (cash counted)**: enter the **Amount received**, the amount you actually counted.
   - **Reject (not received)**: a **Note / reason** is required.
5. Click **Record decision**.

   *What you'll see:* "Remittance confirmed." or "Remittance rejected." The custodian sees your note in their **Office note** column.

"Enter the amount actually received; a difference from the declared amount opens a variance. A rejected remittance never reduces the custodian's outstanding cash." If your company expects the full balance to be remitted (**Remit the full balance**), a remittance that leaves cash not covered by an approved retention is flagged as a **Partial remittance**, and the people who confirm remittances are notified.

Handovers can also be confirmed (verified) or disputed (rejected) in the Asseta Owner app by people with verify permission, often the owner when away from the office. The result is the same, and the same segregation-of-duties rule applies.

You can also record a remittance on someone's behalf: **Record remittance** on the **Custody** tab, with **Handed over by (custodian)**, **How was it paid?**, **Company account**, **Transaction reference** and **Photo of the deposit slip or payment confirmation** (**Add photo**). This needs office cash permission (or your company's permission for recorders). Another person must then confirm it.

### 9. Run the daily cash reconciliation

1. Go to **Finance → Cash custody → Reconciliation**.
2. Choose the **Custodian**, the period (**From** / **To**) and the **Currency**.
3. The card for the last day shows the calculation:

   **Opening + floats + collections + transfers received − transfers sent − approved cash expenses − confirmed remittances ± approved adjustments − written off = outstanding**

4. Beside it, under **Claims not yet counted (shown separately)**, Asseta lists what is still uncertain:
   - **Remittances awaiting confirmation**
   - **Cash expenses pending approval**
   - **Collections not yet verified (included above)**
   - **Sent, not yet acknowledged (still held)** and **Incoming, not yet acknowledged**
   - **Floats awaiting acknowledgement**
   - **Adjustments awaiting decision**
   - **Outstanding if claimed remittances are confirmed**
5. The daily table below shows the same columns for each day.

**Drill down to the evidence.** Click any figure (except Opening and the totals) to open the transactions behind it for that day. Each row shows **When**, **Record**, **Status**, **Other custodian**, **Recorded by**, **Note** and **Amount**, and the record links to its own page. Use **Copy id** when you need a record's id, for example for a reversal.

**How to read it:** if **Outstanding** is higher than the supervisor says they hold, first verify any pending handovers and ask an approver to decide pending expenses. Then compare again. Use **Export** to keep a CSV or PDF copy.

### 10. Review expenses and fuel

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

### 11. Manage expense categories

1. In **Expenses & fuel**, open **Expense categories**.
2. **New expense category** needs a **Code** and a **Name**.
3. To retire a category, deactivate it with a reason. New expenses can no longer use it, but past expenses keep it. You can reactivate it later.

### 12. Record your own expense, fuel or cash collection

You have the same **Field work** screens as a supervisor:

- **Field work → Expenses → Submit expense**
- **Field work → Fuel → Record fuel**
- **Field work → Cash → Record cash collection** / **Remit cash**

The steps are described in the [Supervisor manual](03-supervisor.md#working-from-a-laptop-web-console). The same rules apply: your own submissions must be approved or verified by someone else.

### 13. Profitability report

1. Go to **Finance → Profitability**.
2. Choose the period (**From** / **To**) and **Group by**: **By machine**, **By job** or **By customer**.
3. The report shows recognised hire revenue against approved direct costs, per currency, plus **Costs by category**.

Revenue means **issued invoices, excluding tax**. Voided invoices reverse their revenue. Costs are **approved, categorised** expenses and fuel only. Pending or rejected expenses are not counted.

### 14. Check the company's Asseta subscription

Go to **Administration → Subscription** to see your company's subscription with the Platform Owner, the billable machines and the Platform Owner's invoices to your company. This is read-only for you.

### 15. Cash transfers and float acknowledgements

**Transfers** are cash handed from one custodian to another in the field, for example an operator to a manager. They are recorded in the apps or in **Finance → Cash custody → Transfers** (**Record transfer**).

- With **Receiver acknowledges transfers** on (your company policy), a transfer stays **Awaiting acknowledgement** and the cash stays in the sender's custody ("in transit") until the receiver acknowledges the amount actually received. A recorder who is the receiver acknowledges by recording it, if your policy allows.
- To answer on the receiver's behalf, click **Acknowledge / dispute**, count the cash, choose **Acknowledge (cash received)** with the **Amount actually received**, or **Dispute (not received)** with a **Note**, and click **Record answer**. The person who recorded the transfer cannot answer it: "You recorded this transfer; the receiver must answer it."
- A different amount opens a variance: "Transfer acknowledged; the difference was opened as a variance." A disputed transfer stays with the sender.

**Floats** work the same way on the **Floats** tab when **Receiver acknowledges floats** is on (filter **Awaiting acknowledgement** / **All**). The person who issued a float cannot answer it.

### 16. Cash differences (variances) and write-offs

A **variance** opens automatically whenever the amount received differs from the amount declared on a transfer, remittance or float. It names the **Accountable custodian**. A variance is a fact to follow up, not an accusation. If your policy sets **Open a case for differences above**, larger differences also open an investigation, and the people with variance permission get a "Cash difference to review" notification.

1. Go to **Finance → Cash custody → Variances** (shows **Open** by default). Filter by **From** (**Transfer**, **Remittance**, **Float**) or **Custodian**. The **Kind** column shows **Shortfall** (less received than declared) or **Surplus to explain** (more received than declared, for example when the bank statement shows more than the custodian declared).
2. To close one, click **Resolve**. Choose the **Outcome**: **Recovered**, **Corrected error** (or **Written off**, only if your company does not require write-off approval and you hold the write-off permission). Choose a **Reason (from the tenant's list)** if your company keeps one, write the **Explanation**, and click **Resolve**.
3. To write the difference off, click **Propose write-off**, choose the **Write-off reason (from the tenant's list)**, write the **Explanation**, and click **Propose write-off**. *What you'll see:* "Write-off proposed; someone else with the write-off permission decides."
4. A colleague with the write-off permission clicks **Approve / reject write-off**, chooses **Approve** or **Reject** with a **Note / reason**, and clicks **Record decision**. "Approving resolves the variance as written off and lowers the custodian's expected balance by the difference. Rejecting returns it to open."

### 17. Requests to keep cash (retentions)

Normally the whole balance is remitted. A custodian who needs to keep some cash asks for a **retention** (from the apps, **Field work → Cash → Keep cash requests**, or **Finance → Cash custody → Retentions → Request to keep cash**). Requests made offline arrive when the phone syncs.

1. Go to **Finance → Cash custody → Retentions** (shows **Awaiting decision** by default).
2. Click **Approve / reject**. Check the **Custodian**, **Amount to keep**, **Reason** and **Requested by**.
3. Choose **Approve** or **Reject**, write a note (required to reject) and click **Record decision**.

*What you'll see:* "Retention approved." "An approved retention lets the custodian keep this amount instead of remitting it; the full-remittance check allows for it." If your policy has **Approved retentions allowed** off, the tab says "Your organisation does not allow keeping cash: everything collected is remitted."

### 18. Custody adjustments

Cash records are never edited or deleted. A mistake is corrected with a **custody adjustment** that a second person approves.

1. Go to **Finance → Cash custody → Adjustments** and click **Propose adjustment**.
2. Choose the **Custodian** and the **Kind**: **Adjustment** or **Reversal of a record**.
3. Enter the **Amount** ("Positive raises the expected balance; negative (e.g. -5000) lowers it.") and **Currency**.
4. Choose a **Reason (from the tenant's list)** if your company keeps one, and write the **Reason**.
5. For a reversal, choose the **Record reversed** type and paste its **Record id** ("Copy it from the reconciliation drill-down.").
6. Click **Propose adjustment**. *What you'll see:* "Adjustment proposed; it counts once someone else approves it."

A colleague with the adjustment permission clicks **Approve / reject** and records the decision. "An approved adjustment changes the custodian's expected balance by the signed amount; a rejected one never counts."

### 19. Overdue remittances

Asseta flags cash that stays with a custodian too long, in two ways that work side by side (Cash custody policy):

- **Daily remittance cut-off**: every day, after that local hour, custodians who still hold cash they have not remitted are flagged once per day with the reason **Not remitted by the cut-off**.
- **Days a custodian may hold unremitted cash** (the holding allowance; it can differ per site or per staff member): cash held longer than allowed, and not covered by an approved retention, is flagged with the reason **Held longer than allowed**. The notification reads "<name> has held <amounts> since <date>, longer than the allowed N days. Please remit or explain."

A "Remittance overdue" notification goes to the people who confirm remittances, the custodian, and whoever recorded the cash for them.

Go to **Finance → Cash custody → Overdue remittances** ("Custodians still holding cash not remitted by your organisation's daily cut-off, or held longer than the days allowed. Flags appear only when a cut-off or a holding allowance is set in the cash custody policy."). Filter by **Reason**, **Custodian**, **From day** and **To day**. Each row shows the **Day**, **Custodian**, **Reason**, **Flagged** time and **Cash still held**. Open one with **View details** to see, for a held-too-long flag, **Held since**, **Allowed holding** and the **Oldest unremitted cash received**, or the **Cut-off** for a daily flag. Use **Open custody** to see the custodian's cash.

### 20. Cash reason lists

**Finance → Cash custody → Reason lists** holds your company's reasons for **Variance**, **Write-off**, **Retention** and **Adjustment**. Click **New reason**, choose the **List**, enter a **Label** and **Description (optional)**, and click **Create**. Once a list has entries, people must choose from it; "Without a list, people explain variances, write-offs, retentions and adjustments in free text." A deactivated reason "can no longer be chosen; records that used it keep it."

### 21. Customer hours: payments and credit

When your company sells prepaid customer hours, finance makes the hours usable:

- **Verify the payment.** A payment linked to an hours purchase is verified like any other ([Task 3](#3-verify-or-reject-a-payment)). Once verified, the purchase's hours activate (partly, for a part-payment, if your policy allows). Rejecting a payment reverses hours not yet used.
- **Link a payment to a purchase.** Open the purchase (**Customer hours → Hours purchases**) and click **Allocate payment**. See the [Manager manual, Task 16](02-manager-dispatcher.md#16-record-an-hours-purchase-and-link-its-payment).
- **Activate on credit.** For a customer with an approved credit arrangement, click **Activate on credit** on the purchase, enter the **Hours to activate** and the **Reason**. It is allowed only within the customer's available credit.

You cannot verify a payment you recorded yourself, including one recorded with an hours sale.

### 22. Accountability dashboard

**Overview → Accountability** shows the cash tiles that matter to finance: **Cash per custodian**, **Cash awaiting acknowledgement or confirmation** (including **Remittances overdue today**), **Payments awaiting confirmation**, **Open discrepancies**, **Outstanding approvals** and, when revenue checks are on, **Revenue differences**. Click a line to open the matching list. See the [Tenant Owner manual, Task 14](01-tenant-owner.md#14-accountability-dashboard).

### 23. Deposit accounts

**Finance → Deposit accounts** ("Company accounts remittances are paid into; supervisors pick one when they remit") lists every bank account, mobile-money wallet and cash office of the company. Managing it needs the deposit-account permission (in the example roles, the accountant and the owner).

**Add an account:**

1. Click **New deposit account**.
2. Under **Account**, enter the **Name** ("What supervisors pick when they remit, e.g. "CRDB main".") and choose the **Type** (**Bank account**, **Mobile-money wallet** or **Cash office**) and **Currency**.
3. Under **Details**, enter the **Bank or operator (optional)**, the **Account number (optional)** ("Only the last four characters are kept (shown as •••• 4821).") and a **Note (optional)**.
4. Click **Create account**. *What you'll see:* "<name> added."

**Look after the list:** filter by **Type**, search by name or bank / operator, and tick **Show inactive** to see old accounts. Open an account to see its details, who created it, and **Edit** it ("Leave empty to keep it" for the stored number). When an account is closed, **Deactivate** it with a reason: "New remittances can no longer name this account. Remittances already recorded keep it." You can **Reactivate** it later.

Supervisors' phones receive the active accounts at their next sync. Your company can require every remittance to name an account (**Require the company account the money was paid into**), to give the transaction reference for bank and mobile-money payments, and to include a photo of the deposit slip (see [Task 8](#8-confirm-a-remittance-cash-handover)).

### 24. Revenue differences and the daily machine sheet

When your company switches revenue checks on, Asseta matches each machine's engine hours with the money billed for them. Your role can, by default, read and explain; someone with the decide permission decides. The full steps are in the Tenant Owner manual:

- **Engine hours → Daily machine sheet**: each machine's day, with **Expected**, **Attributed** and **Difference** per currency, and the **Money sources** (invoice lines and prepaid hours used) behind them ([Task 23](01-tenant-owner.md#23-daily-machine-sheet)). Use **Export CSV** to keep a copy.
- **Finance → Revenue differences**: periods where the money attributed fell short of the expected revenue by more than your company's tolerance. Click **Explain**, choose the **Reason**, write **What happened** and click **Propose explanation** ([Task 25](01-tenant-owner.md#25-revenue-differences)). A typical reason is an invoice not yet issued: once it is issued, the money is attributed and an open difference clears by itself (**Cleared (money arrived)**).
- **Engine hours → Non-revenue hours**: explain movement time inside a job ([Task 24](01-tenant-owner.md#24-non-revenue-hours)).

A revenue difference is a difference to explain, not an accusation. You cannot decide your own explanation.

### 25. Customer hours used over days

If your company takes prepaid hours every day, hours used by running jobs show as **In use by running jobs** on the purchase and in **Balances**, and the ledger shows **Used that day (provisional)** entries until the job is completed. A **low-balance warning** ("Hours running low") tells you when a customer should be offered a top-up. Each customer's **Hours statement** (**Operations → Customers** → the customer → **Hours statement**) can be downloaded with **Download PDF** and sent to the customer. See the [Manager manual, Task 25](02-manager-dispatcher.md#25-prepaid-hours-used-over-days).

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
| Remittance | Awaiting confirmation (Claimed) | Recorded; does not reduce custody yet |
| | Confirmed (Verified) | Counted; reduces custody by the amount received |
| | Rejected | Not received; never reduces custody |
| Cash transfer, float acknowledgement | Awaiting acknowledgement / Acknowledged / Disputed | Floats show **Not required** when your policy does not ask for acknowledgement |
| Variance | Open → Write-off proposed → Resolved | Outcomes: Recovered, Corrected error, Written off. Kind: Shortfall or Surplus to explain |
| Overdue remittance | Not remitted by the cut-off / Held longer than allowed | The reason it was flagged |
| Deposit account | Active / Inactive | An inactive account cannot be named on new remittances |
| Revenue difference | To explain → Explanation awaiting decision → Explained; Confirmed (money to recover); Cleared (money arrived) | Someone other than the explainer decides |
| Retention, custody adjustment | Awaiting decision → Approved / Rejected | Only approved ones count |

## Good practice

- **Verify daily.** Supervisors' cash stays "claimed" until you verify it. Late verification makes the reconciliation look worse than reality.
- **Always enter references** (bank transaction ID, mobile-money code, receipt book number). They prevent double entry and help audits.
- **Never edit around a mistake.** Void the invoice or reject the payment, and record it again correctly. Asseta keeps the full trail.
- **Keep different currencies apart.** Asseta never adds TZS and USD together, so check the currency before saving.
- **Export month-end reports** (Reconciliation, Cash custody, Expenses) for your records.
- **Always enter the amount you counted** when confirming a remittance or acknowledging a transfer, even when it differs. A recorded difference is better than a hidden one.
- **Resolve variances with a clear explanation**, and keep at least two people with the write-off permission.
- **Keep the deposit account list current.** Add a new account before supervisors need it, and deactivate closed ones.
- **Check every remittance against the statement**: account, reference and slip photo, then the amount received.
- **Issue invoices promptly.** Uninvoiced work shows as a revenue difference until the money is attributed.

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

**I can't find All supervisors, Handovers or Reconciliation in Hire finance.**
They moved to **Finance → Cash custody** (All custodians, Remittances, Reconciliation).

**"You recorded this transfer; the receiver must answer it."**
Only the receiver, or a recorder on their behalf, may acknowledge a transfer.

**"This tenant requires write-offs to be proposed and then approved by someone else."**
Use **Propose write-off**; a colleague with the write-off permission decides it.

**A figure in the reconciliation looks wrong.**
Click it to see the transactions behind it. Correct a mistake with a custody adjustment ([Task 18](#18-custody-adjustments)), never by editing.

**"Another deposit account already has this name."**
Each deposit account needs its own name. Choose a different one, or reactivate the old account.

**A supervisor cannot choose an account when remitting.**
The account is inactive, holds another currency, or is of another type than the method chosen. Check it in **Finance → Deposit accounts**, then ask the supervisor to sync.

**I can explain a revenue difference but not decide it.**
Deciding needs the decide permission, and you can never decide your own explanation. Ask a colleague who holds it.

**The page says the company is read-only.**
Your company's Asseta subscription is restricted. You can view everything but cannot make changes. Contact your account owner.
