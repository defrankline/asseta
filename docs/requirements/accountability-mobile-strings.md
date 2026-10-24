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
