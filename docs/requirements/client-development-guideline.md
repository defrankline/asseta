# Client developer implementation guideline: Excavator Operational Accountability System

> Source: "Development Guideline.pdf" from the founding tenant (Mzalendo Investment Ltd), received 2026-11-08. Text extracted verbatim from the PDF. It extends `client-accountability-requirements.md` and governs scope with it (DEC-032).

```text
MZALENDO INVESTMENT LTD
EXCAVATOR OPERATIONAL ACCOUNTABILITY SYSTEM
DEVELOPER IMPLEMENTATION GUIDELINE

Document Purpose: To guide the design, development, implementation and testing of a
digital system that controls customer hours, excavator operations and company cash.

1. PURPOSE OF THE SYSTEM
Mzalendo Investment Ltd operates an excavator rental business. The machines normally
operate at remote sites where management is not physically present, and internet
connectivity is unavailable.
The Company needs a system that provides reliable accountability for three things:
   1. Customer hours: Every hour purchased by a customer must be recorded, activated,
      consumed and accounted for.

   2. Excavator operating hours: Every hour recorded by an excavator's hour meter must
      be accounted for.

   3. Company money: Every amount collected must be traceable from the customer to
      the person holding the money and ultimately to the Company's confirmed receipt.
The system must prevent revenue leakage, unauthorized transactions, manipulation of
records and unexplained differences.
The guiding principle is:
EVERY CUSTOMER HOUR, EVERY EXCAVATOR OPERATING HOUR AND EVERY AMOUNT OF
MONEY MUST HAVE A TRACEABLE RECORD.

2. GENERAL SYSTEM REQUIREMENTS
The system must:
   •   Be accessible to authorized management and field personnel according to their
       assigned roles.
   •   Work offline at remote operating sites.
   •   Synchronize records when internet connectivity becomes available.
   •   Maintain a complete history of transactions and changes.
   •   Automatically calculate balances and identify discrepancies.
   •   Require authorization for exceptional transactions and adjustments.
   •   Provide management with real-time information whenever synchronized data is
       available.
IMPORTANT: THE SYSTEM MUST BE DESIGNED AROUND CONTROLLED RECORDS AND
LEDGERS, NOT MERELY DATA-ENTRY FORMS.

3. THE THREE MAIN ACCOUNTABILITY AREAS

3.1. CUSTOMER HOURS ACCOUNTABILITY
The system must maintain a separate account of hours purchased by every customer.
The following information must be recorded for each purchase:
   •   Customer name or identification.
   •   Transaction reference number.
   •   Date of purchase.
   •   Number of hours purchased.
   •   Excavator originally assigned.
   •   Applicable hourly rate.
   •   Any approved discount.
   •   Total amount payable.
   •   Payment method.
   •   Payment confirmation status.
   •   Person who recorded the transaction.
   •   Person who confirmed payment.
   •   Remaining customer hours.
Walk-in customers must also be accommodated. The system must not force every customer
to complete a lengthy registration process before purchasing hours.

Mandatory customer-hour controls
   1. Pricing control: Hourly rates must be centrally controlled. Field personnel must not
      freely change prices.
   2. Discount control: Customer-specific discounts must be predefined and authorized.
      The system must automatically apply the applicable discount.
   3. Payment confirmation: Recording that a customer has paid is not sufficient. Hours
      must only be activated after independent payment confirmation or approval of an
      authorized credit transaction.
   4. Separate purchase and payment records: The system must distinguish between a sale,
      a payment claim and confirmed receipt of payment.
   5. Excavator assignment: Every purchased batch of hours must have an original excavator
      assignment.
   6. Reassignment: Hours may be transferred to another excavator only when properly
      authorized. The original assignment must remain visible in the transaction history.
   7. No unauthorized activation: Field personnel must not be able to activate unpaid hours
      or bypass payment confirmation.
   8. No silent balance changes: Customer balances must only change through recorded
      transactions.
3.2. EXCAVATOR OPERATING-HOUR ACCOUNTABILITY
The system must account for every hour recorded by each excavator's hour meter.
Each excavator must have its own operational record.
The following information must be recorded:
   •   Excavator identification.
   •   Date of report.
   •   Initial hour-meter reading.
   •   Final hour-meter reading.
   •   Total operating hours.
   •   Billable hours.
   •   Unbillable hours.
   •   Reason for unbillable hours.
   •   Customer or work allocation.
   •   Supporting evidence where required.
   •   Person submitting the report.

Mandatory meter controls
   1. Every excavator must have a verified initial meter reading (baseline) before being
      placed under system monitoring.
   2. The system must calculate total operating hours automatically:

Total Operating Hours = Final Meter Reading − Initial Meter Reading
   3. Every recorded engine hour must be accounted for through a valid work allocation or
      an identified exception.
   4. The system must not automatically assume that unexplained hours are wasted hours
      or legitimate working hours.
   5. Unexplained hours must remain visible as unexplained until investigated and resolved
      through an authorized process.
   6. The Company must define an investigation threshold. Once an unexplained balance
      exceeds the permitted age or threshold, the system must flag it for management
      attention.
   7. Meter readings must not be changed or deleted without authorization and a recorded
      reason.
   8. The system must identify unusual readings, including decreasing readings, duplicate
      reports, excessive changes and possible meter resets.
   9. Photographs of the hour meter or dashboard should be captured as supporting
      evidence.
   10. Where automatic machine-hour data collection is introduced, it should be integrated
       without interfering with the excavator's original safety and control systems.

3.3. CASH COLLECTION AND ACCOUNTABILITY
The system must track money collected from customers and establish who is responsible for
holding it at every stage.
It must distinguish between:
   •   Money collected from customers.
   •   Money held by an operator or field employee.
   •   Money transferred from one employee to another.
   •   Money actually remitted to the Company.
   •   Money independently confirmed as received by the Company.
Mandatory cash controls
   1. Every cash collection must be recorded against the relevant customer and transaction.
   2. Every cash collection must identify the person who received the money.
   3. The system must calculate the expected cash balance held by each responsible person.
   4. Transferring cash from an operator to a manager is a cash custody transfer, not a
      company remittance.
   5. A custody transfer must be acknowledged by the receiving person.
   6. Remitting money to the Company must be recorded as a separate transaction.
   7. A remittance must not be treated as completed merely because a field employee
      claims to have deposited or handed over the money.
   8. The Company must independently acknowledge the amount actually received. For
      bank deposits, appropriate bank evidence must be recorded.
   9. By default, the entire accountable cash balance must be remitted. Any partial
      remittance or authorized cash retention must have an approved reason.
   10. Direct payments made by customers into the Company's bank account must be
       recorded separately and must not be treated as cash held by field personnel.

4. THE REQUIRED SYSTEM LEDGERS
The following ledgers are mandatory. They are the foundation of the system and must be
maintained independently, even if the developer presents them through combined screens or
reports.
4.1. LEDGER 1: CUSTOMER HOURS LEDGER
Purpose: To establish how many hours each customer has purchased, used and has
remaining.
Each purchase must create a separate transaction or hours lot.
Required records:
   •   Customer.
   •   Purchase reference.
   •   Purchase date.
   •   Original excavator assignment.
   •   Hours purchased.
   •   Payment status.
   •   Activation date.
   •   Hours consumed.
   •   Authorized adjustments.
   •   Remaining hours.
Calculation:
Opening Hours Balance
   •   New Hours Purchased and Activated
       − Hours Consumed
       ± Authorized Adjustments
       = Closing Hours Balance
The system must preserve the history of each purchase. It must not simply overwrite a
customer's previous balance.
The system must also show the remaining hours for each individual purchase lot, not only
the customer's combined balance.
Critical rule: Hours cannot be consumed before activation, except under an explicitly
authorized credit arrangement.

4.2. LEDGER 2: EXCAVATOR ENGINE-HOUR LEDGER
Purpose: To account for every hour recorded by each excavator.
Required records:
   •   Excavator identification.
   •   Reporting date.
   •   Opening meter reading.
   •   Closing meter reading.
   •   Total engine hours.
   •   Hours allocated to customers.
   •   Other authorized operating hours.
   •   Unexplained hours.
   •   Adjustment records.
   •   Supporting evidence.
Calculation:
Closing Meter Reading − Opening Meter Reading = Total Engine Hours
Total Engine Hours must be reconciled against:
   •   Customer work hours.
   •   Other authorized operating hours.
   •   Unexplained hours.
The system must display the reconciliation difference.
Critical rule: No engine hour should disappear from the system. Unexplained hours must
remain visible until resolved.

4.3. LEDGER 3: WORK EXECUTION ALLOCATION LEDGER
Purpose: To connect actual excavator operating hours to the customer or authorized activity
responsible for those hours.
This ledger is particularly important because recording that an excavator operated does not
automatically establish which customer received the service.
Each allocation must contain:
   •   Excavator identification.
   •   Customer or authorized activity.
   •   Work date.
   •   Starting meter reading.
   •   Ending meter reading.
   •   Hours allocated.
   •   Relevant customer purchase reference or hours lot.
   •   Person who recorded the allocation.
   •   Approval, where required.
   •   Supporting evidence.
The system must prevent the same engine hours from being allocated more than once.
Example:
An excavator records 10 engine hours in one working day:

Allocation          Hours

Customer A          6

Customer B          3

Unexplained hours 1
Total               10

The system must reconcile the allocations against the 10 actual engine hours.
If an allocation is changed, the original record must remain available in the audit history.

4.4. LEDGER 4: CASH COLLECTION AND CUSTODY LEDGER
Purpose: To establish how much money has been collected and who is currently responsible
for it.
The ledger must record:
   •    Collection reference.
   •    Customer.
   •    Amount collected.
   •    Date and time.
   •    Payment method.
   •    Person who collected the money.
   •    Related customer purchase.
   •    Current cash custodian.
   •    Supporting evidence.
For each cash custodian, the system must calculate:
Opening Cash Balance
   •    New Cash Collections
   •    Cash Received from Other Custodians
        − Cash Transferred to Other Custodians
        − Cash Remitted and Confirmed by Company
        = Closing Accountable Cash Balance
The system must show the cash balance held by each person separately.
Critical rule: A transfer between two field employees must not reduce the Company's total
outstanding cash. It only changes the person responsible for holding that cash.

4.5. LEDGER 5: COMPANY CASH REMITTANCE LEDGER
Purpose: To establish how much money has actually reached the Company.
Required records:
   •   Remittance reference.
   •   Person making the remittance.
   •   Amount declared.
   •   Date of remittance.
   •   Payment method.
   •   Bank deposit or transfer reference, where applicable.
   •   Supporting evidence.
   •   Amount independently confirmed by the Company.
   •   Person who confirmed receipt.
   •   Confirmation date.
   •   Outstanding difference, if any.
The system must distinguish between:
   1. Remittance declared by the field employee.
   2. Remittance supported by evidence.
   3. Remittance independently confirmed by the Company.
Only the amount confirmed as received by the Company may reduce the field employee's
accountable cash balance.
Any difference must remain outstanding and visible for investigation.

4.6. LEDGER 6: ADJUSTMENTS AND EXCEPTIONS LEDGER
Purpose: To control all activities that change an otherwise established customer, operational
or financial balance.
Examples include:
   •   Customer-hour corrections.
   •   Approved refunds.
   •   Customer-hour reassignment.
   •   Meter-reading corrections.
   •   Approved unbillable hours.
   •   Cash shortages or overages.
   •   Reversal of incorrect transactions.
   •   Authorized credit arrangements.
Every adjustment must record:
   •   Original transaction reference.
   •   Type of adjustment.
   •   Original value.
   •   New value or adjustment amount.
   •   Reason.
   •   Supporting evidence.
   •   Person requesting the adjustment.
   •   Person approving the adjustment.
   •   Date and time.
   •   Resulting balance.
Critical rule: No user must be able to silently edit or delete a posted transaction. Corrections
must be made through authorized adjustment or reversal records.

5. REQUIRED OPERATIONAL WORKFLOWS
The developer must implement the following workflows.
T1. Customer Hours Purchase / Sale
   •   Record the customer and purchase.
   •   Apply the centrally controlled hourly rate.
   •   Apply any authorized customer discount.
   •   Generate a unique transaction reference.
   •   Assign the hours to an excavator.
   •   Record the payment method and payment status.

T2. Payment Confirmation and Hours Activation
   •   Record payment evidence or payment claim.
   •   Route the transaction for independent confirmation.
   •   Activate the purchased hours only after confirmation.
   •   Allow credit activation only where specifically authorized.
   •   Record who confirmed or authorized activation.

T3. Site and Meter Verification
   •   Record the excavator's meter reading.
   •   Capture dashboard or meter photographs.
   •   Verify the opening and closing readings.
   •   Identify unusual readings and inconsistencies.
   •   Maintain a traceable meter history.

T4. Work Execution Allocation
   •   Record the actual work performed.
   •   Allocate engine hours to the relevant customer or authorized activity.
   •   Link the allocation to the customer's activated hours.
   •   Reconcile total allocations against actual engine hours.
   •   Flag unexplained hours.

T5. Cash Custody Transfer
   •   Record the amount being transferred.
   •   Identify the person handing over the cash.
   •   Identify the person receiving the cash.
   •   Require acknowledgement by the receiving person.
   •   Transfer accountability without recording a company remittance.

T6. Cash Remittance to Company
   •   Record the amount declared for remittance.
   •   Capture deposit or handover evidence.
   •   Require independent Company confirmation.
   •   Reconcile the declared amount against the amount received.
   •   Update the responsible person's cash balance only for the confirmed amount.
T7. Operational and Financial Adjustments
   •   Allow authorized users to request adjustments.
   •   Require a reason and supporting evidence.
   •   Require approval from an authorized person.
   •   Preserve the original transaction.
   •   Record the adjustment separately.

T8. Variance Investigation and Resolution
   •   Identify differences in customer hours, engine hours and cash balances.
   •   Assign the variance for investigation.
   •   Record the explanation and supporting evidence.
   •   Require authorized approval before closure.
   •   Preserve the investigation and resolution history.

6. SYSTEM SECURITY AND MANAGEMENT CONTROLS
The developer must implement role-based access. Users must only perform activities
permitted by their responsibilities.
At a minimum, the system should distinguish:
   •   Administrator: Manages system configuration and user access.
   •   Management: Reviews operations, approves exceptions and monitors accountability.
   •   Field Manager: Records and manages authorized field transactions and cash custody.
   •   Operator: Submits operational information and meter readings.
   •   Finance / Cashier: Independently confirms company receipts and performs financial
       reconciliation.
The same person should not be able to initiate and independently approve the same
sensitive transaction.
The system must also:
   1. Maintain a permanent audit history of important activities.
   2. Record who performed each activity and when.
   3. Prevent unauthorized deletion or modification of posted records.
   4. Generate unique references for transactions.
   5. Prevent duplicate submissions, especially during offline synchronization.
   6. Flag conflicting records instead of silently overwriting them.
   7. Preserve the original transaction history when corrections are made.
   8. Maintain reliable backups and provide a way to reconstruct balances from the
      underlying transaction records.

Important design principle: The transaction and ledger records must be the authoritative
source of truth. Any displayed balance or summary should be reconstructable from those
records. If a calculated balance conflicts with the underlying ledger, the underlying ledger
must prevail.

7. OFFLINE OPERATION AND SYNCHRONIZATION
Because excavators operate in remote areas, the system must support offline data entry.
The developer must ensure:
   •   Authorized users can record operational activities without internet access.
   •   Records are stored safely on the device until synchronization.
   •   Each transaction has a unique identifier.
   •   Synchronization does not create duplicate transactions.
   •   Previously synchronized records are not silently overwritten.
   •   Conflicting changes are flagged for resolution.
   •   The system records when a transaction was created and when it was synchronized.
   •   Sensitive approvals and confirmations follow the required authorization rules, even
       when offline.
The developer must clearly explain which activities can be completed offline and which
require central confirmation or authorization.

8. MANAGEMENT DASHBOARDS AND REPORTS
Management must have a dashboard that provides a clear picture of the Company's
operations and outstanding accountability.
At a minimum, the dashboard must show:
Customer Hours
   •   Total hours purchased.
   •   Total activated hours.
   •   Total hours consumed.
   •   Remaining hours by customer.
   •   Unpaid or unconfirmed purchases.
   •   Hours awaiting activation.
Excavator Operations
   •   Operating hours by excavator.
   •   Hours allocated to customers.
   •   Authorized non-customer operating hours.
   •   Unexplained engine hours.
   •   Meter-reading discrepancies.
   •   Pending operational reports.
Cash Accountability
   •   Total cash collected.
   •   Cash balance held by each employee.
   •   Cash transferred between employees.
   •   Cash declared for remittance.
   •   Cash confirmed as received by the Company.
   •   Outstanding cash balances.
   •   Unconfirmed or disputed remittances.
Exceptions and Investigations
   •   Unexplained engine hours.
   •   Cash shortages or overages.
   •   Unauthorized or pending adjustments.
   •   Unconfirmed payments.
   •   Outstanding approvals.
   •   Overdue reports.
   •   Unresolved variances.
All reports must be traceable to the underlying transactions.

9. DEVELOPER IMPLEMENTATION AND ACCEPTANCE REQUIREMENTS
The developer must not consider the project complete merely because the application has
been built or the forms are working.
Before implementation is approved, the developer must demonstrate the following
scenarios:
   1. A customer purchases hours, payment is independently confirmed, and the hours
      become available.
   2. A customer purchase is recorded but payment is not confirmed. The hours must
      remain inactive.
   3. A customer uses part of the purchased hours. The system correctly calculates the
      remaining balance.
   4. A customer has multiple purchases. The system maintains the history and balance of
      each purchase.
   5. Hours are reassigned to another excavator with approval while preserving the
      original assignment.
   6. An excavator records operating hours. The system reconciles those hours against
      customer and authorized work allocations.
   7. Some engine hours remain unexplained. The system flags them without
      automatically treating them as wasted or billable.
   8. An operator hands cash to a manager. The system transfers custody but does not
      treat the cash as remitted to the Company.
   9. A manager declares a bank deposit. The system does not clear the cash balance until
      the Company independently confirms receipt.
   10. A remittance is partially confirmed. Only the confirmed amount reduces the
       outstanding balance.
   11. An adjustment is made. The original transaction remains visible and the approval
       history is retained.
   12. Transactions are entered offline and synchronized without duplication or loss.
   13. Management can trace a customer-hour balance, an excavator-hour balance and a
       cash balance back to their underlying transactions.
The developer must also provide:
   •   A clear explanation of the proposed system architecture.
   •   A description of the database and ledger structure.
   •   A demonstration of the main workflows.
   •   A list of any requirements that cannot be fully enforced by the proposed technology.
   •   A project implementation schedule and cost.
   •   User training and basic system documentation.
   •   Confirmation that the Company will own and have access to its data, system
       configuration and necessary accounts.
Any limitation affecting the controls in this document must be disclosed before development
is approved, not after implementation.

10. FINAL IMPLEMENTATION PRINCIPLE
The system must be designed to protect the Company's revenue and assets, not simply to
make daily reporting easier.
The developer must ensure that:
   •   Every customer purchase is traceable to payment confirmation and activated hours.
   •   Every customer hour consumed is traceable to actual work.
   •   Every excavator engine hour is allocated or remains visible as an unexplained hour.
   •   Every amount collected is traceable to its current custodian.
   •   Every amount remitted is supported by independent Company confirmation.
   •   Every adjustment is authorized and auditable.
The ultimate test of the system is simple:
Management must be able to select any customer, excavator, employee or financial
transaction and establish exactly what happened, when it happened, who was responsible
and what balance remains outstanding.
END OF GUIDELINE
```
