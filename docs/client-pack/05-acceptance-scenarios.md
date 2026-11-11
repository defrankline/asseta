# Acceptance scenarios: demonstration script

This is the script for demonstrating the 13 scenarios in section 9 of your guideline, followed by scenarios 14 to 19 for the petty cash funds. It runs on a **test company**, never on your live company. Follow the scenarios in order: each one builds on the last.

**How to use it.** A named witness from the company ticks each box when the expected result is seen on screen. Tick only what you saw. Sign the page at the end.

**How to read the Device column.**

| Mark | Meaning |
|---|---|
| **PHONE** | Must be done on a real phone (Android or iPhone) with the Asseta Supervisor app |
| **OWNER APP** | Done on a phone with the Asseta Owner app |
| **WEB** | Done in the web console |

Run the scenarios once with an **Android** phone. Then repeat scenario 12 on an **iPhone**, and any others you wish.

The amounts and hours below are examples. The meter steps are small (tenths of an hour) so that the demonstration can be done in one sitting. The arithmetic is the same as for your guideline's 6, 3 and 1 hour example.

## Before the demonstration

The Platform Owner creates the test company. The Owner completes this list and confirms it to the witness.

**People.** Four logins, each used by a different person, and one employee with no login.

| Person | Role | Staff record linked to login |
|---|---|---|
| **Owner** | Tenant Owner | Yes |
| **Manager** | Manager / Dispatcher | Yes |
| **Supervisor** | Supervisor, with a real phone and the app installed | Yes |
| **Accountant** | Accountant / Finance | Yes |
| **Juma** | Staff record only, no login (an operator who holds cash) | Not needed |

**Other records.**

- Two excavators, **EX-01** and **EX-02**, with the Supervisor assigned on each machine's **Staff assignments** tab.
- A rate card for their category at TZS 100,000 per hour.
- Three customers with active contracts: **Customer A**, **Customer B** and **Customer C**.
- A deposit account, **Company bank**, in **Finance → Deposit accounts**.
- At least one reason in each list: **Customer hours → Reason lists**, **Engine hours → Engine-hour reasons** (including a category **Maintenance**), and **Finance → Revenue reasons**.

**Settings in Administration → Policies.**

| Policy | Setting | Value |
|---|---|---|
| Customer hours | **Default billing of new jobs** | Prepaid customer hours |
| Engine hours | **Approved meter baseline before a job starts** | On |
| Engine hours | **Daily report required** | On |
| Cash custody | **Remit the full balance** | On |
| Cash custody | **Require a transaction reference for bank / mobile-money remittances** | On |
| Cash custody | **Require a photo of the deposit slip or payment confirmation** | On |
| Cash custody | **Require the company account the money was paid into** | On |
| Revenue checks | **Revenue checks switched on** | On |
| Revenue checks | **Unexplained hours outside jobs** | Show as value at risk (never in expected revenue) |
| Meter capture | **Max meter hours per elapsed hour** | 5 (for this demonstration only; a live company keeps the standard value) |
| Device sync | **Offline grant** and **Policy snapshot validity** | Leave as they are |
| Petty cash | **Petty cash funds** | On |
| Petty cash | **Keep offline overspends for approval** | On (the default) |

**Why the Meter capture setting.** The system flags a meter that climbs faster than time allows. Because this demonstration compresses a day into minutes, **wait at least 8 minutes between the readings of each job** in scenarios 3 and 6. If a reading still shows **Provisional**, the Manager opens **Risk & review → Exceptions** and records it as **Explained**.

**Meter baseline.** Sign in as the Supervisor on the phone and sync. For EX-01: **Jobs → My machines → EX-01 → Propose meter baseline**, reading 1000.0. Then the Manager approves it in **Engine hours → Meter baselines → Decide**. Repeat for EX-02. Readings need a photo and a GPS position, so do this outdoors.

**Petty cash approver.** For scenario 18, the Owner gives the Manager role the permission "Approve or reject petty cash fundings, top-ups and adjustments (never your own)" in **Administration → Users & roles**, so that two people can approve.

☐ Test company ready, confirmed by the Owner.

---

## Scenario 1: A customer purchases hours, payment is independently confirmed, and the hours become available

| # | Who | Device | Do | Should see | ✓ |
|---|---|---|---|---|---|
| 1 | Supervisor | PHONE | **Money → + → Sell customer hours**. Customer A, machine EX-01, **Hours** 10. **Paid now**, **Cash**, **Amount received** 1,000,000. Save and sync | "Hours become available only after someone else verifies this payment." | ☐ |
| 2 | Manager | WEB | **Customer hours → Hours purchases**. Open the new purchase | A purchase number HP-… Status **Awaiting payment**. Rate from the rate card. **Activated** 0 | ☐ |
| 3 | Accountant | WEB | **Finance → Hire finance → Customer payments**, filter **Claimed (unverified)**. **Verify / reject** this payment, choose verify | "Payment verified." | ☐ |
| 4 | Manager | WEB | Reopen the purchase | Status **Active**. **Activated** 10. The payment shows who recorded it and who verified it | ☐ |
| 5 | Supervisor | WEB | Try to verify the payment | The option is not available to this role | ☐ |

## Scenario 2: A purchase is recorded but payment is not confirmed; the hours must remain inactive

| # | Who | Device | Do | Should see | ✓ |
|---|---|---|---|---|---|
| 1 | Supervisor | PHONE | **Sell customer hours**. Customer B, EX-02, 5 hours, **Paid now**, **Mobile money**, amount 500,000, a reference. Save and sync | Saved | ☐ |
| 2 | Manager | WEB | Open the purchase | Status **Awaiting payment**. **Activated** 0. Awaiting activation 5 | ☐ |
| 3 | Owner | WEB | **Overview → Accountability** | The purchase counts under **Hours awaiting activation** and **Unconfirmed purchases** | ☐ |
| 4 | Manager | WEB | **Operations → Jobs → New job** for Customer B on EX-02. **Billing**: Prepaid customer hours. **Minimum hours** 0. Create, **Submit for approval** | Job created | ☐ |
| 5 | Owner | WEB | Approve the job | Status **Approved** | ☐ |
| 6 | Supervisor | WEB | **Field work → My jobs**, open the job, capture the opening reading 1000.0 (type it and upload a photo of the meter), then **Start job** | Refused: "The customer has no activated hours left on this machine" | ☐ |
| 7 | Manager | WEB | On the purchase, look for a way to activate the hours | There is no such button without a confirmed payment or approved credit | ☐ |
| 8 | Manager | WEB | Cancel the job, so that EX-02 is free | Job **Cancelled** | ☐ |

The purchase stays unconfirmed. Leave it so.

## Scenario 3: A customer uses part of the purchased hours; the system calculates the remaining balance

| # | Who | Device | Do | Should see | ✓ |
|---|---|---|---|---|---|
| 1 | Manager | WEB | Create job **J1**: Customer A, EX-01, **Prepaid customer hours**, **Minimum hours** 0, Supervisor assigned. **Submit for approval** | Job in **Pending approval** | ☐ |
| 2 | Owner | OWNER APP | **More → Approvals → Jobs**. Approve J1 | Job approved | ☐ |
| 3 | Supervisor | PHONE | Sync. **Jobs → Ready to start → J1**. **Capture opening reading**: photograph the meter, value 1000.0, GPS fix, **Save** | Reading saved | ☐ |
| 4 | Supervisor | PHONE | **Start job** | **In progress** | ☐ |
| 5 | Supervisor | PHONE | Wait at least 8 minutes. **Capture closing reading** 1000.6. **Customer acknowledgement**: signature. **Complete job**. Sync | **Completed** | ☐ |
| 6 | Manager | WEB | **Customer hours → Balances**, **By customer**, Customer A | **Activated** 10, **Used** 0.6, **Remaining** 9.4 | ☐ |
| 7 | Manager | WEB | **Customer hours → Prepaid hours used** | J1: **Billable** 0.6, **Covered** 0.6, **Not covered** 0 | ☐ |

## Scenario 4: A customer has multiple purchases; the system keeps the history and balance of each

| # | Who | Device | Do | Should see | ✓ |
|---|---|---|---|---|---|
| 1 | Supervisor | PHONE | **Sell customer hours**. Customer A, EX-01, 5 hours, cash 500,000. Save and sync | Second HP-… number | ☐ |
| 2 | Accountant | WEB | Verify the payment | "Payment verified." | ☐ |
| 3 | Manager | WEB | **Customer hours → Balances**, Customer A | Combined **Remaining** 14.4 | ☐ |
| 4 | Manager | WEB | Open each purchase | First: 9.4 remaining. Second: 5 remaining. Each has its own payment and history | ☐ |
| 5 | Manager | WEB | **Customer hours → Hours ledger**, filter by Customer A | Each movement on its own line against its purchase. The first purchase's activation and use are still there | ☐ |

## Scenario 5: Hours are reassigned to another excavator with approval, preserving the original assignment

| # | Who | Device | Do | Should see | ✓ |
|---|---|---|---|---|---|
| 1 | Manager | WEB | Open the second purchase. **Request transfer**. **To machine** EX-02, **Hours** 2, a reason. **Request transfer** | "Transfer requested; someone else decides it." | ☐ |
| 2 | Manager | WEB | **Customer hours → Transfers**. Look at the request | **Decide** is disabled: "Someone else must decide your own request" | ☐ |
| 3 | Owner | WEB | **Customer hours → Transfers**, **Decide**, **Approve**, **Record decision** | "Transfer of 2 h approved." | ☐ |
| 4 | Manager | WEB | Open the purchase | Its **Machine** is still EX-01. **Transfers between machines** shows the 2 hours, who asked and who approved. Remaining: EX-01 3, EX-02 2 | ☐ |
| 5 | Manager | WEB | **Customer hours → Hours ledger** for this purchase | One entry out of EX-01, one entry in to EX-02 | ☐ |

## Scenario 6: An excavator records operating hours, reconciled against customer and authorized work

| # | Who | Device | Do | Should see | ✓ |
|---|---|---|---|---|---|
| 1 | Manager, Owner | WEB | Create and approve job **J2**: Customer C, EX-01, **Billing**: Invoice after the work | J2 **Approved** | ☐ |
| 2 | Supervisor | PHONE | Sync. On J2: opening reading 1000.6, **Start job**. Wait at least 8 minutes. Closing reading 1000.9, acknowledgement, **Complete job** | **Completed** | ☐ |
| 3 | Supervisor | PHONE | Wait 3 minutes. **Jobs → My machines → EX-01 → Record daily reading** 1001.0 | Saved | ☐ |
| 4 | Supervisor | PHONE | Wait 3 minutes. **Record daily reading** 1001.2. Sync | Saved and synced | ☐ |
| 5 | Manager | WEB | **Engine hours → Hours to explain**. Find the 0.2 hours. **Explain**: **Non-customer activity**, category **Maintenance**, **What happened**, **Propose explanation** | "Explanation proposed; a second person decides it." | ☐ |
| 6 | Owner | WEB | **Engine hours → Hour explanations**, **Decide**, **Approve**, a note, **Record decision** | Approved | ☐ |
| 7 | Manager | WEB | **Engine hours → Work allocations → Per-day reconciliation**, EX-01, today | **Total engine hours** 1.2. **Customer** 0.9. **Authorized** 0.2. **Unexplained** 0.1. **Difference** 0, marked **Reconciled** | ☐ |
| 8 | Manager | WEB | Open the **Ledger** tab | Each entry has its start and end reading, its **Kind**, who it is **For**. J1 shows the purchase it drew on | ☐ |

## Scenario 7: Some engine hours remain unexplained; the system flags them without treating them as wasted or billable

| # | Who | Device | Do | Should see | ✓ |
|---|---|---|---|---|---|
| 1 | Manager | WEB | **Engine hours → Hours to explain** | 0.1 hours on EX-01, **Not yet explained** | ☐ |
| 2 | Manager | WEB | **Customer hours → Balances**, Customer A and Customer C | Nothing has been taken for the 0.1 hours | ☐ |
| 3 | Accountant | WEB | **Operations → Jobs**, open J2, check its billable hours | 0.3 hours. The 0.1 hours is not billed | ☐ |
| 4 | Owner | WEB | **Overview → Accountability**, under **Unexplained engine hours** | EX-01 listed, with a **Value at risk** line "not in expected" | ☐ |
| 5 | Owner | WEB | **Engine hours → Daily machine sheet**, EX-01, today | The value at risk shown apart from expected revenue and the difference | ☐ |
| 6 | Owner | WEB | After the number of days set in **Open an investigation for unexplained hours after** (3 by default), open **Investigations** | An investigation was opened. The hours are **still** not yet explained | ☐ later |

Step 6 cannot be seen in one sitting. Record the date it was checked.

## Scenario 8: An operator hands cash to a manager; custody transfers but the cash is not remitted

| # | Who | Device | Do | Should see | ✓ |
|---|---|---|---|---|---|
| 1 | Supervisor | PHONE | **Money → + → Record cash collection**. Customer C, 300,000. **Cash held by**: Juma. Save and sync | Saved | ☐ |
| 2 | Accountant | WEB | **Finance → Cash custody → All custodians** | Juma holds 300,000 | ☐ |
| 3 | Owner | WEB | **Overview → Accountability**. Note **Outstanding cash balances** and **Confirmed received by the company** | Figures noted | ☐ |
| 4 | Supervisor | PHONE | **Transfer cash to a colleague**. **From** Juma, **To** Manager, **Amount handed over** 300,000. Save and sync | **Awaiting acknowledgement** | ☐ |
| 5 | Accountant | WEB | **All custodians** | Juma still holds it: the cash is in transit | ☐ |
| 6 | Manager | WEB | **Field work → Cash → Transfers**, **Acknowledge / dispute**, **Acknowledge (cash received)**, **Amount actually received** 300,000, **Record answer** | Answer recorded | ☐ |
| 7 | Accountant | WEB | **All custodians** | Juma 0. Manager 300,000 | ☐ |
| 8 | Owner | WEB | **Overview → Accountability** | **Outstanding cash balances** unchanged. **Confirmed received by the company** unchanged | ☐ |

## Scenario 9: A manager declares a bank deposit; the balance does not clear until the company confirms

| # | Who | Device | Do | Should see | ✓ |
|---|---|---|---|---|---|
| 1 | Manager | WEB | **Field work → Cash → Remit cash**. Amount 300,000. **How was it paid?** Bank deposit. **Company account**: Company bank. **Transaction reference**. **Add photo**: a picture of a slip | "Remittance recorded; it is awaiting confirmation until the office counts it." | ☐ |
| 2 | Accountant | WEB | **Finance → Cash custody → Remittances**, **Awaiting confirmation** | Remittance RMT-… Declared 300,000. Evidence status **Supported**. Reference and photo available | ☐ |
| 3 | Accountant | WEB | **All custodians** | Manager's outstanding is still 300,000 | ☐ |
| 4 | Manager | WEB | Try to confirm the remittance | The option is not available to this role | ☐ |

## Scenario 10: A remittance is partially confirmed; only the confirmed amount reduces the balance

| # | Who | Device | Do | Should see | ✓ |
|---|---|---|---|---|---|
| 1 | Accountant | WEB | On the remittance: **Confirm / reject**. **Confirm (cash counted)**, **Amount received** 250,000, **Record decision** | "Remittance confirmed." | ☐ |
| 2 | Accountant | WEB | **All custodians** | Manager's outstanding is 50,000 | ☐ |
| 3 | Accountant | WEB | **Remittances**, **Confirmed** | Declared 300,000. Received 250,000. Evidence status **Confirmed** | ☐ |
| 4 | Accountant | WEB | **Cash custody → Variances** | One open variance of 50,000, **Shortfall**, naming the Manager as accountable | ☐ |
| 5 | Owner | OWNER APP | **More → Accountability**, Cash accountability | **Confirmed by the company** up by 250,000; 50,000 still outstanding | ☐ |

The Owner app can also confirm a remittance (**More → Approvals → Cash handovers**). Use a second remittance if you want to see it.

## Scenario 11: An adjustment is made; the original remains visible and the approval history is retained

| # | Who | Device | Do | Should see | ✓ |
|---|---|---|---|---|---|
| 1 | Manager | WEB | Note the first purchase's remaining hours (9.4). On that purchase choose **Correct hours**. **Change**: Take hours off, **Hours** 1, **Machine** EX-01, a reason, an evidence picture. **Propose correction** | Request created, status **Awaiting decision**. A forecast shows what would change. The balance has not changed | ☐ |
| 2 | Manager | WEB | Open the request and look for a way to decide it | No way to decide it: the role cannot decide adjustments, and nobody can decide their own | ☐ |
| 3 | Accountant | WEB | **Finance → Adjustments ledger → Adjustment requests**, **Decide**, **Approve** | Approved | ☐ |
| 4 | Manager | WEB | **Customer hours → Hours ledger** for this purchase | A new correction line. All earlier lines are still there | ☐ |
| 5 | Owner | WEB | **Finance → Adjustments ledger**, open the entry | **Original value**, **New value**, **Resulting balance** 8.4, the reason, the evidence, who requested and who approved, with times | ☐ |
| 6 | Owner | WEB | **Administration → Audit log** | The request and the decision are listed | ☐ |

## Scenario 12: Transactions are entered offline and synchronized without duplication or loss

**This scenario must be done on real phones. Do it on an Android phone and on an iPhone.**

| # | Who | Device | Do | Should see | ✓ |
|---|---|---|---|---|---|
| 0 | Manager, Owner, Supervisor | WEB, PHONE | Before going offline: create and approve job **J3** for Customer C on EX-02 (**Billing**: Invoice after the work). The Supervisor syncs, so that J3 is on the phone under **Ready to start** | J3 on the phone | ☐ |
| 1 | Supervisor | PHONE | Note the time. Switch on **airplane mode** | Banner: "Offline. You can keep working; everything is saved on this phone and syncs when you are back online." | ☐ |
| 2 | Supervisor | PHONE | **Record daily reading** on EX-02 (reading a little above the last, with a photo) | Saved. Shown as **Waiting to sync** | ☐ |
| 3 | Supervisor | PHONE | **Sell customer hours**: Customer C, EX-02, 3 hours, cash 300,000 | Saved | ☐ |
| 4 | Supervisor | PHONE | **Record cash collection**: Customer C, 100,000 | Saved | ☐ |
| 5 | Supervisor | PHONE | **Hand over cash**: 100,000. **How was it handed over?** Bank deposit. **Paid into** Company bank. **Transaction reference**. **Photograph the slip**. Because this is less than the Supervisor holds, fill in **Why part of the cash stays** | Saved. Waits for its photo | ☐ |
| 6 | Manager | WEB | Look for those four records | None has arrived | ☐ |
| 7 | Supervisor | PHONE | Fully close the app and reopen it, still in airplane mode | All four records are still there. **Sync status** shows them under **Not yet synced** | ☐ |
| 8 | Manager | WEB | While the phone is offline, cancel J3 | J3 **Cancelled** | ☐ |
| 9 | Supervisor | PHONE | Still offline: on J3, capture an opening reading and tap **Start job** | Saved on the phone, which does not yet know J3 was cancelled | ☐ |
| 10 | Supervisor | PHONE | Switch off airplane mode. On **Sync status**, tap **Sync now**. While it is sending, switch airplane mode on briefly, then off again, and tap **Sync now** again | Finishes. The four records are **Synced**. J3's reading and start appear under **Needs attention: conflicts** | ☐ |
| 11 | Manager | WEB | Open the hours purchase | Exactly **one** new purchase. **Recorded on the phone at** shows the offline time | ☐ |
| 12 | Accountant | WEB | **Cash custody → Remittances** and **Customer payments** | Exactly **one** handover and **one** collection | ☐ |
| 13 | Manager | WEB | Open the reading | **Device time**, **Server receive time** and **Clock difference**. One reading only | ☐ |
| 14 | Supervisor | PHONE | Tap **Sync now** again | No change | ☐ |
| 15 | Manager | WEB | **Risk & review → Sync conflicts**. Open J3's start | **Why not applied**, **Recorded on device**, **Received**, what the device sent | ☐ |
| 16 | Owner | WEB | **Resolve**, **Dismiss**, a reason, **Record outcome** | "Outcome recorded." | ☐ |

**Optional, needs two phones.** With two Supervisor logins and both phones offline, complete two prepaid jobs on the same machine using more hours than remain. After both sync, the second job gets what is left and the rest is flagged **Hours beyond purchase**.

## Scenario 13: Management can trace a customer-hour balance, an excavator-hour balance and a cash balance to the underlying transactions

| # | Who | Device | Do | Should see | ✓ |
|---|---|---|---|---|---|
| | | | **Customer hours** | | |
| 1 | Owner | WEB | **Overview → Accountability**, click **Hours remaining** | Opens the balances | ☐ |
| 2 | Owner | WEB | Customer A: **Hours statement** | Opening, bought, activated, used by job, moved, closing | ☐ |
| 3 | Owner | WEB | Open the first purchase, **Open the hours ledger**. Open J1's used-hours line, then the job | Job J1 with both readings, photos and the customer's signature | ☐ |
| 4 | Owner | WEB | From the purchase, open the payment | Who recorded it, who verified it, when | ☐ |
| | | | **Excavator hours** | | |
| 5 | Owner | WEB | **Engine hours → Reconciliation**, EX-01 | Every interval from the baseline: **From**, **To**, **Hours**, breakdown | ☐ |
| 6 | Owner | WEB | Open a reading from the timeline | Photo, GPS, **Device time**, **Server receive time** | ☐ |
| | | | **Cash** | | |
| 7 | Owner | WEB | **Finance → Cash custody → Reconciliation**, the Manager, today | Transfers received 300,000; confirmed remittance 250,000; outstanding 50,000 | ☐ |
| 8 | Owner | WEB | Click the transfer figure | The transaction behind it, with the record link | ☐ |
| | | | **Any record, any person** | | |
| 9 | Owner | WEB | Copy the RMT- number. Paste it into **Find a reference** at the top of the page | One result, with who recorded it, who decided it, the amount and balance | ☐ |
| 10 | Owner | OWNER APP | **More → Find a reference**, same number | Same result | ☐ |
| 11 | Owner | WEB | **Operations → Staff**, open the Manager, **Accountability** | Cash held now, transfers in, remittances, adjustments requested | ☐ |
| 12 | Owner | WEB | **Administration → Balance verification**, **Verify now** | The run lists **Balances checked**. **Differences** 0 (any difference is a finding to raise and record) | ☐ |

The final test in your guideline is to select any customer, excavator, employee or transaction and establish what happened, when, who was responsible and what remains. **The witness should pick one of each at random and ask for it to be traced.**

☐ Customer traced   ☐ Excavator traced   ☐ Employee traced   ☐ Transaction traced

## Scenario 14: A petty cash fund is funded, acknowledged, spent from with receipts, topped up, and its statement balances

| # | Who | Device | Do | Should see | ✓ |
|---|---|---|---|---|---|
| 1 | Manager | WEB | **Finance → Petty cash → New fund**. **Code** PC-SITE, **Name** Site petty cash, **Holder** the Supervisor, **Approved limit** 200,000, **Low-balance level** 50,000. **Create fund** | "Site petty cash created." The fund page shows **Balance** 0 | ☐ |
| 2 | Accountant | WEB | On the fund: **Propose funding or top-up**. **Kind** Funding, **Amount** 200,000. **Propose** | "Funding PC-… sent for approval." Status **Waiting for approval** | ☐ |
| 3 | Owner | OWNER APP | **More → Approvals → Petty cash to approve**. Open the funding, tap **Approve** | "Request approved." | ☐ |
| 4 | Accountant | WEB | **Fundings & top-ups**, the funding: **Hand over the money**. **How** Cash at the office. **Record hand-over** | "PC-… handed over; the holder confirms what they received." On the fund: **Balance** 0, **Handed over, not yet acknowledged** 200,000 | ☐ |
| 5 | Supervisor | PHONE | Sync. **Money → My petty cash**. Under **Waiting for you**, open the funding. **Amount received** 200,000, **Acknowledge**. Sync | The fund shows **Balance** 200,000, **Available to spend** 200,000 | ☐ |
| 6 | Supervisor | PHONE | **Money → + → Record expense**. **Paid from** Petty cash, **Fund** PC-SITE, amount 30,000, a receipt photo. Save. Then a second expense of 20,000 the same way. Sync | Both saved and synced | ☐ |
| 7 | Owner | WEB | If either expense waits for approval (above the auto-approval limit), approve it in **Finance → Expense approvals** | Both expenses **Approved** | ☐ |
| 8 | Accountant | WEB | **Finance → Expenses & fuel**. **Paid from** Petty cash fund, **Petty cash fund** PC-SITE | The two expenses with their receipts. The funding is not listed as an expense | ☐ |
| 9 | Supervisor | PHONE | Sync. On the fund: **Request a top-up**, leave **Amount (optional)** empty, **Send request**. Sync | Fund **Balance** 150,000 | ☐ |
| 10 | Owner | WEB | **Finance → Expense approvals → Petty cash**. Open the top-up | **Suggested** 50,000. **Spending behind this top-up** lists the two expenses | ☐ |
| 11 | Owner | WEB | **Approve / reject**, approve | "PC-… approved; it can be handed over." | ☐ |
| 12 | Accountant, Supervisor | WEB, PHONE | Accountant: **Hand over the money**. Supervisor: sync, acknowledge 50,000, sync | Fund **Balance** 200,000 | ☐ |
| 13 | Owner | WEB | Fund page, **Statement** for this month | Lines: **Fundings and top-ups received** 200,000 in; **Approved spending** 30,000 and 20,000 out; **Fundings and top-ups received** 50,000 in. **Closing balance** 200,000, the same as **Balance** | ☐ |
| 14 | Owner | WEB | **Export**, **Petty cash fund statement (PDF)** | The same lines and running balance | ☐ |
| 15 | Owner | WEB | **Overview → Dashboard**, the TZS money card | **Petty cash held** 200,000, shown apart from the cash with supervisors | ☐ |

## Scenario 15: A count finds a shortage that is explained or written off, and the fund balance follows

| # | Who | Device | Do | Should see | ✓ |
|---|---|---|---|---|---|
| 1 | Supervisor | PHONE | Sync. On PC-SITE: **Record a count**. **Cash counted** 190,000 (10,000 less than available). Save and sync | Saved and synced | ☐ |
| 2 | Manager | WEB | **Finance → Petty cash → Counts**. Open the count | **Cash expected** 200,000, **Cash counted** 190,000, **Difference** −10,000, a **Variance** link | ☐ |
| 3 | Accountant | WEB | **Finance → Petty cash → Differences** (or the fund page's **Differences**) | One open variance, **Shortfall** 10,000. The fund **Balance** is still 200,000 | ☐ |
| 4 | Accountant | WEB | **Assign** it to yourself, **Explain** it ("Explanation saved.") | The history shows each step | ☐ |
| | | | **Either: written off** | | |
| 5a | Accountant | WEB | **Propose write-off**, a reason, an explanation | "Write-off proposed; someone else with the write-off permission decides." | ☐ |
| 6a | Owner | WEB | **Approve / reject write-off**, **Approve**, **Record decision** | Variance **Resolved**, written off | ☐ |
| 7a | Owner | WEB | Fund page | **Written-off differences** 10,000. **Balance** 190,000. The statement shows a **Written-off differences** line of 10,000 out | ☐ |
| | | | **Or: explained** | | |
| 5b | Supervisor | PHONE | The shortage was a purchase never recorded: **Record expense**, **Paid from** Petty cash, 10,000, its receipt. Sync. (Approve it in **Expense approvals** if it waits) | Expense **Approved**. Fund **Balance** 190,000 | ☐ |
| 6b | Accountant, Owner | WEB | Accountant: **Propose closure**, **Outcome** Corrected error, an explanation. Owner: **Decide closure**, approve | Variance **Resolved**. Nothing written off | ☐ |
| | | | **Both ways** | | |
| 8 | Supervisor | PHONE | Sync. **Record a count**, **Cash counted** 190,000. Save and sync | The count's **Difference** is 0 and no variance opens | ☐ |

## Scenario 16: An expense recorded offline above the available amount is kept for approval and flagged

| # | Who | Device | Do | Should see | ✓ |
|---|---|---|---|---|---|
| 1 | Supervisor | PHONE | Sync. Note PC-SITE's **Available to spend** (190,000 after scenario 15). Switch on **airplane mode** | Offline banner | ☐ |
| 2 | Supervisor | PHONE | **Record expense**, **Paid from** Petty cash, **Fund** PC-SITE, amount 200,000, a receipt photo | Before saving: "Above what the fund has available (…): it is kept for approval and marked for the approver to check." Save works | ☐ |
| 3 | Supervisor | PHONE | Switch off airplane mode, **Sync now** | The expense is **Synced**, not refused | ☐ |
| 4 | Manager | WEB | **Finance → Expenses & fuel**, open the expense | **Pending approval**, even if the amount were within the auto-approval limit. **To look at**: More than the fund had available. "For the approver to look at: …" | ☐ |
| 5 | Owner | WEB | Fund page | **Balance** unchanged at 190,000. **Spending waiting for approval** 200,000 | ☐ |
| 6 | Owner | OWNER APP | **More → Field spend**, the expense | **To check**: Recorded above what the fund had available | ☐ |
| 7 | Owner | WEB | **Finance → Expense approvals**, reject it with a note | Rejected. Fund **Spending waiting for approval** back to 0; **Balance** 190,000. The expense stays on record as **Rejected** | ☐ |
| 8 | Supervisor | WEB | **Field work → Petty cash → Record an expense** on PC-SITE, amount 200,000 | Refused: "The fund has TZS … available". Online, it is never accepted | ☐ |

## Scenario 17: With spending from collections switched off, an expense paid from collected cash is refused

| # | Who | Device | Do | Should see | ✓ |
|---|---|---|---|---|---|
| 1 | Owner | WEB | **Administration → Policies**, **Cash custody**, **New override**. Turn on **Staff may spend from cash collected from customers** and set it off. A reason, **Create version** | A new version in the **Version history** | ☐ |
| 2 | Accountant | WEB | **Finance → Cash custody → All custodians**. Note the Supervisor's outstanding cash | Figure noted | ☐ |
| 3 | Supervisor | WEB | **Field work → Expenses → Submit expense**. **Paid from** Supervisor cash custody, amount 5,000. Submit | Refused: "This company does not allow spending from cash collected from customers; pay from a petty cash fund or by the office" | ☐ |
| 4 | Supervisor | PHONE | Sync. **Record expense**, **Paid from** My cash, 5,000, a receipt. Save and sync | Synced | ☐ |
| 5 | Manager | WEB | **Finance → Expenses & fuel**, open it | **Pending approval**, never approved automatically. **To look at**: Paid from collected cash | ☐ |
| 6 | Accountant | WEB | **All custodians** | The Supervisor's outstanding cash is unchanged | ☐ |
| 7 | Owner | WEB | Reject the expense in **Finance → Expense approvals** | Rejected. Outstanding cash still unchanged | ☐ |

Leave the setting as your company has decided after the demonstration.

## Scenario 18: The person who proposes a funding or top-up cannot approve it

| # | Who | Device | Do | Should see | ✓ |
|---|---|---|---|---|---|
| 1 | Owner | WEB | On PC-SITE: **Propose funding or top-up**. **Kind** Funding, **Amount** 10,000. **Propose** | "Funding PC-… sent for approval." | ☐ |
| 2 | Owner | WEB | **Finance → Expense approvals → Petty cash**. Find the funding | No **Approve / reject** for it: the proposer never decides their own proposal | ☐ |
| 3 | Owner | OWNER APP | **More → Approvals → Petty cash to approve**, open it | "You proposed this, so someone else must approve or reject it." No buttons | ☐ |
| 4 | Accountant | WEB | **Finance → Petty cash → Fundings & top-ups**, open the funding | No **Approve / reject**: the role proposes but does not approve | ☐ |
| 5 | Manager | WEB | **Finance → Expense approvals → Petty cash**, **Approve / reject**, approve | "PC-… approved; it can be handed over." | ☐ |
| 6 | Owner | WEB | Open the funding | **Proposed** by the Owner and **Approved** by the Manager, with times | ☐ |
| 7 | Accountant, Supervisor | WEB, PHONE | Hand it over; the Supervisor acknowledges it | Fund **Balance** 200,000 | ☐ |

## Scenario 19: An advance handed out offline is recorded once, spent against with a receipt, and cleared with change

| # | Who | Device | Do | Should see | ✓ |
|---|---|---|---|---|---|
| 1 | Owner | WEB | **Administration → Policies**, **Petty cash**, **New override**. Turn on **Cash advances**. A reason, **Create version** | A new version in the **Version history** | ☐ |
| 2 | Supervisor | PHONE | Sync. Note PC-SITE's **Balance** (200,000 after scenario 18). Switch on **airplane mode** | Offline banner | ☐ |
| 3 | Supervisor | PHONE | On PC-SITE: **Give an advance**. Recipient **Juma**, **Amount** 20,000, purpose "Diesel at the quarry". Save | Saved. Listed under **Recorded on this phone** as **Waiting to sync** | ☐ |
| 4 | Supervisor | PHONE | Switch off airplane mode, **Sync now**. Then tap **Sync now** again | **Synced**. Under **Advances**: "Given to Juma", 20,000. The second sync changes nothing | ☐ |
| 5 | Accountant | WEB | **Finance → Petty cash → Advances** | Exactly **one** advance PC-… to Juma, 20,000, **Not cleared yet**. The fund **Balance** is 180,000 | ☐ |
| 6 | Supervisor | PHONE | **Record expense**, **Paid from** Petty cash, **Fund** PC-SITE, **Advance** Juma's advance, amount 15,000, a receipt photo. Save and sync. (Approve it in **Expense approvals** if it waits) | Expense **Approved**. The advance shows **Remaining** 5,000. The fund **Balance** is still 180,000: the spending is not taken twice | ☐ |
| 7 | Supervisor | PHONE | Tap the advance, **Clear an advance**. **Change handed back** 5,000, **Clear advance**. Sync | Advance **Cleared** | ☐ |
| 8 | Owner | WEB | Fund page and **Statement** | **Balance** 185,000: the 15,000 spent is the only cost. No difference opened | ☐ |

Leave **Cash advances** as your company has decided after the demonstration.

---

## Acceptance record

| Scenario | Accepted | Comments or exceptions |
|---|---|---|
| 1 Purchase with confirmed payment | ☐ | |
| 2 Unconfirmed purchase stays inactive | ☐ | |
| 3 Partial use, remaining balance | ☐ | |
| 4 Multiple purchases | ☐ | |
| 5 Reassignment with approval | ☐ | |
| 6 Engine hours reconciled | ☐ | |
| 7 Unexplained hours flagged | ☐ | |
| 8 Custody transfer is not a remittance | ☐ | |
| 9 Bank deposit needs company confirmation | ☐ | |
| 10 Partial confirmation | ☐ | |
| 11 Adjustment keeps the original | ☐ | |
| 12 Offline without duplication or loss (Android) | ☐ | |
| 12 Offline without duplication or loss (iPhone) | ☐ | |
| 13 Trace to underlying transactions | ☐ | |
| 14 Petty cash funded, spent and topped up; statement balances | ☐ | |
| 15 Count shortage explained or written off | ☐ | |
| 16 Offline overspend kept for approval and flagged | ☐ | |
| 17 Spending from collected cash refused | ☐ | |
| 18 Proposer cannot approve their own funding | ☐ | |
| 19 Advance given offline recorded once and cleared | ☐ | |

| | Name | Signature | Date |
|---|---|---|---|
| For the company (owner or authorized manager) | | | |
| Witness | | | |
| For the Platform Owner | | | |
