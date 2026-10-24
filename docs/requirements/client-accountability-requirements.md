# Client requirements: Excavator Operational Accountability System

> Source: "System Development.docx" from the founding tenant (Mzalendo Investment Ltd), received 2026-10-24. Transcribed verbatim; control IDs (`[3.1.1]` …) added for traceability. This document governs scope (DEC-030).

_EXCAVATOR OPERATIONAL ACCOUNTABILITY SYSTEM_  
_Business Problem, Proposed Solution and Required Controls_  
_Document purpose: To communicate the company's business requirements to a prospective software developer and obtain a proposal for developing the system._  

## 1. The Problem We Want to Solve

Mzalendo Investment Ltd operates an excavator rental business. Our excavators work at different customer sites, including remote locations where internet connectivity may be unreliable.
Customers may purchase excavator operating hours in advance and consume them over several days. Some customers are served on an ad hoc basis and pay cash to operators or other authorized field personnel. Managers may collect the cash later before remitting it to the company.
This operating model creates three major accountability risks:

**A. Customer hours and revenue leakage**

- Customers may consume more hours than they have purchased or paid for.
- Hours may be used on an excavator other than the one for which they were purchased.
- Payments may be claimed without being independently confirmed.
- Customer hours and balances may be incorrectly recorded or adjusted.

**B. Excavator operating hours**

- Excavators may operate for more hours than are allocated to recorded customer work.
- Meter readings may be incorrect, inconsistent or unsupported by evidence.
- Unexplained engine hours may go undetected or remain unresolved.
- Operational reports may be incomplete or retrospectively altered.

**C. Cash collection and financial accountability**

- Cash may be collected but not fully handed over to the company.
- Money may change hands between operators and managers without a reliable record.
- A field employee may claim to have remitted cash without the company independently confirming receipt.
- Management may be unable to establish exactly who is accountable for outstanding money.
We therefore need a system that does more than collect daily reports. It must establish a reliable chain of accountability for every customer hour, every engine hour and every amount of money collected.

## 2. The Proposed Solution

We want to develop a digital Excavator Operational Accountability System that records and reconciles the company's customer transactions, excavator operations and cash movements.
The system should provide a clear answer to three questions:
- Customer accountability: How many hours did each customer purchase, how many were activated and consumed, and how many remain available?
- Operational accountability: What happened to every verified engine hour recorded by each excavator?
Financial accountability: Who collected each amount, who currently holds it, and how much has the company independently acknowledged receiving?
The application must support daily operational reporting, photographs and supporting evidence, GPS location capture where available, management dashboards, exception alerts and offline data capture with controlled synchronization.

## 3. Mandatory Business Controls


### 3.1 Customer purchases and hours activation

- `[3.1.1]` Every customer hours purchase must have a unique transaction reference.
- `[3.1.2]` Every purchase must identify the customer, the number of hours purchased and the specific excavator for which the hours are intended.
- `[3.1.3]` Walk-in customers must be accommodated without requiring full customer registration.
- `[3.1.4]` The system must apply a centrally controlled standard hourly rate and automatically apply any authorized, predefined customer discount.
- `[3.1.5]` A customer purchase and its payment must be recorded as separate but linked transactions.
- `[3.1.6]` A customer claim, receipt photograph or payment screenshot must not automatically count as independent confirmation that the company has received the money.
- `[3.1.7]` Hours must only become available for use after the applicable payment confirmation or an explicitly authorized credit arrangement.
- `[3.1.8]` The system must prevent unauthorized activation, duplicate payment allocation and consumption beyond available hours.
- `[3.1.9]` If hours must be transferred to another excavator because the original machine cannot perform the work, the transfer must be authorized, justified and traceable. The original assignment and complete transfer history must remain visible.

### 3.2 Excavator meter readings and operating hours

- `[3.2.1]` Every excavator must have an approved, verified initial engine-hour meter reading before normal operational reconciliation begins.
- `[3.2.2]` Subsequent readings must be recorded with the relevant date, time, responsible user and supporting evidence where required.
- `[3.2.3]` The system must calculate elapsed engine hours from consecutive approved readings.
- `[3.2.4]` Customer work must be recorded through a controlled Work Execution Allocation process linked to the relevant customer entitlement.
- `[3.2.5]` The system must prevent overlapping allocations and double-counting of engine hours.
- `[3.2.6]` Engine hours not allocated to customer work must remain visible and be classified appropriately, including approved non-customer activity, identified variance or unexplained hours.
- `[3.2.7]` The system must flag inconsistent meter readings, missing reports and unexplained differences.
- `[3.2.8]` Unexplained hours must not automatically be treated as fraud or converted into a variance merely because time has passed. A configurable aging threshold must trigger investigation.
- `[3.2.9]` Corrections and adjustments must require a recorded reason, appropriate authorization and an audit trail.

### 3.3 Cash collection and custody

- `[3.3.1]` Every cash collection must identify the amount collected, the person responsible and the relevant transaction where available.
- `[3.3.2]` The system must calculate the expected cash balance held by each field custodian from recorded collections, transfers, remittances and approved corrections.
- `[3.3.3]` Transfers between field personnel—for example, operator to manager—must be recorded as separate transactions and acknowledged by the receiving custodian.
- `[3.3.4]` A transfer between field personnel must never be treated as money received by the company.
- `[3.3.5]` Cash remittance to the company must follow a separate process.
- `[3.3.6]` The company must independently acknowledge the amount actually received before it is classified as confirmed company receipt.
- `[3.3.7]` Differences between the amount declared and the amount received must be recorded and investigated.
- `[3.3.8]` The default expectation is that the entire accountable field cash balance is remitted to the company. Any permitted exception must be authorized and traceable.
- `[3.3.9]` Payments made directly to the company's bank account or an authorized company representative must be recorded without falsely showing that a field operator physically handled the money.

### 3.4 Record integrity, approvals and audit trails

- `[3.4.1]` Posted transactions must not be silently edited or deleted.
- `[3.4.2]` Errors must be corrected through authorized, traceable reversals or adjustment transactions.
- `[3.4.3]` Every material transaction must record who initiated it and when; approvals must identify the approving person and time.
- `[3.4.4]` Sensitive responsibilities must be separated wherever practical. For example, the person claiming a payment should not automatically be the person independently confirming it.
- `[3.4.5]` The system must retain the history of changes, approvals, rejections, adjustments and investigations.
- `[3.4.6]` Calculated balances must be derived from authoritative transaction records, not manually overwritten.
- `[3.4.7]` Stored balance summaries must be reproducible from the underlying ledger.
- `[3.4.8]` Management must be able to trace reported figures to the transactions and evidence supporting them.

### 3.5 Offline operation and synchronization

- `[3.5.1]` Authorized field personnel must be able to capture permitted operational information in areas without internet connectivity.
- `[3.5.2]` The system must synchronize captured records when connectivity becomes available.
- `[3.5.3]` Offline operation must not silently bypass mandatory approvals or independent payment confirmation.
- `[3.5.4]` Synchronization must prevent duplicate transactions, lost records and silent overwriting of conflicting information.
- `[3.5.5]` Conflicts—for example, two users attempting to consume the same remaining customer hours—must be detected and resolved through a controlled process.
- `[3.5.6]` The developer must demonstrate these controls using the actual proposed platform and devices.

### 3.6 Management oversight and exception reporting

- `[3.6.1]` The system must provide dashboards and reports showing, at minimum:
- `[3.6.2]` Customer hours purchased, activated, consumed and remaining.
- `[3.6.3]` Excavator meter readings and engine-hour reconciliation.
- `[3.6.4]` Unexplained engine hours and outstanding investigations.
- `[3.6.5]` Cash held by each field custodian.
- `[3.6.6]` Cash transfers awaiting acknowledgement.
- `[3.6.7]` Remittances awaiting company confirmation.
- `[3.6.8]` Payments awaiting confirmation and hours awaiting activation.
- `[3.6.9]` Missing or overdue operational reports.
- `[3.6.10]` Unauthorized attempts, unresolved discrepancies and outstanding approvals.
- `[3.6.11]` The system must help management identify exceptions promptly rather than relying solely on routine reports.

## 4. What We Expect from the Developer

We want the developer to:
- Review these business requirements and identify any gaps or ambiguities.
Recommend an appropriate technical architecture and explain its limitations, particularly for offline operation, ledger integrity and access control.
- Demonstrate how the proposed system will enforce each mandatory control.
- Provide a development quotation, implementation schedule and clearly defined deliverables.
- Explain the proposed workflows, data structure, user roles, security, audit trails, backups and recovery arrangements.
- Provide a testing and acceptance plan proving that the controls work before the company accepts the application.
- Deliver user training, documentation and the agreed administrative access, data ownership and maintenance arrangements.
The developer must identify any requirement that cannot be implemented reliably as specified and obtain the company's approval before proposing a deviation.

## 5. Our Definition of Success

The system will be successful when management can reliably establish:
- Every customer hour: where it came from, whether it was authorized for use, how it was consumed and what remains.
- Every engine hour: how it was allocated, explained or flagged for investigation.
- Every amount of money: who collected it, who held it, how it moved and whether the company independently acknowledged receipt.
The ultimate objective is to reduce revenue leakage, improve operational discipline, strengthen cash accountability and give management reliable, traceable information for decision-making.
This document defines the business problem and the controls required. The developer is expected to propose the technical solution that satisfies them.
