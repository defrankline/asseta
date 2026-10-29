# Accountability UI — mobile strings (Android = iOS)

Source of truth for every new user-facing string of the accountability wave in the **Supervisor** (field) app and the
**Owner** app. Android defines them as Kotlin constants (`FieldAccountabilityTexts`, `OwnerAccountabilityTexts`); iOS
copies the English text exactly. Missing strings: add them here (same key style) and use them on both platforms.

Placeholders: `{name}` style; money is formatted with the existing money formatter (`TZS 50,000.00`), hours with the
existing decimal formatter followed by ` h`. Wording rules: plain English, neutral (never "fraud"), no tenant names,
amounts or day counts hard-coded (they come from the server).

Gating (both platforms, same rules): an entry is shown only when (1) the server advertises the sync capability,
(2) the user has the permission from `/me`, and (3) the tenant policy (effective policy read online and cached
encrypted on the phone) enables it. Unknown policy (never loaded) = hidden, so today's screens are unchanged.

| Feature | Capability | Permission | Policy |
|---|---|---|---|
| Sell customer hours | `OP_HOURS_PURCHASE` | `tenant.hours.purchase` | `CUSTOMER_HOURS.enabled` (walk-in option: `walk_in_allowed`) |
| Request hours transfer | `OP_HOURS_TRANSFER_REQUEST` | `tenant.hours.transfer` (+ `tenant.hours.read` for the purchase list) | `CUSTOMER_HOURS.enabled` |
| Cash holder picker on collection / remittance / sale | — | `tenant.collection.record` | `CASH_CUSTODY.recorders_may_record_for_others` |
| Transfer cash, acknowledge transfer / float | `OP_CASH_TRANSFER` | `tenant.collection.record` | (ack list comes from the server) |
| Ask to keep cash (online only) | — | `tenant.collection.record` | `CASH_CUSTODY.retention_allowed` |
| Daily reading | `METER_DAILY_READING` | `tenant.meter.capture` | — |
| Propose meter baseline | `OP_METER_BASELINE` | `tenant.meter.capture` | — |
| Propose reading correction | `OP_METER_CORRECTION` | `tenant.meter.capture` | — |

## Supervisor app

### Money tab "+" menu (added entries)
| Key | English |
|---|---|
| field.menu.sellHours | Sell customer hours |
| field.menu.requestHoursTransfer | Request hours transfer |
| field.menu.transferCash | Transfer cash to a colleague |
| field.menu.askToKeepCash | Ask to keep cash |

### Screen titles
| Key | English |
|---|---|
| field.title.hoursSale | Sell customer hours |
| field.title.hoursTransfer | Request hours transfer |
| field.title.cashTransfer | Transfer cash |
| field.title.acknowledgeTransfer | Cash transfer |
| field.title.acknowledgeFloat | Cash float |
| field.title.retention | Ask to keep cash |
| field.title.dailyReading | Daily reading |
| field.title.baseline | Propose meter baseline |
| field.title.correction | Propose reading correction |

### Common
| Key | English |
|---|---|
| field.common.cashHolder | Cash held by |
| field.common.me | Me |
| field.common.reasonCategory | Reason category |
| field.common.reasonCategoryOptional | Reason category (optional) |
| field.common.noCategory | No category |
| field.common.reason | Reason |
| field.common.noteOptional | Note (optional) |
| field.common.amount | Amount |
| field.common.currency | Currency |
| field.common.needsRules | Connect once so this phone can load your company's rules for this. |
| field.common.serverTooOld | Your company's server does not accept this from the app yet. |
| field.common.onlineOnly | Connect to the internet to send this request. |
| field.common.lastUpdated | Last updated {time}. |
| field.common.errCurrency | Enter a 3-letter currency code. |
| field.common.send | Send |

### Sell customer hours (offline, `HOURS_PURCHASE`)
| Key | English |
|---|---|
| field.hours.sectionCustomer | Customer |
| field.hours.registered | Registered |
| field.hours.walkIn | Walk-in |
| field.hours.customer | Customer |
| field.hours.customerEmpty | Customers appear here after a sync. |
| field.hours.walkInName | Customer name |
| field.hours.walkInPhone | Phone (optional) |
| field.hours.walkInFooter | The office gives a walk-in customer a code. A phone number helps find them again. |
| field.hours.sectionHours | Hours |
| field.hours.machine | Machine |
| field.hours.hours | Hours |
| field.hours.hoursFooter | The price comes from your company's rate card and any approved discount. |
| field.hours.sectionPayment | Payment |
| field.hours.paidNow | Paid now |
| field.hours.notPaid | Not paid yet |
| field.hours.methodCash | Cash |
| field.hours.methodBank | Bank |
| field.hours.methodMobileMoney | Mobile money |
| field.hours.amountReceived | Amount received |
| field.hours.reference | Reference (required for bank and mobile money) |
| field.hours.received | Received |
| field.hours.paymentFooter | Hours become available only after someone else verifies this payment. |
| field.hours.notPaidFooter | The hours stay inactive until a payment is verified or credit is approved by the office. |
| field.hours.evidence | Payment evidence (optional) |
| field.hours.evidenceFooter | Receipt or mobile-money screenshot. Stored encrypted on this phone and uploaded before the sale is sent. |
| field.hours.photograph | Photograph evidence |
| field.hours.addPhoto | Add another photo |
| field.hours.errCustomer | Choose the customer. |
| field.hours.errWalkInName | Enter the customer's name. |
| field.hours.errPhone | The phone number must have at least 3 characters. |
| field.hours.errMachine | Choose the machine. |
| field.hours.errHours | Enter the hours (more than 0, at most 2 decimal places). |
| field.hours.errAmount | Enter the amount received (more than 0). |
| field.hours.errReference | Enter the reference for bank and mobile-money payments. |
| field.hours.errWalkInOff | Walk-in customers are turned off for your company. |
| field.hours.off | Customer hours are turned off for your company. |

### Request hours transfer (offline, `HOURS_TRANSFER_REQUEST`)
| Key | English |
|---|---|
| field.transfer.purchase | Purchase |
| field.transfer.purchaseOption | {number} · {hours} h left |
| field.transfer.purchasesEmpty | No purchases with hours left. Purchases appear here after you connect. |
| field.transfer.fromMachine | From machine |
| field.transfer.toMachine | To machine |
| field.transfer.hours | Hours to move |
| field.transfer.footerApproval | Someone else approves the transfer before the hours move. |
| field.transfer.footerDirect | The hours move when the server accepts the request. |
| field.transfer.errPurchase | Choose the purchase. |
| field.transfer.errMachine | Choose the machine to move the hours to. |
| field.transfer.errSameMachine | Choose a different machine from the one the hours are on. |
| field.transfer.errHours | Enter the hours to move (more than 0, at most 2 decimal places). |
| field.transfer.errTooMany | Only {hours} h are left on this purchase. |
| field.transfer.errReason | Enter a reason (at least 3 characters). |
| field.transfer.errCategory | Choose a reason category. |

### Transfer cash (offline, `CASH_TRANSFER`)
| Key | English |
|---|---|
| field.cashTransfer.from | From |
| field.cashTransfer.to | To |
| field.cashTransfer.amount | Amount handed over |
| field.cashTransfer.when | Transferred |
| field.cashTransfer.amountReceived | Amount you received |
| field.cashTransfer.footerAck | The cash stays with the sender until the receiver acknowledges it. |
| field.cashTransfer.footerNoAck | The cash moves to the receiver when the server accepts the transfer. |
| field.cashTransfer.footerSelf | Recording a transfer you receive counts as your acknowledgement. |
| field.cashTransfer.custodiansEmpty | Colleagues who hold cash appear here after you connect. |
| field.cashTransfer.errTo | Choose who receives the cash. |
| field.cashTransfer.errSame | The sender and the receiver must be different people. |
| field.cashTransfer.errAmount | Enter the amount (more than 0). |
| field.cashTransfer.errReceived | Enter the amount you received (0 or more). |

### Acknowledge a transfer or a float (offline, `CASH_TRANSFER_ACKNOWLEDGEMENT` / `CASH_FLOAT_ACKNOWLEDGEMENT`)
| Key | English |
|---|---|
| field.ack.section | Cash to acknowledge |
| field.ack.transferFrom | Transfer from {name} |
| field.ack.floatFromOffice | Float from the office |
| field.ack.someone | A colleague |
| field.ack.declared | Declared amount |
| field.ack.sent | Sent |
| field.ack.issued | Issued |
| field.ack.amountReceived | Amount received |
| field.ack.acknowledge | Acknowledge |
| field.ack.dispute | Dispute |
| field.ack.disputeReason | Why you dispute it |
| field.ack.footer | A different amount opens a cash difference for the office to review. |
| field.ack.errReceived | Enter the amount you received (0 or more). |
| field.ack.errReason | Say why you dispute it. |
| field.ack.waiting | Your answer is waiting to sync. |
| field.ack.notFound | This item is no longer waiting for you. |

### Money tab "Transfers" segment
| Key | English |
|---|---|
| field.money.transfers | Transfers |
| field.money.transfersEmptyTitle | No cash transfers |
| field.money.transfersEmptyMessage | Cash moved between you and colleagues appears here. |
| field.money.transferTo | To {name} |
| field.money.transferFrom | From {name} |
| field.money.statusPendingAck | Awaiting acknowledgement |
| field.money.statusAcknowledged | Acknowledged |
| field.money.statusDisputed | Disputed |

### Ask to keep cash (online, `requestCashRetention`)
| Key | English |
|---|---|
| field.retention.amount | Amount to keep |
| field.retention.validUntil | Keep until (optional) |
| field.retention.footer | Someone else approves this. Until then the full balance is expected when you remit. |
| field.retention.sent | Request sent for approval. |
| field.retention.errAmount | Enter the amount to keep (more than 0). |
| field.retention.errReason | Enter a reason (at least 3 characters). |
| field.retention.off | Your company does not allow keeping cash. |

### Readings: daily reading, baseline, correction (offline)
| Key | English |
|---|---|
| field.meter.recordDaily | Record daily reading |
| field.meter.proposeBaseline | Propose meter baseline |
| field.meter.proposeCorrection | Propose a correction |
| field.meter.kindDaily | Daily |
| field.meter.kindBaseline | Baseline |
| field.meter.dailyFooter | A daily reading outside a job keeps the machine's engine hours accounted for. |
| field.meter.baselineFooter | Someone else approves the baseline before it counts. |
| field.meter.baselineNote | Note (optional) |
| field.meter.correctionOf | Reading to correct |
| field.meter.correctionReason | Reason for the correction |
| field.meter.correctionFooter | The corrected reading replaces the old one only after someone else approves it. |
| field.meter.errCorrectionReason | Enter a reason of at least 10 characters. |
| field.meter.correctionNotSynced | A reading can be corrected once the server has it. |
| field.meter.correctionNotLive | Only a reading the server still counts can be corrected. |
| field.meter.readingKindDaily | Daily reading |
| field.meter.needsSync | Sync once while online before recording this. |
| field.meter.machineMissing | This machine is not on this device. |

### Finding (exception) names added by this wave (Readings detail, both apps)
| Key | English |
|---|---|
| field.finding.HOURS_OVERRUN | Hours beyond purchase |
| field.finding.UNEXPLAINED_HOURS | Engine hours not yet explained |
| field.finding.MISSING_DAILY_REPORT | Daily report missing |
| field.finding.OVERLAPPING_ALLOCATION | Overlaps another job's hours |
| field.finding.OVERLAPPING_ACTIVITY | Overlapping work log entries |

### Supervisor notification taps (Inbox)
| Target entity | Opens |
|---|---|
| cash_transfer, supervisor_cash_custody | Money tab ("Cash to acknowledge" at the top) |
| machine | The machine (Readings → machine), else the notification |

A push tap opens the Inbox, then does exactly what tapping that notification in the Inbox does (above).

### Sync status titles (outbox)
| Key | English |
|---|---|
| field.outbox.hoursSale | Hours sale |
| field.outbox.hoursTransfer | Hours transfer request |
| field.outbox.cashTransfer | Cash transfer |
| field.outbox.transferAck | Transfer acknowledgement |
| field.outbox.floatAck | Float acknowledgement |
| field.outbox.baseline | Meter baseline proposal |
| field.outbox.correction | Reading correction proposal |
| field.outbox.dailyReading | Daily reading |

## Owner app

### More
| Key | English |
|---|---|
| owner.more.accountability | Accountability |

### Approvals: section headers / empty lines
| Key | English |
|---|---|
| owner.approvals.discounts | Customer discounts |
| owner.approvals.discountsEmpty | No discounts waiting. |
| owner.approvals.credit | Credit arrangements |
| owner.approvals.creditEmpty | No credit arrangements waiting. |
| owner.approvals.hoursTransfers | Hours transfers |
| owner.approvals.hoursTransfersEmpty | No hours transfers waiting. |
| owner.approvals.cancellations | Hours cancellations |
| owner.approvals.cancellationsEmpty | No cancellations waiting. |
| owner.approvals.baselines | Meter baselines |
| owner.approvals.baselinesEmpty | No baselines waiting. |
| owner.approvals.classifications | Engine-hour classifications |
| owner.approvals.classificationsEmpty | No classifications waiting. |
| owner.approvals.corrections | Reading corrections |
| owner.approvals.correctionsEmpty | No corrections waiting. |
| owner.approvals.writeOffs | Cash write-offs |
| owner.approvals.writeOffsEmpty | No write-offs waiting. |
| owner.approvals.retentions | Cash retentions |
| owner.approvals.retentionsEmpty | No retention requests waiting. |
| owner.approvals.adjustments | Custody adjustments |
| owner.approvals.adjustmentsEmpty | No adjustments waiting. |
| owner.approvals.proposed | Proposed {time} |

### Approvals: row headlines
| Key | English |
|---|---|
| owner.row.discount | {percent}% discount |
| owner.row.credit | Credit limit {money} |
| owner.row.hoursTransfer | Move {hours} h to another machine |
| owner.row.cancellation | Cancel an hours purchase |
| owner.row.baseline | Baseline {reading} h · {machine} |
| owner.row.classification | {hours} h · {category} |
| owner.row.correction | {old} → {new} h · {machine} |
| owner.row.writeOff | Write off {money} |
| owner.row.retention | Keep {money} |
| owner.row.adjustment | {kind} {money} |

### Decision screen (one for every kind above)
| Key | English |
|---|---|
| owner.decision.titleDiscount | Customer discount |
| owner.decision.titleCredit | Credit arrangement |
| owner.decision.titleHoursTransfer | Hours transfer |
| owner.decision.titleCancellation | Hours cancellation |
| owner.decision.titleBaseline | Meter baseline |
| owner.decision.titleClassification | Engine-hour classification |
| owner.decision.titleCorrection | Reading correction |
| owner.decision.titleWriteOff | Cash write-off |
| owner.decision.titleRetention | Cash retention |
| owner.decision.titleAdjustment | Custody adjustment |
| owner.decision.request | Request |
| owner.decision.decision | Decision |
| owner.decision.approve | Approve |
| owner.decision.reject | Reject |
| owner.decision.noteOptional | Note (optional to approve, required to reject) |
| owner.decision.noteRequired | Note (at least 5 characters) |
| owner.decision.ownRequest | Someone else must decide your own request |
| owner.decision.confirmReject | Reject this request? |
| owner.decision.approved | Approved. |
| owner.decision.rejected | Rejected. |
| owner.decision.notFoundTitle | Request not found |
| owner.decision.notFoundMessage | It may already be decided. |
| owner.decision.footer | The person who proposed a request can't decide it. |

### Decision screen: field labels
| Key | English |
|---|---|
| owner.field.discount | Discount |
| owner.field.effectiveFrom | Effective from |
| owner.field.effectiveTo | Effective to |
| owner.field.creditLimit | Credit limit |
| owner.field.terms | Terms |
| owner.field.hours | Hours |
| owner.field.fromMachine | From machine |
| owner.field.toMachine | To machine |
| owner.field.machine | Machine |
| owner.field.reading | Reading |
| owner.field.oldReading | Old reading |
| owner.field.newReading | New reading |
| owner.field.period | Period |
| owner.field.category | Category |
| owner.field.outcome | Outcome |
| owner.field.outcomeNonCustomer | Approved non-customer work |
| owner.field.outcomeVariance | Identified difference |
| owner.field.declared | Declared |
| owner.field.received | Received |
| owner.field.difference | Difference |
| owner.field.amount | Amount |
| owner.field.validUntil | Valid until |
| owner.field.kind | Kind |
| owner.field.reason | Reason |
| owner.field.note | Note |
| owner.field.proposedBy | Proposed by |
| owner.field.proposed | Proposed |
| owner.field.status | Status |
| owner.field.source | Source |
| owner.field.captured | Captured |
| owner.field.when | When |

### Remittance confirm (Cash handover screen)
| Key | English |
|---|---|
| owner.remit.amountReceived | Amount received |
| owner.remit.amountReceivedFooter | Count the cash. A different amount opens a cash difference for review. |
| owner.remit.expected | Expected balance |
| owner.remit.shortfall | Not covered by a retention |
| owner.remit.receivedLabel | Received |
| owner.remit.errAmount | Enter the amount received (0 or more). |

### Accountability dashboard (Owner app summary, `getAccountabilitySummary`)
| Key | English |
|---|---|
| owner.dash.title | Accountability |
| owner.dash.footer | Policy {version} · As of {time} |
| owner.dash.hiddenNote | Some tiles are hidden by your company's settings. |
| owner.dash.empty | Nothing to show. |
| owner.dash.approvals | Outstanding approvals |
| owner.dash.approvalRequests | Approval requests |
| owner.dash.paymentsToVerify | Payments to verify |
| owner.dash.remittancesToVerify | Remittances to verify |
| owner.dash.cashRetentions | Cash retentions |
| owner.dash.custodyAdjustments | Custody adjustments |
| owner.dash.writeOffs | Write-offs |
| owner.dash.total | Total |
| owner.dash.cash | Cash |
| owner.dash.transfersAwaiting | Transfers awaiting acknowledgement |
| owner.dash.floatsAwaiting | Floats awaiting acknowledgement |
| owner.dash.remittancesAwaiting | Remittances awaiting confirmation |
| owner.dash.partialRemittances | Partial remittances |
| owner.dash.custodians | Cash per custodian |
| owner.dash.custodianLine | {money} outstanding |
| owner.dash.inTransit | {money} in transit |
| owner.dash.payments | Payments awaiting confirmation |
| owner.dash.discrepancies | Discrepancies |
| owner.dash.openVariances | Open cash differences |
| owner.dash.writeOffsProposed | Write-offs proposed |
| owner.dash.syncConflicts | Sync conflicts to review |
| owner.dash.investigations | Investigations |
| owner.dash.open | Open |
| owner.dash.inReview | In review |
| owner.dash.attempts | Refused attempts |
| owner.dash.permissionDenied | Permission refusals |
| owner.dash.sod | Own-request decisions refused |
| owner.dash.window | Last {days} days |
| owner.dash.customerHours | Customer hours |
| owner.dash.hoursActivated | Activated |
| owner.dash.hoursConsumed | Consumed |
| owner.dash.hoursRemaining | Remaining |
| owner.dash.hoursAwaiting | Awaiting activation |
| owner.dash.hoursExpired | Expired |
| owner.dash.openOverruns | Hours beyond purchase |
| owner.dash.hoursAwaitingTile | Hours awaiting activation |
| owner.dash.purchasesAwaitingPayment | Purchases awaiting payment |
| owner.dash.purchasesPartlyActive | Purchases partly active |
| owner.dash.engineHours | Engine hours |
| owner.dash.machines | Machines |
| owner.dash.statusNoBaseline | No baseline |
| owner.dash.statusReconciled | Reconciled |
| owner.dash.statusPendingReview | Pending review |
| owner.dash.statusUnexplained | Unexplained hours |
| owner.dash.unexplained | Unexplained engine hours |
| owner.dash.unexplainedLine | {hours} h · oldest {days} days |
| owner.dash.missingReports | Missing daily reports |
| owner.dash.missingLine | {machine} · {day} |
| owner.dash.count | {count} · {money} |
| owner.dash.none | None |

### Notification deep links (push tap / inbox row)
| Notification type | Opens |
|---|---|
| HOURS_APPROVAL_REQUESTED | Decision screen of the discount / credit / transfer / cancellation (by `target.entity`), else Approvals |
| METER_APPROVAL_REQUESTED | Decision screen of the baseline / correction / classification, else Approvals |
| CASH_APPROVAL_REQUESTED | Decision screen of the write-off / retention / custody adjustment, else Approvals |
| HOURS_OVERRUN | The meter exception (review) |
| HOURS_EXPIRING | Accountability dashboard |
| UNEXPLAINED_ENGINE_HOURS, MISSING_DAILY_REPORT | The machine |
| CASH_TRANSFER_TO_ACKNOWLEDGE, CASH_FLOAT_TO_ACKNOWLEDGE | Owner: Cash with supervisors. Supervisor: Money tab |
| CASH_VARIANCE_OPENED | Approvals (cash write-offs) |
| PARTIAL_REMITTANCE | The cash handover (remittance) |

Rules shared by both apps (Owner):
- An accountability section appears under Approvals only when the role may read it AND something waits (a capability the
  company does not use never adds an empty section). Read permissions: hours lists `tenant.hours.read`; baselines,
  classifications, corrections `tenant.meter.read`; write-offs and custody adjustments `tenant.finance.read`; retentions
  `tenant.finance.read` or `tenant.collection.record`.
- Decide permissions: discount `tenant.hours.discount_approve`, credit `tenant.hours.credit_approve`, hours transfer
  `tenant.hours.transfer_approve`, cancellation `tenant.hours.cancel_approve`, baseline and correction
  `tenant.meter.approve`, classification `tenant.meter.classify`, write-off `tenant.finance.writeoff`, retention
  `tenant.finance.retention_approve`, custody adjustment `tenant.finance.adjustment_approve`.
- Own request (proposed_by / requested_by / created_by = `/me` user_id): Approve and Reject are disabled and
  `owner.decision.ownRequest` is shown. Meter decisions (baseline, classification, correction) need a note of at least
  5 characters for both answers; the others need a note only to reject.
- Remittance confirm: "Amount received" is pre-filled with the declared amount, must be a number >= 0, and is sent as
  `amount_received` (RemittanceDecisionIn); expected balance, shortfall and received amount show on the card when set.
- Dashboard (More → Accountability, `tenant.accountability.read`): tiles in this order — outstanding approvals, cash,
  payments, discrepancies, investigations, refused attempts, customer hours, hours awaiting activation, engine hours,
  unexplained engine hours, missing daily reports; null tiles are skipped; links: approvals/discrepancies → Approvals,
  cash → Cash with supervisors (`tenant.finance.read`), investigations → Investigations, unexplained hours → Meter
  exceptions (`tenant.meter.read`).

## Gap pass (DEC-030 G1–G5)

Rules shared by both apps:
- **Capabilities (G1):** `/me` `tenants[].disabled_capabilities` (today only `CUSTOMER_HOURS`). When `CUSTOMER_HOURS` is
  listed: Supervisor hides "Sell customer hours" and "Request hours transfer" (and does not read the CUSTOMER_HOURS
  policy); Owner hides the discount / credit / hours transfer / cancellation Approvals sections and the "Customer
  hours" and "Hours awaiting activation" dashboard tiles. Missing field = nothing disabled (today's behaviour).
- **Names (G2):** every row and detail shows the server's `*_name` (customer_name, machine_code/machine_name,
  staff_member_name, from/to staff names, proposed_by_name / requested_by_name / created_by_name, decided_by_name,
  purchase_number, job_number). Only when the name is null the first 8 characters of the id are shown.
- **Offline retention (G3):** when the server announces `OP_CASH_RETENTION_REQUEST`, "Ask to keep cash" is queued in
  the outbox as `CASH_RETENTION_REQUEST` (`client_id` = the form visit's id) and works offline; otherwise the old
  online request is used. Status is read online with `GET /cash/retentions/{id}` (id from the acked op result).
- **Exact records (G5):** a push tap or inbox row uses `kind` + `record_id` (inbox: `data.kind` / `data.record_id`,
  else `target.entity` / `target.id`, else the link path). Unknown kinds open the list as before.

### Supervisor
| Key | English |
|---|---|
| field.retention.saved | Saved. It is sent when the phone syncs. |
| field.retention.viewStatus | View request status |
| field.title.retentionStatus | Request to keep cash |
| field.retention.statusPending | Waiting for approval |
| field.retention.statusApproved | Approved |
| field.retention.statusRejected | Rejected |
| field.retention.notSynced | This request has not reached the server yet. |
| field.retention.offline | Connect to the internet to see whether it was approved. |
| field.retention.notFound | This request is not on this phone. |
| field.retention.requested | Requested |
| field.retention.decidedBy | Decided by |
| field.retention.decisionNote | Decision note |
| field.retention.status | Status |
| field.money.retentions | Requests to keep cash |
| field.outbox.retention | Request to keep cash |
| field.conflict.RETENTION_NOT_ALLOWED | Your company does not allow keeping cash, so this request was not accepted. |
| field.conflict.DUPLICATE_RETENTION | This request to keep cash was already sent. |

Sync status: a CONFLICT/REJECTED item with one of the `field.conflict.*` codes shows that sentence instead of
"CODE: server message". The "Requests to keep cash" section (Money → Transfers) lists this phone's retention requests
(newest first; amount, sync state or server status); a row opens "Request to keep cash" (status screen).

Supervisor notification taps (replaces the earlier table):
| kind / target entity | Opens |
|---|---|
| CASH_TRANSFER / cash_transfer | That transfer's acknowledge screen while it waits for me, else the Money tab |
| CASH_FLOAT / supervisor_cash_custody | That float's acknowledge screen while it waits for me, else the Money tab |
| CASH_RETENTION / cash_retention | The retention status screen |
| REMITTANCE_OVERDUE / cash_remittance_overdue | Money tab |
| machine | The machine, else the notification |

### Owner
| Key | English |
|---|---|
| owner.field.customer | Customer |
| owner.field.purchase | Purchase |
| owner.field.job | Job |
| owner.field.custodian | Cash held by |
| owner.field.counterparty | Other custodian |
| owner.field.requestedBy | Requested by |
| owner.field.decidedBy | Decided by |
| owner.field.decisionNote | Decision note |
| owner.field.from | From |
| owner.field.to | To |
| owner.field.recordedBy | Recorded by |
| owner.field.acknowledgedBy | Acknowledged by |
| owner.field.transferred | Transferred |
| owner.field.issued | Issued |
| owner.field.day | Day |
| owner.field.cutoff | Cut-off |
| owner.field.notRemitted | Not remitted |
| owner.field.flagged | Flagged |
| owner.approvals.proposedBy | Proposed {time} by {name} |
| owner.record.transferTitle | Cash transfer |
| owner.record.floatTitle | Cash float |
| owner.record.notFoundTitle | Record not found |
| owner.record.notFoundMessage | It may have been removed, or you may not have access to it. |
| owner.dash.remittancesOverdue | Remittances overdue today |
| owner.dash.cutoff | Cut-off {hour}:00 |
| owner.overdue.title | Overdue remittances |
| owner.overdue.detailTitle | Overdue remittance |
| owner.overdue.empty | No overdue remittances today. |
| owner.overdue.line | Still held after the {hour}:00 cut-off on {day}. |

`{hour}` is two digits (`07`, `18`). The dashboard cash tile shows "Remittances overdue today" with the count (and
"Cut-off {hour}:00" beneath) only when `remittances_overdue_today` is not null; tapping it opens "Overdue remittances"
(`GET /cash/remittance-overdue?day_from=today&day_to=today`, `tenant.finance.read`); a row ("{name}" with the amounts)
opens "Overdue remittance" (`GET /cash/remittance-overdue/{id}`). Decision screens load their record by id
(`GET .../{id}`), so a decided request shows its status and decision instead of "Request not found".

Owner notification taps (push and inbox), by `kind`:
| kind | Opens |
|---|---|
| CASH_TRANSFER | Cash transfer (record screen) |
| CASH_FLOAT | Cash float (record screen) |
| CASH_VARIANCE | Cash write-off decision screen of that variance |
| CASH_RETENTION | Cash retention decision screen |
| CUSTODY_ADJUSTMENT | Custody adjustment decision screen |
| CASH_REMITTANCE | Cash handover (remittance) screen |
| REMITTANCE_OVERDUE | Overdue remittance |
| HOURS_DISCOUNT, HOURS_CREDIT, HOURS_TRANSFER, HOURS_CANCELLATION | That decision screen |
| METER_BASELINE, METER_CORRECTION, ENGINE_HOURS_CLASSIFICATION | That decision screen |
| anything else | As before (entity / link), else the notification |

## Capability switches and overdue detail (follow-up F1, F2)

Rules shared by both apps:
- **Switches (F1):** the capability codes `ENGINE_HOURS` and `CASH_CUSTODY` join `CUSTOMER_HOURS` in `/me`
  `tenants[].disabled_capabilities`; the Owner dashboard also reads `AccountabilitySummaryDto.disabled_capabilities`
  (the union of both is used). A listed code hides every entry point in the table below; missing field = nothing
  disabled (today's behaviour). Data of a switched-off capability is not read (CASH_CUSTODY off: no cash policy,
  custodians, transfers, floats to acknowledge or cash reasons are fetched by the Supervisor app).
- **Deep links:** a push tap, inbox row or link to a hidden kind opens the list/home instead (Owner: Approvals for a
  hidden decision, Cash with supervisors for a hidden cash record or overdue remittance; Supervisor: Money tab for
  cash, the notification for anything else).
- **Sync status:** a CONFLICT/REJECTED item with `ENGINE_HOURS_DISABLED` or `CASH_CUSTODY_DISABLED` shows the sentence
  below instead of "CODE: server message".
- **Overdue remittance (F2):** a Supervisor `REMITTANCE_OVERDUE` tap (inbox row or push; `data.kind` +
  `data.record_id`, else target entity `cash_remittance_overdue` + id) reads `GET /cash/remittance-overdue/{id}`
  online and opens "Overdue remittance"; on 404, offline or any error (or CASH_CUSTODY off) it opens the Money tab.

| Switch off | Supervisor app hides | Owner app hides |
|---|---|---|
| `CUSTOMER_HOURS` | Money "+": Sell customer hours, Request hours transfer | Approvals: discounts, credit, hours transfers, cancellations; dashboard tiles Customer hours, Hours awaiting activation; their deep links → Approvals |
| `ENGINE_HOURS` | Readings: Record daily reading, Propose meter baseline, Propose a correction | Approvals: baselines, engine-hour classifications, reading corrections; dashboard tiles Engine hours, Unexplained engine hours, Missing daily reports; their deep links → Approvals |
| `CASH_CUSTODY` | Money "+": Transfer cash to a colleague, Ask to keep cash; Money: "Cash to acknowledge" (transfer / float acknowledgement), Transfers segment (incl. Requests to keep cash); "Cash held by" picker (recording for another custodian) on collection / remittance / sale; Overdue remittance screen; transfer / float / retention / overdue taps → Money tab | Approvals: cash write-offs, requests to keep cash, custody adjustments; Cash transfer / Cash float record screens and Overdue remittances (list and detail) → Cash with supervisors; Cash handover confirm: the "Amount received" field (confirm sends no amount); dashboard rows Transfers / Floats awaiting acknowledgement, Partial remittances, Remittances overdue today (+ Cut-off), Cash retentions, Custody adjustments, Write-offs, Open variances, Write-offs proposed |

Collections, floats (issue / list), cash handovers (remittances), reconciliation and job meter readings stay in every case.

### Supervisor
| Key | English |
|---|---|
| field.conflict.ENGINE_HOURS_DISABLED | Your company has switched off engine-hour controls, so this was not accepted. |
| field.conflict.CASH_CUSTODY_DISABLED | Your company has switched off cash custody controls, so this was not accepted. |
| field.title.remittanceOverdue | Overdue remittance |
| field.overdue.custodian | Cash held by |
| field.overdue.notRemitted | Not remitted |
| field.overdue.day | Day |
| field.overdue.cutoff | Cut-off |
| field.overdue.flagged | Flagged |
| field.overdue.line | Still held after the {hour}:00 cut-off on {day}. |
| field.overdue.hint | Remit this cash to the office as soon as you can. |

"Overdue remittance" shows the custodian's name (short id when null) as the headline, then the fields above
(amounts as "TZS 50,000.00, USD 20.00"; `{hour}` two digits), then `field.overdue.line` and `field.overdue.hint` as
the footer. Pull to refresh re-reads it.

Supervisor notification taps (replaces the REMITTANCE_OVERDUE row of the gap-pass table):
| kind / target entity | Opens |
|---|---|
| REMITTANCE_OVERDUE / cash_remittance_overdue | "Overdue remittance" (read online), else the Money tab |

### Owner
No new strings: switched-off capabilities only hide sections, rows and fields listed above.

## DEC-031 Phase 3 — deposits (D2 stronger remittances, D3 cash holding allowance)

Rules shared by both apps:
- **Gate:** the new remittance details (method, deposit account, deposit slip photos) appear on the Supervisor
  "Hand over cash" form only when the server announces the sync capability `REMITTANCE_DETAILS_V1`. Without it the
  form is exactly as before (amount, currency, reference, time, note) and the payload carries none of the new keys.
- **Deposit accounts (offline):** from `SyncData.deposit_accounts` (`SyncDepositAccountDto`, kept by `sync_revision`;
  a deactivated account arrives with `is_active=false` and is removed from the picker). The picker lists active
  accounts whose `currency` equals the form's currency and whose type matches the chosen method
  (`CASH_TO_OFFICE` ↔ `CASH_OFFICE`, `BANK_DEPOSIT` ↔ `BANK`, `MOBILE_MONEY` ↔ `MOBILE_MONEY`). Choosing an account
  sets the method from its type. Row text: `{name}`, subtitle `{institution} · {account_number_masked}` (missing parts
  left out).
- **Method:** segmented choice, default "Cash to the office". The payload always sends `method` when the capability is
  announced.
- **Requirements (from `GET /tenant/policies/CASH_CUSTODY/effective`, cached encrypted; unknown policy or keys missing
  = not required; never read while `CASH_CUSTODY` is switched off):** `remittance_account_required` → an account must be
  chosen; `remittance_reference_required` → reference required for Bank deposit / Mobile money (never for cash to the
  office); `remittance_evidence_required` → at least one photo. Save stays disabled and the matching
  `field.remit.err*` line is shown under the form while a requirement is not met. Labels lose "(optional)" when
  required.
- **Photos:** in-app camera, at most 10, stored encrypted on the phone; uploaded by resumable blob upload with purpose
  `REMITTANCE_EVIDENCE`; each completed upload id is appended to the op's `evidence_upload_ids`; the op stays waiting
  (server answers DEFERRED `ATTACHMENT_PENDING`) until every photo is uploaded, like reading photos.
- **Sync status:** a CONFLICT/REJECTED item with one of the `field.conflict.*` codes below shows that sentence.
- **Overdue reason (both apps):** `RemittanceOverdueDto.reason` `CUTOFF` (default, as before) or `HELD_TOO_LONG`. For
  `HELD_TOO_LONG` the "Cut-off" row is hidden and "Held since" (`held_since`, date) and "Allowed" (`max_holding_days`)
  are shown; the footer line is `*.overdue.heldLine` instead of `*.overdue.line`. `{days}` text: "1 day" / "N days".
  A missing `held_since` / `max_holding_days` drops that row and uses `*.overdue.heldLineShort`.
- **Variance (Owner):** `CashVarianceDto.kind` `SURPLUS` (more received than declared) is labelled "Surplus to
  explain" with the positive amount; `SHORTFALL` or missing kind keeps today's wording.

Screens that change:
| App | Screen | Change |
|---|---|---|
| Supervisor | Hand over cash (Money "+" → Hand over cash) | Method, Paid into (account picker), reference wording, deposit slip photos, requirement lines |
| Supervisor | Sync status (outbox) | New conflict sentences; handover waiting for its photos |
| Supervisor | Overdue remittance | Reason, Held since, Allowed rows; held-too-long footer |
| Owner | Cash handover (remittance confirm) | Method, Paid into, Reference, deposit slip photos in the Handover card; method / account / reference repeated in the "Confirm received" dialog above "Amount received" |
| Owner | Cash write-off decision (variance) | "Surplus to explain" for SURPLUS |
| Owner | Overdue remittances (list) and Overdue remittance (detail) | Reason line per row; Reason, Held since, Allowed rows; held-too-long footer |

### Supervisor
| Key | English |
|---|---|
| field.remit.method | How was it handed over? |
| field.remit.methodCash | Cash to the office |
| field.remit.methodBank | Bank deposit |
| field.remit.methodMobile | Mobile money |
| field.remit.account | Paid into |
| field.remit.accountOptional | Paid into (optional) |
| field.remit.accountNone | No account |
| field.remit.accountsEmpty | Your company's accounts for this currency appear here after a sync. |
| field.remit.reference | Transaction reference |
| field.remit.referenceOptional | Reference (deposit slip, transaction no.) (optional) |
| field.remit.photos | Deposit slip or payment confirmation |
| field.remit.photosOptional | Deposit slip or payment confirmation (optional) |
| field.remit.photosFooter | Stored encrypted on this phone and uploaded before the handover is sent. |
| field.remit.photograph | Photograph the slip |
| field.remit.addPhoto | Add another photo |
| field.remit.removePhoto | Remove |
| field.remit.errAccount | Choose the company account the money was paid into. |
| field.remit.errReference | Enter the transaction reference of the bank deposit or mobile-money payment. |
| field.remit.errEvidence | Photograph the deposit slip or payment confirmation. |
| field.outbox.waitingPhotos | Waiting for its photos to upload |
| field.conflict.REMITTANCE_REFERENCE_REQUIRED | Your company requires the transaction reference for bank and mobile-money remittances. Record the handover again with the reference. |
| field.conflict.REMITTANCE_EVIDENCE_REQUIRED | Your company requires a photo of the deposit slip or payment confirmation. Record the handover again with a photo. |
| field.conflict.REMITTANCE_ACCOUNT_REQUIRED | Your company requires the account the money was paid into. Record the handover again and choose the account. |
| field.conflict.DEPOSIT_ACCOUNT_INACTIVE | The account you chose is no longer in use. Record the handover again with another account. |
| field.conflict.REMITTANCE_ACCOUNT_MISMATCH | The account you chose does not match how the money was handed over. Record the handover again. |
| field.conflict.DEPOSIT_ACCOUNT_CURRENCY_MISMATCH | The account you chose holds a different currency. Record the handover again with another account. |
| field.overdue.reason | Reason |
| field.overdue.reasonCutoff | Not remitted by the daily cut-off |
| field.overdue.reasonHeld | Held longer than allowed |
| field.overdue.heldSince | Held since |
| field.overdue.allowed | Allowed |
| field.overdue.days | {n} day / {n} days |
| field.overdue.heldLine | Held since {date}, longer than the allowed {days}. |
| field.overdue.heldLineShort | Held longer than allowed. |

"Overdue remittance" rows (in order): Cash held by, Not remitted, Reason, Day, Cut-off (CUTOFF only), Held since and
Allowed (HELD_TOO_LONG only), Flagged. Footer: the line for the reason, then `field.overdue.hint`.

### Owner
| Key | English |
|---|---|
| owner.remit.method | Method |
| owner.remit.methodCash | Cash to the office |
| owner.remit.methodBank | Bank deposit |
| owner.remit.methodMobile | Mobile money |
| owner.remit.account | Paid into |
| owner.remit.reference | Reference |
| owner.remit.photo | deposit slip photo {n} |
| owner.remit.noPhoto | No deposit slip photo |
| owner.variance.surplus | Surplus to explain |
| owner.row.surplus | Surplus to explain: {money} |
| owner.field.reason | Reason |
| owner.overdue.reasonCutoff | Not remitted by the daily cut-off |
| owner.overdue.reasonHeld | Held longer than allowed |
| owner.field.heldSince | Held since |
| owner.field.allowed | Allowed |
| owner.overdue.days | {n} day / {n} days |
| owner.overdue.heldLine | Held since {date}, longer than the allowed {days}. |
| owner.overdue.heldLineShort | Held longer than allowed. |

Owner details: the Handover card shows Method (null method = nothing shown, an older remittance), Paid into
(`deposit_account_name`, else short id), Reference, and one photo button per `evidence_attachment_ids` entry
("View deposit slip photo 1", online only; `GET /cash/handovers/{id}/evidence/{attachment_id}/url`), or
`owner.remit.noPhoto` when the handover has a method other than cash and no photo. The confirm dialog repeats Method,
Paid into and Reference as read-only lines above "Amount received". A SURPLUS write-off row reads
`owner.row.surplus` (amount without the minus sign) and its "Difference" field is labelled "Surplus to explain".
Overdue list rows show the amounts and, beneath, the reason text (`owner.overdue.reasonCutoff` / `reasonHeld`).

## DEC-031 Phase 1 — revenue (R1 non-revenue time, R2 daily machine sheet, R3 revenue differences)

Rules shared by both apps:
- **Online only.** No sync operations: every read and every action calls the API directly; offline the actions are
  disabled with the usual offline note (Owner) or `field.nonrev.offline` (Supervisor). Owner reads may be shown from
  the encrypted snapshot cache like every other Owner screen (stale banner as today).
- **Gate:** capability code `REVENUE_RECONCILIATION` (platform default **off**) not listed in `/me`
  `tenants[].disabled_capabilities` (Owner also: `AccountabilitySummaryDto.disabled_capabilities`), **and** the
  permission. Read = `tenant.revenue.read`; explain = `tenant.revenue.explain` (+ read, for the reason list); decide =
  `tenant.revenue.decide`. A missing permission hides the entry (an older server never grants these permissions, so
  nothing changes there). Switched off → every entry point below is hidden; a deep link of a revenue kind opens
  Approvals (Owner) / the notification (Supervisor).
- **Segregation:** the explainer (`explained_by` of a difference, `proposed_by` of a non-revenue approval) never
  decides it: buttons disabled with `*.rev.ownExplanation`; the server's `SEGREGATION_OF_DUTIES` refusal is shown
  as today.
- **Notes:** every explanation and decision needs a note of at least 5 characters (server `Note` min 5, max 2000).
- **Reasons:** `GET /revenue-reasons` (active only, sorted by name) feed a reason picker; empty list →
  `*.rev.reasonsEmpty` and the send button stays disabled.
- **Money / hours:** money with the money formatter in the record's currency; hours with the decimal formatter + ` h`;
  days as the local date (`26 Oct 2026`); periods `{from} – {to}` from `local_from` / `local_to` (one date when equal).
- **Wording:** neutral. A difference is "to explain", never an accusation.

Status wording (both apps):
| Wire | Revenue difference (`*.rev.status.*`) | Non-revenue time (`*.nonrev.status.*`) |
|---|---|---|
| OPEN / NONE | To explain | Counted as revenue until explained |
| EXPLANATION_PROPOSED / PROPOSED | Explanation waiting for a decision | Explained · waiting for approval |
| EXPLAINED / APPROVED | Explained | Approved as non-revenue time |
| CONFIRMED / REJECTED | Confirmed difference | Not approved · counted as revenue |
| CLEARED | Cleared (money arrived) | — |

Sheet flags (`*.sheet.flag.*`): MISSING_DAILY_REPORT "Daily report missing", UNEXPLAINED_HOURS "Unexplained hours",
ENGINE_ON_WITHOUT_JOB "Engine on without a job", FUEL_ABOVE_NORM "Fuel above norm", REVENUE_DIFFERENCE "Revenue
difference". Unknown flag → humanized wire value.

Screens that change:
| App | Screen | Change |
|---|---|---|
| Owner | Approvals | New sections "Revenue differences" (status OPEN + EXPLANATION_PROPOSED; OPEN rows only for explain or decide holders) and "Non-revenue hours" (PROPOSED), shown only when something waits |
| Owner | Revenue difference (new, from Approvals / dashboard / notification) | Figures, jobs, explanation, adjustments; Explain form (OPEN, explain holder); Approve / Reject / Confirm (decide holder, not the explainer) |
| Owner | Non-revenue hours decision (new, generic decision screen) | Machine, job, type, period, hours, reason, note; Approve / Reject with a note |
| Owner | Accountability dashboard | New tile "Revenue differences" (links to Approvals) |
| Owner | Machine | New row "Daily machine sheet" (read holder) |
| Owner | Daily machine sheet (new, list of the last 14 days, newest first) and Machine day (new) | Read-only |
| Owner | Deep links | kind `REVENUE_DIFFERENCE` / entity `revenue_difference` / `/tenant/revenue-differences/{id}` → Revenue difference; kind `NON_REVENUE_APPROVAL` / entity `non_revenue_approval` / `/tenant/non-revenue-approvals/{id}` → Non-revenue hours decision; `/tenant/revenue-differences`, `/tenant/non-revenue-approvals` → Approvals; `/tenant/engine-hours/daily-sheet` → Fleet |
| Supervisor | Job → Work log | Under each entry the server lists as non-revenue (`GET /non-revenue-activities?job_id=`, read online when the job opens and on pull to refresh; matched by the server activity id): its status line; "Explain" (explain holder, status NONE or REJECTED, online) |
| Supervisor | Explain non-revenue time (new form) | Entry summary, reason picker, note, Send |

### Owner
| Key | English |
|---|---|
| owner.rev.sectionDifferences | Revenue differences |
| owner.rev.sectionNonRevenue | Non-revenue hours |
| owner.rev.rowDifference | {money} to explain · {machine} |
| owner.rev.rowNonRevenue | {hours} h {type} · {machine} |
| owner.rev.titleDifference | Revenue difference |
| owner.rev.titleNonRevenue | Non-revenue hours |
| owner.rev.figures | Figures |
| owner.rev.machine | Machine |
| owner.rev.period | Period |
| owner.rev.job | Job |
| owner.rev.status | Status |
| owner.rev.expected | Expected revenue |
| owner.rev.inProgress | Work still in progress |
| owner.rev.attributed | Money attributed |
| owner.rev.difference | Difference |
| owner.rev.adjustedDifference | Difference after adjustments |
| owner.rev.customerWork | Customer-work hours |
| owner.rev.nonRevenueHours | Non-revenue hours |
| owner.rev.unexplainedHours | Unexplained hours |
| owner.rev.unexplainedExpected | Unexplained hours expected as revenue |
| owner.rev.case | Investigation |
| owner.rev.jobs | Jobs |
| owner.rev.jobLine | Expected {expected} · Attributed {attributed} |
| owner.rev.jobInProgress | In progress {money} |
| owner.rev.noJobs | No jobs in this period. |
| owner.rev.explanation | Explanation |
| owner.rev.reason | Reason |
| owner.rev.note | Note |
| owner.rev.explainedBy | Explained by |
| owner.rev.explained | Explained |
| owner.rev.decidedBy | Decided by |
| owner.rev.decisionNote | Decision note |
| owner.rev.adjustments | Adjustments |
| owner.rev.adjustmentLine | {date}: {previous} → {new} |
| owner.rev.explain | Explain this difference |
| owner.rev.explainFooter | Someone else decides on your explanation. |
| owner.rev.chooseReason | Choose a reason |
| owner.rev.reasonsEmpty | Your company has no revenue reasons yet. Add them on the web. |
| owner.rev.noteLabel | Note (at least 5 characters) |
| owner.rev.sendExplanation | Send explanation |
| owner.rev.explanationSent | Explanation sent. Someone else will decide. |
| owner.rev.decide | Decision |
| owner.rev.decideFooter | Approve or reject the explanation, or confirm the difference as money to recover. The person who explained it can't decide. |
| owner.rev.approve | Approve explanation |
| owner.rev.reject | Reject explanation |
| owner.rev.confirm | Confirm difference |
| owner.rev.confirmReject | Reject this explanation? The difference goes back to "To explain". |
| owner.rev.confirmConfirm | Confirm this difference? It stays recorded as money to recover. |
| owner.rev.approved | Explanation approved. |
| owner.rev.rejected | Explanation rejected. |
| owner.rev.confirmed | Difference confirmed. |
| owner.rev.ownExplanation | Someone else must decide on your explanation |
| owner.rev.status.OPEN | To explain |
| owner.rev.status.EXPLANATION_PROPOSED | Explanation waiting for a decision |
| owner.rev.status.EXPLAINED | Explained |
| owner.rev.status.CONFIRMED | Confirmed difference |
| owner.rev.status.CLEARED | Cleared (money arrived) |
| owner.nonrev.type | Type |
| owner.nonrev.hours | Hours |
| owner.nonrev.time | Time |
| owner.nonrev.footer | Approved time stops counting as revenue. The person who explained it can't approve it. |
| owner.dash.revenue | Revenue differences |
| owner.dash.revToExplain | To explain |
| owner.dash.revAwaiting | Awaiting a decision |
| owner.dash.revAmounts | Amount |
| owner.dash.revOldest | Oldest open |
| owner.dash.revExplained | Explained |
| owner.dash.revConfirmed | Confirmed |
| owner.dash.revCleared | Cleared |
| owner.dash.revItem | {machine} · {period} |
| owner.sheet.open | Daily machine sheet |
| owner.sheet.title | Daily machine sheet |
| owner.sheet.empty | No days with engine hours in the last 14 days. |
| owner.sheet.rowHours | Engine {engine} h · Revenue {revenue} h |
| owner.sheet.rowDifference | Difference {money} |
| owner.sheet.dayTitle | {machine} · {day} |
| owner.sheet.hours | Hours |
| owner.sheet.engine | Engine hours |
| owner.sheet.customerWork | Customer work |
| owner.sheet.nonRevenue | Non-revenue |
| owner.sheet.nonRevenuePending | Non-revenue awaiting approval |
| owner.sheet.revenue | Revenue hours |
| owner.sheet.approvedNonCustomer | Approved non-customer |
| owner.sheet.identifiedVariance | Identified difference |
| owner.sheet.unexplained | Unexplained |
| owner.sheet.pendingReview | Awaiting review |
| owner.sheet.readings | Readings |
| owner.sheet.firstReading | First reading |
| owner.sheet.lastReading | Last reading |
| owner.sheet.readingCount | Readings taken |
| owner.sheet.money | Money ({currency}) |
| owner.sheet.fuel | Fuel |
| owner.sheet.litres | {litres} L |
| owner.sheet.flags | Flags |
| owner.sheet.noFlags | No flags. |
| owner.sheet.flag.* | (see Sheet flags above) |
| owner.sheet.footer | Read-only. Figures come from the readings, jobs, invoices and prepaid hours of the day. |

Revenue difference screen order: Figures card (Machine, Period, Job when `job_id`, Status pill, Expected revenue,
Work still in progress (only when non-zero), Money attributed, Difference, Difference after adjustments (only when
`adjusted_difference`), Customer-work hours, Non-revenue hours, Unexplained hours, Unexplained hours expected as
revenue (both only when non-zero), Investigation (`case_number`, only when `case_id`)); Jobs card (`detail.jobs` of
the difference's currency: row `{job number}` + `owner.rev.jobLine`, `owner.rev.jobInProgress` appended when
non-zero); Explanation card (when `reason_id` or `explained_by`); decided fields (when `decided_by`); Adjustments card
(when any, newest first); then the action card: Explain (status OPEN and explain holder) and/or Decision (decide
holder: OPEN → Confirm only; EXPLANATION_PROPOSED → Approve, Reject, Confirm). When both cards show (OPEN, user holds
explain and decide) they share the one note field of the Explain card. Reject and Confirm ask first
(`owner.rev.confirmReject` / `owner.rev.confirmConfirm`). Headline amount = `adjusted_difference` when present, else
`difference`. Approvals rows: headline `owner.rev.rowDifference` (machine code, else name, else short id); subtitle
`{period} · {status wording}`; footnote "Proposed {time} by {explainer}" only once explained. Non-revenue rows: headline
`owner.rev.rowNonRevenue` (type humanized, hours to 2 dp without trailing zeros); subtitle `reason_name` (else the note);
footnote "Proposed {time} by {name}".

Non-revenue hours decision uses the generic decision screen: fields Machine, Job, Type, Time (`started_at – ended_at`),
Hours, Reason (`reason_name`), Note (the explanation), Proposed by, Decided by, Decision note; note at least 5
characters for both Approve and Reject; footer `owner.nonrev.footer`.

Dashboard tile rows: To explain `{open}`, Awaiting a decision `{awaiting_decision}`, Amount (amounts as
"`{count} · {money}`" joined by ", ", or "None"), Oldest open (`{n} days`, row hidden when null), Explained / Confirmed /
Cleared (`*_in_window`), then one row per item `owner.dash.revItem` → difference money; footer "Last {window_days}
days"; link → Approvals.

Daily machine sheet: `GET /daily-machine-sheet?machine_id=&day_from=&day_to=` for the last 14 local days (today
included), newest first. Row: the day (headline), `owner.sheet.rowHours`, `owner.sheet.rowDifference` per currency with a
non-zero difference, flags joined by " · " (warning colour). Tap → Machine day (`GET
/daily-machine-sheet/{machine_id}/{day}`): Hours card (rows in the key order above; each non-revenue type as
"Non-revenue · {Type}"; zero rows other than Engine / Revenue hidden), Readings card (first, last, count, then each
reading `{time} · {reading} · {kind}`), Jobs card (`{job number} · {customer}` → `{customer work} h`), one Money card per
currency (Expected revenue, Work still in progress, Money attributed, Difference, Unexplained hours expected as revenue
when non-zero), Fuel (`owner.sheet.litres`), Flags (or `owner.sheet.noFlags`); footer `owner.sheet.footer`.

### Supervisor
| Key | English |
|---|---|
| field.nonrev.status.NONE | Counted as revenue until explained |
| field.nonrev.status.PROPOSED | Explained · waiting for approval |
| field.nonrev.status.APPROVED | Approved as non-revenue time |
| field.nonrev.status.REJECTED | Not approved · counted as revenue |
| field.nonrev.explain | Explain |
| field.nonrev.title | Explain non-revenue time |
| field.nonrev.entry | Work log entry |
| field.nonrev.entryLine | {type} · {start} → {end} ({hours} h) |
| field.nonrev.reason | Reason |
| field.nonrev.chooseReason | Choose a reason |
| field.nonrev.reasonsEmpty | Your company has no revenue reasons yet. Ask the office. |
| field.nonrev.note | Note (at least 5 characters) |
| field.nonrev.send | Send |
| field.nonrev.footer | This time counts as revenue until someone else approves it. Needs a connection. |
| field.nonrev.sent | Sent. Someone else will approve it. |
| field.nonrev.offline | Explaining needs a connection. |
| field.nonrev.err.NON_REVENUE_PENDING | This time is already waiting for approval. |
| field.nonrev.err.NON_REVENUE_APPROVAL_NOT_REQUIRED | Your company does not need approval for this time. |
| field.nonrev.err.REVENUE_RECONCILIATION_DISABLED | Your company has switched off revenue checks. |
| field.nonrev.err.REASON_INACTIVE | This reason is no longer in use. Choose another. |

Supervisor details: the status line is a caption under the work-log entry (warning colour for NONE / REJECTED, accent
for PROPOSED, live for APPROVED); "Explain" is a small text button on the same line, shown only to explain holders for
NONE / REJECTED and disabled offline. Other refusals show the server message. After sending, the form closes and the
work log re-reads the statuses.

## DEC-031 Phases 2 and 4 — engine running without work, fuel per engine hour, prepaid hours over days

Rules shared by both apps:
- **Online only, read-only.** No new sync operations. Owner reads go through the snapshot cache like every other
  Owner screen (stale banner as today). Nothing here is decided in the apps.
- **Gates.** Phase 2 additions live on screens that already exist (daily machine sheet: `REVENUE_RECONCILIATION` +
  `tenant.revenue.read`; Investigation: `tenant.case.read`). Customer hours screens need `tenant.hours.read` and the
  capability `CUSTOMER_HOURS` not switched off (the existing Owner `customerHours` feature); otherwise the entry is
  hidden and a customer-hours deep link opens the Accountability dashboard (as today).
- **Hours:** decimal formatter (2 dp, no trailing zeros) + ` h`; litres per engine hour with 2 dp. `provisional` is
  already taken out of `remaining` by the server: it is shown beside it, never subtracted again. A provisional
  figure of zero is not shown.
- **Days / periods:** local date (`26 Oct 2026`); periods `{from} – {to}`.

Screens that change:
| App | Screen | Change |
|---|---|---|
| Owner | Machine day (daily machine sheet) | Fuel card gains "Litres per engine hour" (`fuel_litres_per_engine_hour`, row hidden when null). Flags card: one "Open investigation" row per distinct `flag_records[]` entry with `record_type` `anomaly_case` → Investigation (existing screen, `/tenant/cases/{id}`); hidden without `tenant.case.read` |
| Owner | Investigation (case detail) | Signal names: `ENGINE_RUNNING_WITHOUT_WORK`, `MACHINE_FUEL_ABOVE_NORM` worded below; other codes humanized as today |
| Owner | More | New entry "Customer hours" (customer-hours gate) |
| Owner | Customer hours (new list) | `GET /hours-purchases?cancelled=false&page_size=100`, purchases with hours left or in use, newest first. Row: headline `{purchase number} · {customer}`, subtitle machine, line `owner.hours.left` + `owner.hours.inUse` when provisional > 0 |
| Owner | Hours purchase (new, read-only) | `GET /hours-purchases/{id}`: Hours card, Machines card (only when the hours are on more than one machine), then "Hours statement" row → Customer hours statement of that customer; footer `owner.hours.provisionalFooter` |
| Owner | Customer hours statement (new, read-only) | `GET /customers/{id}/hours-statement?date_from&date_to`: period chips, Totals card, Usage card, "Open PDF" (`GET …/hours-statement.pdf`, same query, saved to the app cache and opened in the phone's PDF viewer) |
| Owner | Deep links | kind `HOURS_PURCHASE` + `record_id` (HOURS_LOW_BALANCE, HOURS_EXPIRING, HOURS_EXPIRED), entity `hours_purchase`, path `/tenant/hours/purchases/{id}` → Hours purchase; `/tenant/hours/purchases` → Customer hours |
| Supervisor | Request hours transfer | Purchase picker row and the hours shown for the chosen purchase add `field.hours.inUse` when provisional > 0 |

### Owner
| Key | English |
|---|---|
| owner.sheet.litresPerHour | Litres per engine hour |
| owner.sheet.litresPerHourValue | {litres} L/h |
| owner.sheet.openCase | Open investigation |
| owner.signal.ENGINE_RUNNING_WITHOUT_WORK | Engine running without work during the day |
| owner.signal.MACHINE_FUEL_ABOVE_NORM | Fuel above the norm for the engine hours |
| owner.hours.more | Customer hours |
| owner.hours.listTitle | Customer hours |
| owner.hours.empty | No prepaid hours with hours left. |
| owner.hours.listFooter | Prepaid hours with hours left or in use by running jobs. Selling and moving hours is done in the field app or on the web. |
| owner.hours.row | {purchase} · {customer} |
| owner.hours.left | {hours} h left |
| owner.hours.inUse | {hours} h in use by running jobs |
| owner.hours.purchaseTitle | Hours purchase |
| owner.hours.hours | Hours |
| owner.hours.customer | Customer |
| owner.hours.machine | Machine |
| owner.hours.status | Status |
| owner.hours.bought | Bought |
| owner.hours.activated | Activated |
| owner.hours.used | Used |
| owner.hours.provisional | In use by running jobs |
| owner.hours.transferred | Moved to other machines |
| owner.hours.expired | Expired |
| owner.hours.remaining | Left |
| owner.hours.awaiting | Awaiting activation |
| owner.hours.machines | Machines |
| owner.hours.machineLine | {left} |
| owner.hours.openStatement | Hours statement |
| owner.hours.provisionalFooter | Hours in use by running jobs are drawn day by day and become final when the job is completed. |
| owner.hours.status.AWAITING_PAYMENT | Awaiting payment |
| owner.hours.status.PARTLY_ACTIVE | Partly active |
| owner.hours.status.ACTIVE | Active |
| owner.hours.status.CONSUMED | Used up |
| owner.hours.status.EXPIRED | Expired |
| owner.hours.status.CANCELLED | Cancelled |
| owner.stmt.title | Hours statement |
| owner.stmt.header | {customer} · {period} |
| owner.stmt.period.THIS_MONTH | This month |
| owner.stmt.period.LAST_MONTH | Last month |
| owner.stmt.period.LAST_3_MONTHS | Last 3 months |
| owner.stmt.period.THIS_YEAR | This year |
| owner.stmt.totals | Totals |
| owner.stmt.opening | Opening balance |
| owner.stmt.bought | Bought |
| owner.stmt.activated | Activated |
| owner.stmt.used | Used |
| owner.stmt.provisionalAtClose | Of which in use by running jobs |
| owner.stmt.transferredIn | Moved in |
| owner.stmt.transferredOut | Moved out |
| owner.stmt.expired | Expired |
| owner.stmt.cancelled | Cancelled |
| owner.stmt.closing | Closing balance |
| owner.stmt.awaiting | Awaiting activation (now) |
| owner.stmt.usage | Hours used |
| owner.stmt.usageEmpty | No hours used in this period. |
| owner.stmt.usageRow | {day} · {job} |
| owner.stmt.basis.DAILY | Drawn day by day |
| owner.stmt.basis.FINAL | Final |
| owner.stmt.running | Job still running |
| owner.stmt.openPdf | Open PDF |
| owner.stmt.pdfFailed | Could not get the PDF. Check your connection and try again. |
| owner.stmt.noPdfApp | No app on this phone can open PDFs. |
| owner.stmt.footer | Times are in {timezone}. Generated {time}. |

Purchase status: unknown wire → humanized. Hours card order: Customer, Machine, Status, Bought, Activated, Used, In
use by running jobs (only when > 0), Moved to other machines (only when > 0), Expired (only when > 0), Left, Awaiting
activation (only when > 0). Machines card row: label = machine code (else name, else short id), value
`owner.hours.left` + " · " + `owner.hours.inUse` when that machine's provisional > 0.

Statement: default chip This month (first of the month – today, local). Last month = whole previous month; Last 3
months = first day of the month two months back – today; This year = 1 Jan – today. Header `owner.stmt.header`
(customer name from the statement, else the purchase's). Totals rows in the key order above; Of which in use by
running jobs, Moved in, Moved out, Expired, Cancelled and Awaiting activation only when > 0. Usage rows newest day
first: label `owner.stmt.usageRow` (job number, else "—"), value `{hours} h`, caption = machine · basis wording,
plus " · " + `owner.stmt.running` when `job_running`. Server refusals (`INVALID_PERIOD`, `PERIOD_TOO_LONG`) show the
server message. Open PDF is disabled offline; a failed download shows `owner.stmt.pdfFailed` (or the server message).

### Supervisor
| Key | English |
|---|---|
| field.hours.purchaseOption | {purchase} · {hours} h left |
| field.hours.inUse | {hours} h in use by running jobs |

Picker row: `field.hours.purchaseOption` + " · " + `field.hours.inUse` when the purchase's provisional > 0. Under the
"From machine" field, when the chosen purchase has provisional hours on that machine, a caption
`field.hours.inUse` (secondary colour). The transfer limit stays `remaining` (provisional hours are already taken
out of it and cannot be moved).

## DEC-031 Phase 5 — oversight

Rules shared by both apps:
- **Gates.** Supervisor site check-in: sync capability `OP_SITE_CHECKIN` (announced only while
  `OVERSIGHT.site_checkin_required`) + `tenant.site_checkin.record` + capability `SITE_CHECKIN` not in `/me`
  `disabled_capabilities`. Owner People scorecard: `tenant.oversight.scorecard.read` + `SCORECARD` not switched off.
  Owner Unbilled work / Idle machines lists: `tenant.oversight.read` + `UNBILLED_WORK` / `IDLE_MACHINES` not switched
  off (the dashboard tiles come from the summary as before; the tile's link is shown only when the list is allowed).
- **Neutral wording.** Scorecard figures are "items to look at", never a verdict.
- **Days:** `1 day` / `{n} days`. Dates `26 Oct 2026`, times `14:05` (24 h); date-time `26 Oct 2026, 14:05`.
- **Hours (parity fix, both apps, every customer-hours screen and the Supervisor hours picker):** the phone's locale
  number format with grouping, 0–2 decimals, no trailing zeros, then ` h` — `12 h left`, `1,234.5 h`, never `12.00 h`
  or `12.0000 h left`. Android: `OwnerFormat.hoursNumber` (Owner) / the same rule in the Supervisor picker; iOS:
  `OwnerFormat.hours` style (`.number.precision(.fractionLength(0...2)).locale(.current)`) also for the `{hours}` inside
  `owner.hours.left`, `owner.hours.inUse`, `field.hours.purchaseOption`, `field.hours.inUse`.
- **No local reminder at slot time:** neither app has local (scheduled) notification infrastructure today, so the
  slot reminder is not built; the due slot is shown on the Jobs tab instead. Server reminders, if added later, arrive
  as normal push notifications.

Screens that change:
| App | Screen | Change |
|---|---|---|
| Supervisor | Jobs tab | Row "Site check-in" under the banners (check-in gate): subtitle `field.checkin.due` when a slot is due, else `field.checkin.next`, else `field.checkin.noneLeft`; opens Site check-ins |
| Supervisor | Site check-ins (new) | `GET /site-checkins/mine` online (saved encrypted for offline). Today card: one row per today's slot (time, status); "Check in now" button; My check-ins card (this phone's queued check-ins + the server's, newest first); footer |
| Supervisor | Check in now | One fresh GPS attempt (same as meter readings; failure recorded without coordinates), then queued as sync op `SITE_CHECKIN {client_id, captured_at, gps}` (no `job_site_id`: the server takes the running job's site). Works offline |
| Supervisor | Sync status / Inbox needs attention | Title `field.checkin.outbox`; refusals in plain words (codes below) |
| Owner | More | New entry "People scorecard" (scorecard gate), after Customer hours |
| Owner | People scorecard (new) | Period chips; rows sorted by `items_total` (most first, then name). Row: headline name (`DisplayNames`, else short id), subtitle `owner.score.items`, caption = the non-zero figures joined with " · " (max 3) |
| Owner | Person (new, read-only) | `GET /scorecard/{staff_member_id}?day_from&day_to`: Figures card, Cash held now card (only when any), Records card (newest first). A record opens the existing screen when the app has one and the role may open it; otherwise its details show in the row |
| Owner | Accountability dashboard | Tiles `unbilled_work` and `idle_machines` (rows below); link to the list when allowed |
| Owner | Unbilled work (new, read-only) | `GET /unbilled-work?page_size=100`; row opens the Job (when the role reads jobs) |
| Owner | Idle machines (new, read-only) | `GET /idle-machines?page_size=100`; row opens the Machine (when the role reads the fleet) |
| Owner | Investigation | Signal `REPEATED_PATTERN` worded below |
| Owner | Deep links | notification `data.kind` `JOB` + `record_id` (UNBILLED_WORK) → Job; `/tenant/scorecard` → People scorecard; `/tenant/unbilled-work` → Unbilled work; `/tenant/idle-machines` → Idle machines (each falls back to the Accountability dashboard when its gate is closed) |

### Supervisor
| Key | English |
|---|---|
| field.checkin.entry | Site check-in |
| field.checkin.title | Site check-ins |
| field.checkin.due | Check-in due now, until {time} |
| field.checkin.next | Next check-in at {time} |
| field.checkin.noneLeft | No more check-ins today |
| field.checkin.today | Today |
| field.checkin.todayEmpty | No check-ins are scheduled for you today. |
| field.checkin.window | Between {from} and {to} |
| field.checkin.status.MADE | Checked in |
| field.checkin.status.MISSED | Missed |
| field.checkin.status.DUE | Due now |
| field.checkin.status.UPCOMING | Upcoming |
| field.checkin.status.SAVED | Saved on this phone |
| field.checkin.action | Check in now |
| field.checkin.locating | Getting your location… |
| field.checkin.saved | Check-in saved. It is sent when the phone is online. |
| field.checkin.footer | Your company asks you to check in at the site at these times. Your location is recorded with each check-in. Check-ins are saved on the phone and sent when you are online. |
| field.checkin.distanceFooter | Check in within {metres} m of the site. |
| field.checkin.mine | My check-ins |
| field.checkin.mineEmpty | No check-ins in the last 7 days. |
| field.checkin.noSite | No site |
| field.checkin.distance | {metres} m from the site |
| field.checkin.outside | Further from the site than allowed |
| field.checkin.noLocation | Recorded without location |
| field.checkin.waiting | Waiting to sync |
| field.checkin.notAccepted | Not accepted |
| field.checkin.savedAt | Schedule from {time}. Connect to update it. |
| field.checkin.never | Your check-in times appear here after you connect. |
| field.checkin.outbox | Site check-in |
| field.checkin.conflict.SITE_CHECKIN_DISABLED | Your company has switched off site check-ins, so this check-in was not accepted. |
| field.checkin.conflict.CHECKIN_ID_CONFLICT | This check-in could not be saved because its id is already used. Check in again. |
| field.checkin.conflict.STAFF_NOT_LINKED | Your account is not linked to a staff record, so check-ins cannot be saved. Ask the office. |
| field.checkin.conflict.CHECKIN_IN_FUTURE | The phone's clock is ahead, so this check-in was not accepted. Correct the phone's time and check in again. |
| field.checkin.conflict.JOB_SITE_NOT_FOUND | The site of this check-in no longer exists. Check in again. |

Slots: today's (tenant timezone from the response) slots in time order, label `HH:mm`, caption `field.checkin.window`
(scheduled − window … scheduled + window). Status is recomputed on the phone from the saved slots: MADE when the
server says so or a check-in saved on this phone falls inside the window (then `field.checkin.status.SAVED` until
the server confirms), else MISSED when the window has ended, DUE while it is open, UPCOMING before. "Check in now" is
always offered (the server matches it to a slot). My check-ins rows: label date-time, value site name
(`field.checkin.noSite` when none), caption: `field.checkin.distance` (+ " · " + `field.checkin.outside` when
`within_distance` is false) or `field.checkin.noLocation` when GPS was not FIX; this phone's not-yet-acked rows show
`field.checkin.waiting`, refused ones `field.checkin.notAccepted` + the conflict wording. Footer `field.checkin.footer`
(+ `field.checkin.distanceFooter` when `max_distance_m` is set) and `field.checkin.savedAt` when shown from the saved
copy.

### Owner
| Key | English |
|---|---|
| owner.score.more | People scorecard |
| owner.score.title | People scorecard |
| owner.score.period.LAST_7_DAYS | Last 7 days |
| owner.score.period.LAST_30_DAYS | Last 30 days |
| owner.score.period.THIS_MONTH | This month |
| owner.score.period.LAST_MONTH | Last month |
| owner.score.empty | No one to show for this period. |
| owner.score.footer | Counts of items to look at for each person, most first. A count is not a verdict: open the person to see each record. |
| owner.score.items.0 | Nothing to look at |
| owner.score.items.1 | 1 item to look at |
| owner.score.items.n | {n} items to look at |
| owner.score.inactive | Inactive |
| owner.score.figures | Figures |
| owner.score.period | Period |
| owner.score.machines | Machines responsible for |
| owner.score.reportsMissing | Daily reports missing |
| owner.score.reportsLate | Daily reports late |
| owner.score.unexplained | Unexplained engine hours |
| owner.score.unexplainedValue | {hours} h · {n} items |
| owner.score.alerts | Alerts |
| owner.score.alertsValue | {n} · {open} open |
| owner.score.ackTime | Time to acknowledge |
| owner.score.ackTimeValue | average {avg} h · longest {max} h |
| owner.score.cashHeldTooLong | Cash held too long |
| owner.score.cashDifferences | Cash differences |
| owner.score.nearThreshold | Near the case threshold |
| owner.score.revenueDifferences | Revenue differences |
| owner.score.refused | Refused attempts |
| owner.score.checkins | Site check-ins |
| owner.score.checkinsValue | {made} made · {missed} missed |
| owner.score.patterns | Repeated patterns |
| owner.score.cashHeld | Cash held now |
| owner.score.heldSince | since {date} ({days}) |
| owner.score.records | Records |
| owner.score.recordsEmpty | No records in this period. |
| owner.score.item.MISSING_DAILY_REPORT | Daily report missing |
| owner.score.item.LATE_DAILY_REPORT | Daily report late |
| owner.score.item.UNEXPLAINED_HOURS | Unexplained engine hours |
| owner.score.item.ALERT | Alert |
| owner.score.item.CASH_HELD_TOO_LONG | Cash held too long |
| owner.score.item.CASH_DIFFERENCE | Cash difference |
| owner.score.item.REVENUE_DIFFERENCE | Revenue difference |
| owner.score.item.REFUSED_ATTEMPT | Refused attempt |
| owner.score.item.MISSED_CHECKIN | Missed site check-in |
| owner.score.item.PATTERN_SIGNAL | Repeated pattern |
| owner.score.scheduled | Scheduled {time} |
| owner.dash.unbilled | Unbilled work |
| owner.dash.unbilledJobs | Jobs |
| owner.dash.unbilledValue | Value |
| owner.dash.oldest | Oldest |
| owner.dash.unbilledFooter | Completed jobs not on an issued invoice after {days}. |
| owner.dash.idle | Idle machines |
| owner.dash.idleMachines | Machines |
| owner.dash.longestIdle | Longest idle |
| owner.dash.idleFooter | Machines with no running job and no engine hours for {days}. |
| owner.unbilled.title | Unbilled work |
| owner.unbilled.empty | No completed jobs waiting for an invoice. |
| owner.unbilled.row | {job} · {customer} |
| owner.unbilled.completed | Completed {date} · {days} unbilled |
| owner.unbilled.draft | On a draft invoice |
| owner.unbilled.footer | Completed jobs not on an issued invoice yet. Invoices are made on the web. |
| owner.idle.title | Idle machines |
| owner.idle.empty | No idle machines. |
| owner.idle.since | Idle since {date} ({days}) |
| owner.idle.lastJob | Last job {job} completed {date} |
| owner.idle.planned | Planned job {job} |
| owner.idle.footer | Machines with no running job and no engine hours for a while. |
| owner.signal.REPEATED_PATTERN | Repeated items to look at for one person |

Scorecard periods (local days, ≤ 93): Last 7 days = today − 6 … today; Last 30 days (default) = today − 29 … today;
This month = 1st … today; Last month = the whole previous month. List caption figures, in this order, only when > 0:
`{n} missing reports`, `{n} late reports`, `{h} h unexplained`, `{n} open alerts`, `{n} cash held too long`,
`{n} cash differences`, `{n} revenue differences`, `{n} refused attempts`, `{n} missed check-ins`, `{n} repeated
patterns` (first three shown). Inactive people add `owner.score.inactive` to the subtitle.

Person Figures rows (in this order): Period (`{from} – {to}`), Machines responsible for, Daily reports missing, Daily
reports late, Unexplained engine hours (`owner.score.unexplainedValue`), Alerts (`owner.score.alertsValue`), Time to
acknowledge (only when `avg_hours_to_acknowledge` is set), Cash held too long, Cash differences (count, then " · " +
each currency total in money format), Near the case threshold (only when > 0), Revenue differences (count + totals),
Refused attempts, Site check-ins (only when `checkins_missed` is not null), Repeated patterns. Cash held now: label =
money, value `owner.score.heldSince` (just the money when `held_since` is null).

Record rows: label `owner.score.item.*` (unknown → humanized), value = money (`amount` + `currency`) or `{hours} h`
when set, caption = local day · machine (code, else name) · job number · humanized status, plus
`owner.score.nearThreshold` when `near_threshold`, the alert `detail.title`, `owner.score.scheduled` for a missed
check-in, `detail.action` / `detail.permission` for a refused attempt. Opens: `job_exception` → Meter exception
(`tenant.meter.read`), `tracking_alert` → Alert (`tenant.fleet.read`), `cash_remittance_overdue` → Overdue remittance
(`tenant.finance.read` and cash custody on), `cash_variance` → the write-off decision, `revenue_difference` → Revenue
difference (`tenant.revenue.read`), `risk_signal` → Investigation `detail.case_id` (`tenant.case.read`),
`engine_interval` → Machine (`tenant.fleet.read`); `security_event` and `site_checkin_slot` do not open.

Dashboard tiles (from the summary; hidden when null or the capability is switched off): Unbilled work rows Jobs
(`count`), Value (each `amounts[]` money, joined ", "; "None" when empty), Oldest (`oldest_days` as days, row hidden
when null), footer `owner.dash.unbilledFooter` with `after_days` (hidden when null). Idle machines rows Machines
(`count`), Longest idle (`longest_idle_days`), footer `owner.dash.idleFooter` with `after_days`.

Unbilled work rows (newest completion last → sort by `days_unbilled` descending): headline `owner.unbilled.row`
(job number else "—", customer name else short id), subtitle machine · site name (when set), caption
`owner.unbilled.completed` + " · " + `owner.unbilled.draft` when `draft_invoice_id`, trailing value total money
(when set). Idle machines rows (longest idle first): headline machine, caption `owner.idle.since`, second caption
`owner.idle.lastJob` (when a last job) and `owner.idle.planned` (when a planned job).

## Go-live checklist

Owner app only (the Supervisor app shows nothing). Backend contract: `GET /api/v1/tenant/setup-checklist`
(`SetupChecklistDto`), writes return the checklist. Online only: nothing is queued; the last checklist is kept as the
usual offline snapshot (read-only, actions disabled while it is shown).

Rules shared by both apps:
- **Gates.** Read: `tenant.setup.read`. Mark as not needed / Undo / "Our default controls are fine":
  `tenant.setup.manage` + online + live data + company not read-only (the standard mutation gate and its wording).
- **Banner** on the Overview (dashboard), above the sections: shown when `/me` tenant `setup_steps_total` is not null
  (null = no `tenant.setup.read`), `setup_complete` is false and `setup_dismissed` is false. Text `owner.setup.banner`
  with `setup_steps_done` / `setup_steps_total`, caption `owner.setup.bannerCaption`; tap → Go-live checklist. The
  figures are replaced by those of the checklist whenever the checklist is loaded or changed in this session (so the
  banner disappears when it becomes complete or is dismissed), without re-reading `/me`.
- **More**: entry `owner.setup.more`, first in the list, while `tenant.setup.read`.
- **Deep link** `/tenant/setup` → Go-live checklist (Overview when not allowed).
- **Step action** (one per step; also on each sub-check row that is not done): the Owner app screen when the link
  maps to one the role may open, else `owner.setup.openWeb`, which opens the configured web base URL (Android build
  config `WEB_BASE_URL`, defaulting to the API base URL; release `https://asseta.co.tz`) + the link in the browser.
  Link → app screen (path before `?`; anything else → web):
  | Link | App screen (label `owner.setup.openScreen` with the screen title) | Needs |
  |---|---|---|
  | `/tenant/machines` (no query) | Fleet | `tenant.fleet.read` |
  | `/tenant/jobs` | Jobs | `tenant.job.read` |
  | `/tenant/approvals`, `/tenant/meter-baselines` (any query) | Approvals | `tenant.approval.read` |
  | `/tenant/hours`, `/tenant/hours/purchases` | Customer hours | customer hours gate |
  | `/tenant/finance/cash` (no query) | Cash with supervisors | `tenant.finance.read` |
  `/tenant/machines?missing=…`, `/tenant/finance/cash?tab=reasons`, `/tenant/hours/reasons` and all other links → web.
  Done steps show no action. When the user lacks the step's `required_permission`, the caption
  `owner.setup.needsAccess` is added (the action is still offered).

Screens:
| App | Screen | Change |
|---|---|---|
| Owner | Overview | Go-live banner (rules above) |
| Owner | More | Entry "Go-live checklist" |
| Owner | Go-live checklist (new) | Pull to refresh. Progress card: `owner.setup.progress` (+ linear progress of `percent`), `owner.setup.complete` when complete, `owner.setup.asOf`. Then one card per step in `order`: title `{order}. {title}` + status pill, description, counts row `owner.setup.count` when `total_count` is not null, the sub-checks (label, ✓ done / `owner.setup.checkTodo`, `owner.setup.count` when counted, `owner.setup.optional` when optional; a not-done check opens its own link), the not-needed note, the controls-confirmed note (CONTROLS_CHOSEN), the action, then the manage buttons. Footer `owner.setup.footer` |
| Owner | Mark as not needed (dialog) | Reason field (3–500 characters, trimmed), Cancel / confirm; `POST /steps/{key}/not-needed {reason}` |
| Owner | Undo | `DELETE /steps/{key}/not-needed` (no confirmation) |
| Owner | Our default controls are fine (dialog) | Optional note (≤500); `POST /confirm-controls {note}` |

Manage buttons (only with the manage gate open; otherwise the gate's `BlockedNote` reason once at the top of the
list, only for holders of `tenant.setup.manage`): `owner.setup.markNotNeeded` when `can_mark_not_needed` and status
TODO; `owner.setup.undo` when status NOT_NEEDED; `owner.setup.controlsFine` on step CONTROLS_CHOSEN while its status is
TODO and `controls_confirmed_at` is null. Status NOT_APPLICABLE steps stay in their place in the order, muted,
without actions. Refusal codes: `SETUP_STEP_REQUIRED` → `owner.setup.error.SETUP_STEP_REQUIRED`; others → the
standard wording. After a write the returned checklist replaces the screen and the banner figures.

### Owner
| Key | English |
|---|---|
| owner.setup.banner | Get ready to go live — {done} of {total} done |
| owner.setup.bannerCaption | Open the go-live checklist to see what is left. |
| owner.setup.more | Go-live checklist |
| owner.setup.title | Go-live checklist |
| owner.setup.progress | {done} of {total} done |
| owner.setup.complete | Everything is ready. You can go live. |
| owner.setup.asOf | Checked {dateTime} |
| owner.setup.footer | Each step is checked against your company's records and updates by itself as the work is done. Most steps are done on the web. |
| owner.setup.status.DONE | Done |
| owner.setup.status.TODO | To do |
| owner.setup.status.NOT_NEEDED | Not needed |
| owner.setup.status.NOT_APPLICABLE | Does not apply |
| owner.setup.count | {done} of {total} |
| owner.setup.checkDone | Done |
| owner.setup.checkTodo | To do |
| owner.setup.optional | Optional |
| owner.setup.openScreen | Open {screen} |
| owner.setup.openWeb | Open on the web |
| owner.setup.needsAccess | Someone with access to this screen must do this step. |
| owner.setup.markNotNeeded | Mark as not needed |
| owner.setup.notNeededTitle | Mark "{step}" as not needed? |
| owner.setup.notNeededReason | Why this step does not apply |
| owner.setup.notNeededHint | At least 3 characters. |
| owner.setup.notNeededBy | Marked not needed by {name} on {date}: {reason} |
| owner.setup.undo | Undo |
| owner.setup.controlsFine | Our default controls are fine |
| owner.setup.controlsTitle | Keep the default controls? |
| owner.setup.controlsMessage | Asseta's default controls stay in place. You can change them on the web at any time. |
| owner.setup.controlsNote | Note (optional) |
| owner.setup.controlsConfirm | Keep the defaults |
| owner.setup.controlsBy | Controls confirmed by {name} on {date} |
| owner.setup.cancel | Cancel |
| owner.setup.error.SETUP_STEP_REQUIRED | This step is needed before going live, so it cannot be marked as not needed. |

`{name}` is the `*_by_name` (else "someone"); `{date}` the local date `26 Oct 2026`; `{dateTime}` `26 Oct 2026, 14:05`;
`{reason}` omitted together with its ": " when null. `{screen}` is the app's screen title (Fleet, Jobs, Approvals,
Customer hours, Cash with supervisors).
