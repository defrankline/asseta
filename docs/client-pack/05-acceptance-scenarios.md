# Acceptance scenarios: demonstration script

This is the script for demonstrating the 13 scenarios in section 9 of your guideline. It runs on a **test company**, never on your live company. Follow the scenarios in order: each one builds on the last.

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

**Why the last-but-one setting.** The system flags a meter that climbs faster than time allows. Because this demonstration compresses a day into minutes, **wait at least 8 minutes between the readings of each job** in scenarios 3 and 6. If a reading still shows **Provisional**, the Manager opens **Risk & review → Exceptions** and records it as **Explained**.

**Meter baseline.** Sign in as the Supervisor on the phone and sync. For EX-01: **Jobs → My machines → EX-01 → Propose meter baseline**, reading 1000.0. Then the Manager approves it in **Engine hours → Meter baselines → Decide**. Repeat for EX-02. Readings need a photo and a GPS position, so do this outdoors.

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

| | Name | Signature | Date |
|---|---|---|---|
| For the company (owner or authorized manager) | | | |
| Witness | | | |
| For the Platform Owner | | | |
