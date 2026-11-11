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
| field.hours.total | Total: {amount} ({hours} h × {rate}/h) |
| field.hours.totalDiscount | Total: {amount} ({hours} h × {rate}/h less {percent}% discount) |
| field.hours.priceLater | The price is set when the sale reaches the office. |
| field.hours.sectionPayment | Payment |
| field.hours.notPaid | Not paid yet |
| field.hours.addPayment | Add payment |
| field.hours.removePayment | Remove payment |
| field.hours.paymentNumber | Payment {n} |
| field.hours.method | Method |
| field.hours.paidOf | Paid {paid} of {total} · Balance {balance} |
| field.hours.paidNoTotal | Paid {paid} |
| field.hours.fullyPaid | Fully paid |
| field.hours.partPaid | Part paid (balance {balance}) |
| field.hours.noncashByOffice | Bank and mobile-money payments are recorded by the office. |
| field.hours.linePhoto | Photo of the slip or message (optional) |
| field.hours.referenceLine | Enter the reference for this payment |
| field.hours.toSave | To save: {todo}[, {todo}…] and {todo}. |
| field.hours.toSaveRegistered | choose a registered customer |
| field.hours.toSaveName | enter the customer's name |
| field.hours.toSavePhone | fix the phone number (at least 3 characters) |
| field.hours.toSaveCustomer | choose the customer |
| field.hours.toSaveMachine | choose the machine |
| field.hours.toSaveHours | enter the hours (more than 0) |
| field.hours.toSaveTooMany | remove payments (at most 10) |
| field.hours.toSaveAmount | enter the amount for {payments} |
| field.hours.toSaveCash | change {payments} to cash |
| field.hours.toSaveReference | enter the reference for {payments} |
| field.hours.toSaveLower | lower the payments to the total of {total} |
| field.hours.toSavePayments | payment {n} / payments {n} and {m} / payments {n}, {m} and {k} |
| field.hours.outbox | Hours sale · {method} {amount}[ + {method} {amount}…] (no payment: "Hours sale · Not paid yet") |
| field.hours.methodCash | Cash |
| field.hours.methodBank | Bank |
| field.hours.methodMobileMoney | Mobile money |
| field.hours.amountReceived | Amount received |
| field.hours.reference | Reference (required for bank and mobile money) |
| field.hours.received | Received |
| field.hours.paymentFooter | Hours become available only after someone else verifies this payment. |
| field.hours.paymentFooterCashOnRecording | The hours are available once this sale syncs. You hold this cash until you hand it over. |
| field.hours.paymentFooterCashOnHandover | The hours become available when the office confirms your handover of this cash. |
| field.hours.paymentFooterCashParts | Cash parts: hand them over; the office confirms the handover. |
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
| field.hours.errNoncashOff | Bank and mobile-money payments are recorded by the office. |
| field.hours.errTooManyPayments | At most 10 payments per sale. |
| field.hours.errPaymentsExceed | The payments add up to more than the total of {total}. |
| field.hours.off | Customer hours are turned off for your company. |

The total line shows under Hours once a machine is chosen and the hours are more than 0. It is computed on the phone from
the last pull's `SyncData.hours_prices` and `customer_discounts` (`SYNC_HOURS_PRICES`, full snapshots that replace the
local sets; cleared when the capability goes away), so it works offline, with the server's rule: effective rate = hourly
rate × (100 − percent) / 100, rounded to 4 decimals (half-even); total = hours × effective rate, rounded half-up to the
price's `minor_units` (the server's currency setting; a server that does not send it falls back to ISO 4217: TZS 2,
UGX 0, KWD 3, 2 for an unlisted code). A walk-in sale has no discount.
`{amount}` is the currency code then the grouped amount, with decimals only when it has cents ("TZS 570,000",
"USD 1,234.50"); `{rate}` is the hourly rate before the discount, grouped, up to 4 decimals ("95,000"); `{hours}` and
`{percent}` are grouped, up to 2 decimals ("6", "12.5"). A machine without a stored price shows `field.hours.priceLater`;
saving still works and the server prices the sale on arrival.

**Cash activation (CUSTOMER_HOURS `cash_activation`).** `VERIFY` (also when missing or unknown): the office verifies
the cash payment. `ON_HANDOVER`: cash parts are verified when the office confirms the cash handover that covers them.
`ON_RECORDING`: cash parts count as verified when recorded; the supervisor holds the cash until handing it over. Bank
and mobile-money parts always need office verification. With at least one payment line, the Payment footer is:
- `VERIFY`, or no cash line: `field.hours.paymentFooter`.
- Only cash lines: `field.hours.paymentFooterCashOnRecording` (`ON_RECORDING`) or `field.hours.paymentFooterCashOnHandover`
  (`ON_HANDOVER`).
- Cash with a bank or mobile-money line under `ON_RECORDING` or `ON_HANDOVER`: `field.hours.paymentFooter` then
  `field.hours.paymentFooterCashParts`.

`field.hours.noncashByOffice` still follows when bank and mobile money are off. After the sale syncs the cash shows as
before: the sync status row (`field.hours.outbox`) and My cash, where the server's custody balance holds it until it is
handed over; no new screen.

**Payment lines (split bill, backend 2cb541c).** The Payment section lists payment lines: **Add payment** adds one
(`field.hours.paymentNumber`, then Method, `field.hours.amountReceived`, and `field.hours.reference` for bank and mobile
money); each line has `field.hours.removePayment`; no lines means not paid yet. At most 10 lines. The form opens with
one Cash line whose amount follows the total: set once the total is known (offline price on the phones, the quote on the
web), updated when hours, machine or customer change the total, empty while the total is unknown (it still needs an
amount to save); once the user types into that amount it is never changed again. Removing it gives not paid yet. A line
added later has its amount filled once with what is still owed (total − the other lines) when the total is known;
typed values are never changed. A bank or mobile-money line with an empty reference shows `field.hours.referenceLine`
under its Reference field as soon as the line exists. Save stays disabled while the sale is invalid, so under the paid
summary one line says why: `field.hours.toSave` listing, in order, every rule that blocks it (`toSaveRegistered`,
`toSaveName`, `toSavePhone`, `toSaveCustomer`, `toSaveMachine`, `toSaveHours`, `toSaveTooMany`, `toSaveAmount`,
`toSaveCash`, `toSaveReference`, `toSaveLower`), e.g. "To save: enter the reference for payments 2 and 3."
The methods follow CUSTOMER_HOURS `field_noncash_payments` (missing = off): off, only Cash is offered (no method picker)
and the section footer adds `field.hours.noncashByOffice`; on, Cash, Bank and Mobile money, a reference required for the
last two. Under the lines: `field.hours.paidOf` (`{paid}`, `{total}`, `{balance}` formatted like `{amount}`, balance never
below 0) when the total is known, else `field.hours.paidNoTotal` (grouped amount without a currency) once something is
paid; then the status: `field.hours.notPaid`, `field.hours.fullyPaid`, `field.hours.partPaid`, or
`field.hours.errPaymentsExceed` when the lines add up to more than the total (Save stays off). Received date and, for cash
lines, the cash holder are shared by all lines. One line is sent as `payment` (unchanged, so its photos and older servers
keep working); two or more as `payments` in the order typed, never both; cash parts carry the cash holder
(`staff_member_id`) when recording for another custodian. The server keys part n's payment uuid5(client_id, "payment-n")
(the first "payment"), and a second save of the same form is refused on the phone, so retries stay exactly-once.
Each payment line has its own evidence photos (bank slip, mobile-money receipt; at most 10 per line), inside the line
under Reference (under Amount for cash): titled `field.hours.evidence` when there is one line, `field.hours.linePhoto`
in each line when there are more; removing a line drops its photos. A single line's photos go in the op-level `evidence_upload_ids` (as before). With two or more
lines each part of `payments` carries its own `evidence_upload_ids` (omitted when it has none): queued with the local
attachment ids, each replaced by its upload id as the photo finishes uploading; the op is sent only after every photo of
every part has uploaded (sync fix 13595b6, `PurchasePaymentOp`). On the sync status screen the sale reads `field.hours.outbox`,
e.g. "Hours sale · Cash 300,000 + Bank 270,000".

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

## DEC-032 Phase 1 — allocations and daily reports

Rules shared by both apps:
- **Supervisor is offline-first.** `DAILY_REPORT` is an outbox operation whose **operation id is the report id** (payload `DailyReportIn` without `id`, plus `evidence_upload_ids`). Photos use blob purpose `DAILY_REPORT_EVIDENCE` and the operation waits until every upload completes. It also depends on the outbox operations of any chosen reading the server does not have yet. `client_created_at` is the phone's time at save. One operation per form visit (entity type `daily_report`, entity id = the form's client id).
- **Changeover** is a `METER_CAPTURE` of kind `DAILY` on the running job (`job_id` set, `machine_id` null) with `changeover_to_customer_id` and, when chosen, `changeover_to_job_id`; same photo, OCR and GPS rules as any reading. It waits for the job's own START operation when that is still on the phone. The current customer of the job is not offered as the next customer. Next jobs offered come from `SyncData.changeover_jobs` (capability `SYNC_CHANGEOVER_JOBS`, upsert by `sync_revision`; a bootstrap replaces the list): same machine, chosen customer, status `PENDING_APPROVAL` only, whether the job is mandatory or not (only such a job can be named while another runs). Customers named by those jobs are offered even when the phone has no other record of them. Older servers: the phone's own jobs under the same rule.
- **Gates.** Daily report entries: server announces `OP_DAILY_REPORT`, `tenant.meter.capture`, `ENGINE_HOURS` on. Changeover: `METER_CHANGEOVER`, `tenant.meter.capture`, `ENGINE_HOURS` on, local job status `IN_PROGRESS`. Report list and detail need `tenant.meter.read`.
- **Policy keys read by the form** (`ENGINE_HOURS` effective policy, saved on the phone, unknown = not required; the server decides either way): `changeover_splits_billing` on → the next job is mandatory; `daily_report_evidence_required` on → at least one photo.
- **Unbillable reasons:** `SyncData.unbillable_reasons` (capability `SYNC_UNBILLABLE_REASONS`, upsert by `sync_revision`, deactivations by `is_active=false`, a bootstrap replaces the list). Older servers: `GET /engine-hour-reasons?kind=UNBILLABLE_REASON` (active only), read on refresh and saved encrypted.
- **Prefill** from this phone's readings of the machine for the local day (the opening is the day's first when it has at least two, otherwise the latest reading before the day; the closing is the day's last). Online, `/daily-reports/prefill` adds readings the phone does not have and `existing_report_ids` drives the repeat warning. Both pickers stay editable.
- **Day boundaries of a daily report are the tenant's**, as the server counts them: `tenant_timezone` from bootstrap/changes (kept when a pull omits it), else the `timezone` of the saved cash reconciliation, else of the saved site check-ins, else the phone's zone. They set "today", the three day chips and which readings fall in the day.
- **Owner is online-only for actions.** Reading screens use the snapshot cache and stale banner as today. Own records are shown with the decision disabled.
- **Machine days without revenue checks.** With `tenant.meter.read` and `ENGINE_HOURS` on but no `tenant.revenue.read` or `REVENUE_RECONCILIATION` off, the Machine screen's sheet row still opens: the day list comes from `/work-allocations/reconciliation` (last 14 days) and the day shows only the "Hours allocated" and "Work allocations" cards, no money, readings, fuel or flags.
- **Hours:** decimal formatter (2 dp, no trailing zeros) + ` h`. **Dates:** `26 Oct 2026`. Money: the Owner money formatter. Value at risk is always its own row, never added to expected, attributed or difference.
- `{name}` is the `*_by_name` value, else the short id. `{kind}` is the allocation kind label below.

Screens per app:
| App | Screen | Change |
|---|---|---|
| Supervisor | Readings tab | Row "Daily reports" above the lists (daily report gate), trailing badge = reports sent back to me |
| Supervisor | Machine detail | Action "Daily report for this machine" (daily report gate) |
| Supervisor | Job detail, Next steps | Action "Record changeover" (changeover gate) |
| Supervisor | Daily reports (new list) | Section "Sent back to you" then "My reports" (server list of the last 60 days merged with this phone's unsent ones); saved for offline reading |
| Supervisor | Daily report form (new) | Machine + day (fixed on a resubmission), opening/closing pickers, total, billable, unbillable lines, not-accounted figure, note, photos, Send report |
| Supervisor | Daily report detail (new) | Status, figures, reasons, allocations, the office's note, sync state in plain words; "Correct and send again" while RETURNED |
| Supervisor | Capture (changeover) | Next customer (required), next job (required when the policy says so) |
| Supervisor | Sync status, job and reading sync rows | Conflict codes below in plain words |
| Supervisor | Deep link | Kind `DAILY_REPORT` + `record_id` (DAILY_REPORT_RETURNED), entity `daily_report` → Daily report detail |
| Owner | Approvals | Two new sections shown only when something waits: "Daily reports to review" (`tenant.meter.read`, status SUBMITTED) and "Work allocation corrections" (`tenant.meter.read`, PROPOSED, one row per correction group) |
| Owner | Daily report review (new) | Figures, reasons, allocations, evidence, flags; note + "Mark as reviewed" / "Send back" (`tenant.meter.review`, never the submitter) |
| Owner | Work allocation correction (existing decision screen) | Request card with proposed parts and "Proposed by", every evidence photo; "Now recorded as" in its own row below the request; Approve / Reject (`tenant.meter.approve`, never the proposer), note of at least 5 characters |
| Owner | Machine day (daily machine sheet) | Card "Hours allocated" (`/work-allocations/reconciliation`) and card "Work allocations" (each entry with lots), `tenant.meter.read` and `ENGINE_HOURS` on; money card gains "Value at risk" |
| Owner | Accountability dashboard | Unexplained hours tile and revenue differences tile gain "Value at risk" (one row per currency, hidden when empty) |
| Owner | Revenue difference | Figures gain "Value at risk" after the difference (hidden when zero) |
| Owner | Deep links | Kind `DAILY_REPORT` / entity `daily_report` / path `/tenant/daily-reports/{id}` → Daily report review; kind `WORK_ALLOCATION_CORRECTION` / entity `work_allocation_correction` / path `/tenant/work-allocations/corrections/{id}` → correction decision (the record id is the group id); `/tenant/daily-reports` and `/tenant/work-allocations` → Approvals |

### Supervisor
| Key | English |
|---|---|
| field.report.menu | Daily reports |
| field.report.action | Daily report for this machine |
| field.report.listTitle | Daily reports |
| field.report.sectionReturned | Sent back to you |
| field.report.sectionMine | My reports |
| field.report.empty | No daily reports yet |
| field.report.emptyHint | Reports you send for your machines appear here. |
| field.report.staleFooter | Connect to see the office's latest answers. |
| field.report.rowLine | {total} h in total · {billable} h billable |
| field.report.status.SUBMITTED | Sent |
| field.report.status.REVIEWED | Reviewed |
| field.report.status.RETURNED | Sent back |
| field.report.status.SUPERSEDED | Replaced |
| field.report.status.waiting | Waiting to sync |
| field.report.status.notAccepted | Not accepted |
| field.report.formTitle | Daily report |
| field.report.resubmitTitle | Send report again |
| field.report.machine | Machine |
| field.report.day | Day |
| field.report.readings | Readings |
| field.report.opening | Opening reading |
| field.report.closing | Closing reading |
| field.report.chooseReading | Choose a reading |
| field.report.readingOption | {reading} · {dateTime} |
| field.report.readingNotSynced | {reading} · {dateTime} · not synced yet |
| field.report.noReadings | No readings for this day on this phone. Capture a reading first. |
| field.report.total | Hours between the readings |
| field.report.readingsFooter | Taken from your readings. You can choose others. |
| field.report.billable | Billable hours (optional) |
| field.report.billableFooter | Left empty, the billable hours are the total minus the unbillable hours. |
| field.report.unbillable | Unbillable hours |
| field.report.reason | Reason |
| field.report.chooseReason | Choose a reason |
| field.report.reasonHours | Hours |
| field.report.addReason | Add a reason |
| field.report.removeReason | Remove |
| field.report.reasonsEmpty | Your company has no unbillable reasons yet. Ask the office. |
| field.report.notAccounted | Not accounted for |
| field.report.note | Note (optional) |
| field.report.photoOptional | Photo (optional) |
| field.report.photoRequired | Photo (required) |
| field.report.photoFooter | Stored encrypted on this phone and uploaded before the report is sent. |
| field.report.takePhoto | Take photo |
| field.report.addPhoto | Add another photo |
| field.report.removePhoto | Remove |
| field.report.send | Send report |
| field.report.repeatWarning | A report for this machine and day was already sent. A repeat is kept and flagged for review. |
| field.report.resubmitFooter | This replaces the report that was sent back. |
| field.report.officeNote | The office's note |
| field.report.error.opening | Choose the opening reading. |
| field.report.error.closing | Choose the closing reading. |
| field.report.error.sameReading | Choose two different readings. |
| field.report.error.billable | Enter the billable hours as a number (0 or more, at most 2 decimal places). |
| field.report.error.reasonMissing | Choose a reason for each line of unbillable hours. |
| field.report.error.reasonHours | Enter the hours for each reason (more than 0, at most 2 decimal places). |
| field.report.error.reasonRepeated | Each reason can be used once. |
| field.report.error.exceeds | Billable and unbillable hours are more than the {total} h between the readings. |
| field.report.error.photo | Your company requires a photo with this report. |
| field.report.detailTitle | Daily report |
| field.report.totalHours | Total hours |
| field.report.billableHours | Billable hours |
| field.report.unbillableHours | Unbillable hours |
| field.report.opening.value | Opening reading |
| field.report.closing.value | Closing reading |
| field.report.submitted | Sent |
| field.report.submittedBy | Sent by |
| field.report.reviewedBy | Reviewed by |
| field.report.returnedBy | Sent back by |
| field.report.flagLate | Sent after the daily cut-off |
| field.report.flagRepeat | Repeat report for this day |
| field.report.allocations | Hours by customer |
| field.report.resubmit | Correct and send again |
| field.report.notFound | Report not available |
| field.report.notFoundHint | Connect to load it, or it is no longer on this phone. |
| field.report.outbox | Daily report |
| field.report.waitingPhotos | Waiting for its photos to upload |
| field.report.statusLabel | Status |
| field.report.noteLabel | Note |
| field.report.photos | Photos |
| field.report.sync | Sync |
| field.report.onThisPhone | On this phone |
| field.changeover.action | Record changeover |
| field.changeover.title | Changeover reading |
| field.changeover.footer | Take this reading when the machine moves to the next customer while this job is still running. |
| field.changeover.nextCustomer | Next customer |
| field.changeover.chooseCustomer | Choose the customer |
| field.changeover.nextJob | Next job (optional) |
| field.changeover.nextJobRequired | Next job (required) |
| field.changeover.chooseJob | Choose the job |
| field.changeover.noJobs | No job for this customer on this phone yet. Ask the office to create it. |
| field.changeover.errorCustomer | Choose the next customer. |
| field.changeover.errorJob | Choose the next job. Your company bills the hours after a changeover to that job. |
| field.changeover.outbox | Changeover reading |
| field.conflict.REPORT_READINGS_INVALID | The readings in this report are no longer valid or do not fit the day. Send the report again with other readings. |
| field.conflict.REPORT_HOURS_EXCEED_TOTAL | Billable and unbillable hours are more than the hours between the readings. Send the report again. |
| field.conflict.REPORT_ID_CONFLICT | This report could not be saved because its id is already used. Send the report again. |
| field.conflict.REPORT_NOT_SUPERSEDABLE | That report can no longer be replaced. It may have been reviewed already. |
| field.conflict.REPORT_EVIDENCE_REQUIRED | Your company requires a photo with this report. Send the report again with a photo. |
| field.conflict.REASON_NOT_ALLOWED | One of the reasons is no longer in use. Send the report again with another reason. |
| field.conflict.CHANGEOVER_NOT_ALLOWED | This job was no longer running, so the changeover was not accepted. |
| field.conflict.CHANGEOVER_SAME_CUSTOMER | The machine is already working for this customer, so the changeover was not accepted. |
| field.conflict.CHANGEOVER_JOB_REQUIRED | Your company bills the hours after a changeover to the next job. Record the changeover again and choose the job. |
| field.conflict.CHANGEOVER_JOB_INVALID | That job can no longer follow this one. It must still be waiting for approval, on this machine, for that customer. |
| field.allocation.kind.CUSTOMER_WORK | Customer work |
| field.allocation.kind.AUTHORIZED_ACTIVITY | Authorized activity |
| field.allocation.kind.UNEXPLAINED | Unexplained |

### Owner
| Key | English |
|---|---|
| owner.report.section | Daily reports to review |
| owner.report.empty | No daily reports waiting. |
| owner.report.title | Daily report |
| owner.report.rowHeadline | {machine} · {date} |
| owner.report.rowLine | {total} h in total · {billable} h billable · {unbillable} h unbillable |
| owner.report.figures | Figures |
| owner.report.machine | Machine |
| owner.report.day | Day |
| owner.report.opening | Opening reading |
| owner.report.closing | Closing reading |
| owner.report.total | Total hours |
| owner.report.billable | Billable hours |
| owner.report.unbillable | Unbillable hours |
| owner.report.notAccounted | Not accounted for |
| owner.report.reasons | Unbillable hours by reason |
| owner.report.allocations | Hours by customer |
| owner.report.note | Supervisor's note |
| owner.report.submittedBy | Sent by |
| owner.report.submitted | Sent |
| owner.report.flagLate | Sent after the daily cut-off |
| owner.report.flagRepeat | Repeat report for this day |
| owner.report.replaces | Replaces an earlier report |
| owner.report.evidence | Evidence |
| owner.report.review | Review |
| owner.report.reviewFooter | Someone other than the sender reviews a report. Sending it back asks the sender to correct it. |
| owner.report.noteLabel | Note (at least 5 characters) |
| owner.report.markReviewed | Mark as reviewed |
| owner.report.sendBack | Send back |
| owner.report.reviewed | Marked as reviewed. |
| owner.report.sentBack | Sent back to the supervisor. |
| owner.report.own | You sent this report, so someone else must review it. |
| owner.report.reviewedBy | Reviewed by |
| owner.report.reviewNote | Review note |
| owner.report.status.SUBMITTED | To review |
| owner.report.status.REVIEWED | Reviewed |
| owner.report.status.RETURNED | Sent back |
| owner.report.status.SUPERSEDED | Replaced |
| owner.report.error.REPORT_ALREADY_REVIEWED | This report was already reviewed or replaced. Reload to see it. |
| owner.report.error.SEGREGATION_OF_DUTIES | You sent this report, so someone else must review it. |
| owner.allocation.section | Work allocation corrections |
| owner.allocation.empty | No corrections waiting. |
| owner.allocation.title | Work allocation correction |
| owner.allocation.rowHeadline | {machine} · {date} · {hours} h |
| owner.allocation.original | Now recorded as |
| owner.allocation.part | Proposed: {kind} |
| owner.allocation.partValue | {hours} h · {who} |
| owner.allocation.error.ALLOCATION_NOT_ACTIVE | The original entry has changed. Reload to see it. |
| owner.allocation.error.ALLOCATION_CORRECTION_PENDING | Another correction of this entry is already waiting. |
| owner.allocation.kind.CUSTOMER_WORK | Customer work |
| owner.allocation.kind.AUTHORIZED_ACTIVITY | Authorized activity |
| owner.allocation.kind.UNEXPLAINED | Unexplained |
| owner.allocation.dayCard | Hours allocated |
| owner.allocation.dayTotal | Engine hours |
| owner.allocation.dayCustomer | Customer work |
| owner.allocation.dayAuthorized | Authorized activity |
| owner.allocation.dayUnexplained | Unexplained |
| owner.allocation.dayAllocated | Allocated |
| owner.allocation.dayDifference | Difference |
| owner.allocation.dayReconciled | Every engine hour is allocated. |
| owner.allocation.dayNotReconciled | Some engine hours are not allocated yet. |
| owner.allocation.entries | Work allocations |
| owner.allocation.entriesEmpty | No allocations for this day. |
| owner.allocation.entryLine | {start} → {end} · {hours} h |
| owner.allocation.lotLine | From {purchase}: {hours} h |
| owner.allocation.proposedPill | Waiting for approval |
| owner.allocation.daysEmpty | No engine hours in the last 14 days. |
| owner.allocation.dayLine | {engine} h engine · {allocated} h allocated |
| owner.allocation.dayUnexplainedLine | {hours} h unexplained |
| owner.valueAtRisk | Value at risk |
| owner.valueAtRiskFooter | Unexplained hours at the job's rate. Not part of expected revenue or the shortfall. |

Allocation row subject `{who}`: customer name, then ` · {job number}`; authorized activity: the reason name, else the activity type humanized; unexplained: empty. Rows use `owner.allocation.kind.*` as the title. Value-at-risk rows read `{amount}` per currency.

## DEC-032 Phase 2 — adjustments

Rules shared by both apps:
- **Owner is online-only for actions**; reading screens use the snapshot cache and stale banner as today. No sync changes. Supervisor app: no new screens, new fields decoded tolerantly.
- **Permissions:** section and detail `tenant.adjustment.read`; Approve/Reject `tenant.adjustment.decide`, never the proposer (`proposed_by` = signed-in user: both buttons disabled + `owner.decision.ownRequest`-style note, as the other decision kinds); Withdraw only for the proposer, with `tenant.adjustment.propose`, only while PROPOSED.
- **Reaching Approvals:** the Approvals entry shows with `tenant.approval.read` or `tenant.adjustment.read` (the accountant role decides adjustments and has no `tenant.approval.*`). Without `tenant.approval.read` the expense requests are not fetched and their filter chips and rows are hidden; when no other section applies and nothing waits, show the empty state with `owner.adjust.empty`.
- **List:** `GET /adjustment-requests?status=PROPOSED&page_size=100`, section hidden when nothing waits (same as the other accountability sections). **Detail:** `GET /adjustment-requests/{id}` (any status). **Decide:** `POST .../{id}/decision {decision: APPROVE|REJECT, note?}`; note optional to approve, required to reject (same as the other non-meter kinds), at most 1000 characters. **Withdraw:** `POST .../{id}/withdraw {reason}` (3..1000 characters). After a decision or withdrawal the screen reloads so `effects` shows what actually happened.
- **`effects`** is an open object: forecast while PROPOSED ("If approved"), the actual result once decided ("What it did"); `{refused: code}` while PROPOSED shows `owner.adjust.refused` instead of rows, and Approve stays available (the server decides at the moment of approving). Rows only for the keys below, in this order, money with the request's `currency`, hours with the decimal formatter + ` h`; unknown keys are ignored; zero rows are hidden except the two lot rows. Empty effects hide the card.
- **Evidence:** every `evidence_attachment_ids` as a photo (`GET /attachments/{id}/url`, on demand), same as work allocation corrections.
- **Reversed payments** on the Hours purchase screen: `allocations[]` of `GET /hours-purchases/{id}` (`payment_id`, `amount`, `payment_status`, `released_at`). For released allocations the app reads `GET /customer-payments/{payment_id}` (best effort, at most 25, only with `tenant.finance.read` or `tenant.adjustment.read`); `reversed_at` set → `owner.hours.payment.reversed`. Released but not reversed (or not readable) → `owner.hours.payment.released`. Never parse `release_reason`. Otherwise the status is `payment_status` humanized.

Row formats: headline `{type}`, then ` · {amount}` with `amount` = signed hours for HOURS_CORRECTION (`+2 h`, `-2 h`), hours for HOURS_REFUND, money for the reversals, nothing for INVOICE_VOID. Subtitle `{customer} · {machine}` (each only when present; machine = code, else name). Then the reason (2 lines), then the usual "Proposed {time} by {name}".

Screens per app:
| App | Screen | Change |
|---|---|---|
| Owner | Approvals | New section "Adjustments" (`owner.adjust.section`) after the existing ones, PROPOSED requests, shown only when something waits |
| Owner | Adjustment request (existing decision screen) | Request card (rows below), "If approved" / "What it did" card, Evidence card, Decision card (Approve / Reject), Withdraw card for the proposer |
| Owner | Hours purchase | Hours card gains Refunded, Corrected (signed), Reversed (each only when not zero); new Payments card, only when the purchase has allocations |
| Owner | Hours statement | Totals gain Refunded, Corrected (signed, only when not zero); new card "Corrections, refunds and reversals" from `lines[]` with `entry_type` CORRECTION_ADD, CORRECTION_DEDUCT, REFUNDED, REVERSAL, newest first (card hidden when none): title `{day} · {kind}`, value signed hours, caption `{purchase number} · {reason}` |
| Owner | Deep links | Kind `ADJUSTMENT_REQUEST` + `record_id`, entity `adjustment_request`, path `/tenant/finance/adjustments/requests/{id}` → Adjustment request; `/tenant/finance/adjustments` and `/tenant/finance/adjustments/{id}` → Approvals |
| Supervisor | none | Additive fields only |

Request card rows, in order (each only when present): Type, Reference (`original_reference`), Customer, Machine, Purchase (`purchase_number`), Hours, Amount, Settlement, Reason category (`reason_label`), Proposed by, Decided by, Decision note (a WITHDRAWN request shows its `decision_note` as `owner.adjust.withdrawnReason` instead), then the usual Reason, Proposed, Status.

### Owner
| Key | English |
|---|---|
| owner.adjust.section | Adjustments |
| owner.adjust.empty | No adjustments waiting. |
| owner.adjust.title | Adjustment request |
| owner.adjust.type.HOURS_CORRECTION | Hours correction |
| owner.adjust.type.HOURS_REFUND | Hours refund |
| owner.adjust.type.PAYMENT_REVERSAL | Payment reversal |
| owner.adjust.type.COLLECTION_REVERSAL | Collection reversal |
| owner.adjust.type.PURCHASE_REVERSAL | Purchase reversal |
| owner.adjust.type.INVOICE_VOID | Invoice void |
| owner.adjust.type | Type |
| owner.adjust.reference | Reference |
| owner.adjust.customer | Customer |
| owner.adjust.machine | Machine |
| owner.adjust.purchase | Purchase |
| owner.adjust.hours | Hours |
| owner.adjust.amount | Amount |
| owner.adjust.settlement | Settlement |
| owner.adjust.settlement.CREDIT | Credit to the customer |
| owner.adjust.settlement.PAY_OUT | Paid out |
| owner.adjust.reasonCategory | Reason category |
| owner.adjust.withdrawnReason | Why it was withdrawn |
| owner.adjust.evidence | Evidence |
| owner.adjust.effects.forecast | If approved |
| owner.adjust.effects.actual | What it did |
| owner.adjust.refused | This request can't be approved as it stands: {reason} |
| owner.adjust.effect.lotBefore.forecast | Hours on the lot now |
| owner.adjust.effect.lotBefore.actual | Hours on the lot before |
| owner.adjust.effect.lotAfter | Hours on the lot after |
| owner.adjust.effect.purchaseRemaining | Left on the purchase |
| owner.adjust.effect.hoursRefunded | Hours refunded |
| owner.adjust.effect.value | Value of the hours |
| owner.adjust.effect.settlement | Settlement |
| owner.adjust.effect.paymentAmount | Payment amount |
| owner.adjust.effect.unusedRemoved | Unused hours removed |
| owner.adjust.effect.usedHours | Hours already used |
| owner.adjust.effect.usedKept | Used hours kept |
| owner.adjust.effect.moneyOwed | Money owed for hours already used |
| owner.adjust.effect.treatment | For hours already used |
| owner.adjust.effect.treatment.RECEIVABLE | Bill the customer |
| owner.adjust.effect.treatment.CASE | Open an investigation case |
| owner.adjust.effect.recoveryInvoice | Recovery invoice |
| owner.adjust.effect.released | Released from invoices |
| owner.adjust.effect.moneyReleased | Released to credit |
| owner.adjust.effect.customerBalance | Customer balance |
| owner.adjust.effect.custodyAfter | Custodian's cash after |
| owner.adjust.effect.purchaseLine | {unused} h removed · {used} h used · {owed} owed |
| owner.adjust.withdraw | Withdraw |
| owner.adjust.withdrawTitle | Withdraw this request |
| owner.adjust.withdrawFooter | Only the person who proposed a request can withdraw it. |
| owner.adjust.withdrawLabel | Why are you withdrawing it? (at least 3 characters) |
| owner.adjust.withdrawConfirm | Withdraw this request? |
| owner.adjust.withdrawn | Withdrawn. |
| owner.adjust.error.SEGREGATION_OF_DUTIES | You proposed this request, so someone else must decide it. |
| owner.adjust.error.ALREADY_DECIDED | This request was already decided or withdrawn. Reload to see it. |
| owner.adjust.error.NOT_PROPOSER | Only the person who proposed this request can withdraw it. |
| owner.adjust.error.REVERSAL_EXISTS | A reversal of this record is already waiting or done. |
| owner.adjust.error.REVERSAL_TYPE_MISMATCH | This record can't be reversed this way. |
| owner.adjust.error.NOTHING_TO_REVERSE | There is nothing left to reverse on this record. |
| owner.adjust.error.PURCHASE_CANCELLED | This purchase is cancelled. |
| owner.adjust.error.HOURS_CORRECTION_INVALID | The hours of this correction are not valid. |
| owner.adjust.error.HOURS_CORRECTION_NEGATIVE | This correction would take the hours below zero. |
| owner.adjust.error.HOURS_CORRECTION_EXCEEDS_LOT | This correction would lift the purchase above its activated hours. |
| owner.adjust.error.HOURS_CORRECTION_EXCEEDS_ENTRY | This correction is more than the entry it corrects. |
| owner.adjust.error.CONSUMED_ENTRY_NOT_FOUND | The usage entry this correction names is no longer on the purchase. |
| owner.adjust.error.REFUND_NOT_ALLOWED | Your company has switched refunds off. |
| owner.adjust.error.HOURS_REFUND_INVALID | The hours of this refund are not valid. |
| owner.adjust.error.EXCEEDS_REMAINING_HOURS | This refund is more than the unused hours left on the machine. |
| owner.adjust.error.REFUND_EXCEEDS_PAID | This refund is more than the verified money on the purchase. |
| owner.adjust.error.STAFF_NOT_FOUND | The person named to pay out this refund is no longer on record. |
| owner.adjust.error.PAYMENT_NOT_VERIFIED | Only a verified payment can be reversed. |
| owner.adjust.error.PAYMENT_ALREADY_REVERSED | This payment is already reversed. |
| owner.adjust.error.PAYMENT_REVERSED | This payment has been reversed. |
| owner.adjust.error.INVOICE_NOT_ISSUED | Only an issued invoice can be voided. |
| owner.hours.refunded | Refunded |
| owner.hours.corrected | Corrected |
| owner.hours.reversed | Reversed |
| owner.hours.payments | Payments |
| owner.hours.payment.reversed | Reversed {date} |
| owner.hours.payment.released | No longer counted |
| owner.stmt.refunded | Refunded |
| owner.stmt.corrected | Corrected |
| owner.stmt.adjustments | Corrections, refunds and reversals |
| owner.stmt.line.CORRECTION_ADD | Hours added by correction |
| owner.stmt.line.CORRECTION_DEDUCT | Hours removed by correction |
| owner.stmt.line.REFUNDED | Hours refunded |
| owner.stmt.line.REVERSAL | Hours reversed |
| owner.stmt.lineRow | {day} · {kind} |

Effect rows by key, in order: `lot_hours_before`, `lot_hours_after`, `purchase_remaining`, `hours_refunded`, `value`, `settlement`, `payment_amount`, `unused_hours_removed`, `used_hours`, `used_hours_kept`, `money_owed`, `treatment`, `recovery_invoice_number`, `hire_allocations_released`, `money_released_to_credit`, `customer_balance`, `custody_balance_after`, then one row per `purchases[]` (label = `purchase_number`, value = `owner.adjust.effect.purchaseLine`). `treatment` is shown only when `used_hours` or `money_owed` is not zero. Refusal codes not listed use the server's message; a `refused` code not listed uses "the record has changed. Reload to see it."

## DEC-032 Phase 3 — independence and evidence

Rules shared by both apps:
- **Switched-off modules (`/me` `disabled_capabilities`):** both apps hide the entry points; deep links to a hidden record open the list or home instead (Investigations/Alerts lists → Overview; decisions → Approvals). `INSIGHTS`, `MANAGED_SERVICE` have no mobile screens, nothing to hide. `DEPOSIT_ACCOUNTS` off: the handover form offers the method only (no account picker, no `deposit_account_id`, and `remittance_account_required` is not enforced on the phone). `TRACKING` off: no Alerts tab or alert rows, no tracker or connectivity figures. `INVESTIGATIONS` off: no Investigations entry, no case links, overview risk section hidden.
- **Supervisor, offline first (capability `CASH_DETAILS_V2`; without it none of these appear and nothing new is sent):**
  - **Collection link:** `CASH_COLLECTION.purchase_id` from "Pays for": the customer's open purchases cached by the accountability refresh, plus this phone's unsynced `HOURS_PURCHASE` ops of that customer (the op's `client_id`, shown with `field.collection.unsynced`; the collection waits for that op). Excludes CANCELLED. `CASH_CUSTODY.collection_link_required` on: "Pays for" is required (`field.collection.linkRequired`); off: optional. Invoices are not selectable on the phone (no invoice list reaches the field app; the office links invoices, and a company that requires a link for invoices sees `CONFLICT.COLLECTION_LINK_REQUIRED` in plain words).
  - **Hand-over partial reason:** `CASH_CUSTODY.remit_full_balance` on and the amount below "Your cash" for the currency (the phone's estimate; recording for another holder: the estimate is unknown, so the reason is optional there) → the reason is required, at least 3 characters (`CASH_HANDOVER.partial_reason`), and `partial_reason_id` from the cached `PARTIAL_REMITTANCE` reasons is offered when the tenant has any. Equal or above the estimate: the section is hidden.
  - **Hours transfer evidence:** photos as on remittances (blob `ADJUSTMENT_EVIDENCE`, `HOURS_TRANSFER_REQUEST.evidence_upload_ids`, the op waits for every upload, at most 10). `CUSTOMER_HOURS.transfer_evidence_required`: at least one photo before saving.
  - New **CONFLICT** codes show `field.conflict.*`; unknown codes keep the server's message.
  - **Human numbers:** Money detail and rows show `collection_number` / `remittance_number` once synced (`field.money.collectionNumber`, `field.money.remittanceNumber`), hidden while unsynced. Retention status shows `retention_number`, cash transfers `transfer_number` when present.
- **Owner, online for actions (same rules as other decisions: own request disabled, note optional to approve, required to reject):**
  - Approvals gains **Partial remittance reasons** (`GET /cash/handovers?page_size=100`, rows where `partial_approval.status` = PENDING; visible with `tenant.finance.read`, CASH_CUSTODY on; decide `tenant.finance.retention_approve`; own = `partial_approval.created_by`) via `POST /cash/handovers/{id}/partial-reason-decision {approve, note?}`, and **Variance closures** (`GET /cash/variances?status=CLOSURE_PROPOSED&page_size=100`; visible with `tenant.finance.read`; decide `tenant.finance.variance_close`, own = `proposed_by`; `POST /cash/variances/{id}/closure-decision {approve, note?}`). Zero-amount purchases arrive as Adjustments rows of type `ZERO_AMOUNT_ACTIVATION` (no new section).
  - **Remittance card** (Handover screen + rows): `remittance_number`, `evidence_status`, `outstanding_difference` (hidden when 0/null), and the partial reason with its status; while PENDING and the user has the decide permission, a "Review the reason" row opens the Partial remittance decision.
  - **Variance screen** (Decision screen of a variance, by id, same `CashVarianceDto`): assignee, explanation, explained by, evidence photos, investigation history (`GET /cash/variances/{id}/history`, best effort, hidden on failure), customer/machine/purchase/job when present; `unit` HOURS shows figures in hours. Opening a CLOSURE_PROPOSED variance decides the closure; WRITE_OFF_PROPOSED decides the write-off.
  - **Deep links:** `CASH_VARIANCE` + record id (CASH_VARIANCE_OPENED, CUSTOMER_HOUR_VARIANCE_OPENED, VARIANCE_ASSIGNED, VARIANCE_CLOSURE_DECIDED, CASH_APPROVAL_REQUESTED/VARIANCE_CLOSURE) → Variance screen; `CASH_REMITTANCE` + record id (PARTIAL_REMITTANCE_DECIDED, CASH_APPROVAL_REQUESTED/PARTIAL_REMITTANCE) → Remittance card. `/tenant/finance/cash/variances/{id}` and `/remittances/{id}` likewise.
  - **Numbers:** retention `retention_number`, custody adjustment `adjustment_number`, cash transfer `transfer_number`, hours transfer `transfer_number`, adjustment request `request_number` show as a "Number" row on their decision screens when present.

Screens per app:
| App | Screen | Change |
|---|---|---|
| Supervisor | Record cash collection | New "Pays for" picker (customer's purchases), required per policy |
| Supervisor | Hand over cash | Partial reason section (required per rule above); deposit account picker hidden when DEPOSIT_ACCOUNTS is off |
| Supervisor | Move hours (request) | New evidence photos card, required per policy |
| Supervisor | Money rows and detail | Collection / remittance number once synced |
| Owner | Overview | Tracker and connectivity rows and "Open alerts" hidden when TRACKING off; Risk section hidden when INVESTIGATIONS off |
| Owner | Tabs / More | Alerts tab and Investigations entry hidden per switch |
| Owner | Machine | Tracker rows, connectivity pill and recent alerts hidden when TRACKING off |
| Owner | Fleet | Connectivity filter and pills hidden when TRACKING off |
| Owner | Approvals | Sections "Partial remittance reasons", "Variance closures" after the existing ones, shown only when something waits |
| Owner | Partial remittance decision (Decision screen) | Rows: Custodian, Remitted, Not remitted, Reason, Proposed by |
| Owner | Variance (Decision screen) | Assignee, Explanation, Evidence, History cards; closures decided here |
| Owner | Remittance (Handover) | Number, Evidence, Difference still open, Partial reason card with review link |
| Owner | Adjustment request | `ZERO_AMOUNT_ACTIVATION` row label, `request_number` row |
| Owner | Deep links | As above |

Row format in Approvals: Partial reason `{amount} not remitted · {custodian}` then the reason (2 lines); Variance closure `Close {difference} ({outcome})` (hours: `{hours} h`) then the proposal note (2 lines).

### Supervisor
| Key | English |
|---|---|
| field.collection.link | Pays for |
| field.collection.linkOptional | Pays for (optional) |
| field.collection.linkNone | Not linked |
| field.collection.linkEmpty | No open purchases for this customer on this phone. |
| field.collection.linkRow | {number} · {hours} h left |
| field.collection.unsynced | Not synced yet · {hours} h |
| field.collection.linkRequired | Your company requires every collection to name its purchase or invoice. |
| field.collection.linkFooter | The cash pays this purchase up to what it still owes; anything above stays as customer credit. |
| field.handover.partialTitle | Part of your cash stays with you |
| field.handover.partialFooter | {balance} is your cash. Your company requires the full balance to be remitted, so say why part of it stays with you. |
| field.handover.partialFooterOther | If this is less than this person holds, your company requires the reason. |
| field.handover.partialReason | Why part of the cash stays (required) |
| field.handover.partialReasonOptional | Why part of the cash stays (optional) |
| field.handover.partialCategory | Reason category (optional) |
| field.handover.partialCategoryNone | No category |
| field.handover.partialError | Enter why part of the cash stays with you (at least 3 characters). |
| field.transfer.evidenceTitle | Evidence photos |
| field.transfer.evidenceTitleRequired | Evidence photos (required) |
| field.transfer.evidenceFooter | Photographs are kept with the request and sent when there is a connection. |
| field.transfer.evidenceRequired | Photograph the evidence for this transfer. |
| field.transfer.photograph | Photograph evidence |
| field.transfer.addPhoto | Add another photo |
| field.transfer.removePhoto | Remove photo |
| field.money.collectionNumber | Collection number |
| field.money.remittanceNumber | Remittance number |
| field.conflict.COLLECTION_LINK_REQUIRED | Your company requires every collection to name its purchase or invoice. Record it again and choose one. |
| field.conflict.PARTIAL_REMITTANCE_REASON_REQUIRED | Part of this cash is still with you and your company requires the reason. Record the handover again with the reason. |
| field.conflict.EVIDENCE_REQUIRED | Your company requires evidence for this. Record it again with a photo. |
| field.conflict.PURCHASE_NOT_FOUND | The purchase you chose is no longer on record. Record it again and choose another. |
| field.conflict.PURCHASE_CANCELLED | The purchase you chose is cancelled. Record it again and choose another. |
| field.conflict.OVER_ALLOCATION | This is more than the purchase still owes. Record it again with the right amount. |
| field.conflict.ALLOCATION_MISMATCH | The purchase you chose is for another customer or currency. Record it again and choose another. |

### Owner
| Key | English |
|---|---|
| owner.partial.section | Partial remittance reasons |
| owner.partial.empty | No partial remittance reasons waiting. |
| owner.partial.title | Partial remittance reason |
| owner.partial.row | {amount} not remitted · {custodian} |
| owner.partial.remitted | Remitted |
| owner.partial.notRemitted | Not remitted |
| owner.closure.section | Variance closures |
| owner.closure.empty | No variance closures waiting. |
| owner.closure.title | Variance closure |
| owner.closure.row | Close {difference} ({outcome}) |
| owner.closure.outcome | Proposed outcome |
| owner.closure.outcome.RECOVERED | Recovered |
| owner.closure.outcome.CORRECTED_ERROR | Corrected error |
| owner.closure.outcome.EXPLAINED | Explained |
| owner.closure.outcome.WRITTEN_OFF | Written off |
| owner.variance.title | Variance |
| owner.variance.unit.HOURS | Hours |
| owner.variance.assignee | Assigned to |
| owner.variance.assignedBy | Assigned by |
| owner.variance.explanation | Explanation |
| owner.variance.explainedBy | Explained by |
| owner.variance.evidence | Evidence |
| owner.variance.history | History |
| owner.variance.historyRow | {when} · {action} · {who} |
| owner.variance.history.OPENED | Opened |
| owner.variance.history.ASSIGNED | Assigned |
| owner.variance.history.EXPLAINED | Explained |
| owner.variance.history.CLOSURE_PROPOSED | Closure proposed |
| owner.variance.history.CLOSURE_APPROVED | Closure approved |
| owner.variance.history.CLOSURE_REJECTED | Closure rejected |
| owner.variance.history.WRITE_OFF_PROPOSED | Write-off proposed |
| owner.variance.history.WRITE_OFF_APPROVED | Write-off approved |
| owner.variance.history.WRITE_OFF_REJECTED | Write-off rejected |
| owner.variance.history.RESOLVED | Resolved |
| owner.variance.check.PURCHASE_OVER_ACTIVATED | Purchase over-activated |
| owner.variance.check.NEGATIVE_REMAINING | Negative hours remaining |
| owner.variance.check.CONSUMPTION_MISMATCH | Usage does not match records |
| owner.variance.check.ALLOCATION_MISMATCH | Allocation does not match records |
| owner.variance.check | What was found |
| owner.remit.number | Remittance number |
| owner.remit.evidence | Evidence |
| owner.remit.evidence.DECLARED | Declared by the field |
| owner.remit.evidence.SUPPORTED | Supported by evidence |
| owner.remit.evidence.CONFIRMED | Confirmed by the company |
| owner.remit.outstanding | Difference still open |
| owner.remit.partialReason | Why part stayed with the custodian |
| owner.remit.partialStatus | Reason status |
| owner.remit.partialReview | Review the reason |
| owner.number | Number |
| owner.adjust.type.ZERO_AMOUNT_ACTIVATION | Purchase with nothing to pay |
| owner.adjust.error.PURCHASE_NOT_ZERO_AMOUNT | This purchase has an amount to pay. |
| owner.adjust.error.ALREADY_ACTIVATED | This purchase is already activated. |
| owner.adjust.error.ZERO_AMOUNT_PENDING | A request for this purchase already waits for a decision. |
| owner.closure.error.SEGREGATION_OF_DUTIES | You proposed this closure, so someone else must decide it. |
| owner.closure.error.CLOSURE_NOT_PROPOSED | This closure was already decided. Reload to see it. |
| owner.closure.error.WRITEOFF_APPROVAL_REQUIRED | A write-off needs its own approval. |
| owner.closure.error.VARIANCE_OUTCOME_NOT_ALLOWED | This outcome is not allowed for this variance. |
| owner.partial.error.SEGREGATION_OF_DUTIES | You recorded this remittance, so someone else must decide its reason. |
| owner.partial.error.PARTIAL_APPROVAL_NOT_FOUND | This reason was already decided. Reload to see it. |

## DEC-032 Phase 4 — management view

Contract: `contracts/openapi.json` (commit a15d864). Rules shared by both apps:
- **Owner, online for lookup; the dashboard and employee screens are cached snapshots like the other Owner reads.**
- **Dashboard (`GET /accountability/summary?date_from&date_to`):** period chips reuse `owner.score.period.*` (Last 7 days, Last 30 days default, This month, Last month; at most 93 days). The four group cards come first, in guideline order, each only when its section is non-null: `hours_section`, `operations_section`, `cash_section`, `exceptions_section`. Every figure is a row (label, value, optional caption); a figure opens its screen (rule below). Rows without a target are plain.
- **Tiles that stay below the groups:** investigations, revenue differences, unbilled work, idle machines, discrepancies, unexplained hours, missing daily reports, engine hours. Replaced when the section is present: `customer_hours` and `hours_awaiting_activation` (hours_section), `cash` and `payments` (cash_section), `approvals` and `attempts` (exceptions_section). A section that is null (hidden or switched off) keeps its old tile, so an older server shows exactly what it did.
- **Names (Phases 1–4, both apps, `DisplayName.or` / `DisplayNames.or`):** a null customer, staff or machine name shows the first 8 characters of the id in lower case, never the whole id; `—` only when there is no id either. A row whose name and id are both missing is hidden where the rules say empty rows are hidden.
- **Same on both apps (Phases 1–3 too):** Approvals order is expense requests, jobs, remittances, meter exceptions, meter resets, then the decision kinds; the empty state also waits for revenue differences. A daily report row reads headline, figures, flags, then "Proposed {time} by {name}". On a report, "Hours by customer" rows use the kind as title and `{hours} h · {who}` as value. The Hours statement shows Usage, then "Corrections, refunds and reversals". Meter decision notes allow 5..2000 characters, other decisions up to 1000. The Supervisor "Daily reports" row needs the daily report gate and `tenant.meter.read`; a `DAILY_REPORT` notification with ENGINE_HOURS off opens as any other notification.
- **Value formats:** hours `{hours} h` (phone number format, 0–2 decimals); money figure: its `lines` as money joined with ", ", `owner.mgmt.none` when empty; count figure `{count}`; purchase queue: `{count} · {hours} h` with the money `amounts` as caption.
- **Where a figure opens (`route` from the server; same table on both apps):** the app screen when one exists **and** shows those records and the role may open it; else `owner.mgmt.openWeb` ("Open on the web") with the base web URL + route, only when the route starts `/tenant/` (never absolute, `//` or containing `\`). Empty route: no link.

| Route (query ignored unless stated) | App screen | Needs |
|---|---|---|
| `/tenant/hours/balances` (no customer) | Customer hours | customer hours readable |
| `/tenant/hours/balances?customer_id=X` | Hours statement of X | customer hours readable |
| `/tenant/hours/purchases/{id}` | Hours purchase | customer hours readable |
| `/tenant/hours/purchases?…`, `/tenant/hours/ledger…` | Web (the app's Customer hours lists only open purchases) | |
| `/tenant/hours/{transfers,cancellations,credit,discounts}/{id}` | Decision of that record | decision kind visible |
| Same lists with `status=PENDING` or `PROPOSED`; `/tenant/meter-corrections`, `/tenant/meter-baselines`, `/tenant/meter-resets`, `/tenant/engine-hours/classifications`, `/tenant/non-revenue-approvals`, `/tenant/finance/adjustments/requests`, `/tenant/work-allocations/corrections`, `/tenant/approvals` with that status or none; `/tenant/jobs?status=PENDING_APPROVAL`; `/tenant/daily-reports?status=SUBMITTED`; `/tenant/revenue-differences?status=EXPLANATION_PROPOSED`; cash `/retentions`, `/adjustments` with `status=PENDING`; `/variances?status=WRITE_OFF_PROPOSED` or `CLOSURE_PROPOSED`; `/remittances?status=CLAIMED` or `partial_reason_pending=true`; `/tenant/accountability/pending-adjustments` | Approvals | Approvals open to the role |
| Record routes with an id | The record's screen, same as a notification deep link (decision, remittance, cash record, overdue flag, hours purchase, job, machine, case, meter reset, meter exception, alert) | role may open it |
| `/tenant/finance/cash` (no query) | Cash with supervisors | finance read |
| `/tenant/finance/cash/remittance-overdue` | Overdue remittances | finance read, cash custody on |
| `/tenant/exceptions` | Meter exceptions | meter read |
| `/tenant/revenue-differences` (no status) | Approvals | Approvals open to the role |
| `/tenant/cases` | Investigations | investigations on and readable |
| `/tenant/staff/{id}/accountability` | Employee accountability | `tenant.accountability.employee.read` |
| anything else (`/tenant/work-allocations?…`, `/tenant/customer-payments…`, `/tenant/finance/invoices…`, `/tenant/expenses…`, `/tenant/security-events`, `/tenant/daily-reports?status=RETURNED`, `/tenant/daily-reports` no status, other cash lists, ledger entries `/tenant/finance/adjustments/{id}`, `/tenant/customers…`, `/tenant/sync-conflicts`, `/tenant/revenue-differences` with any other status, a route with an id whose deep link would only open a list such as `/tenant/hours/ledger/{id}`, `/tenant/exceptions/{id}`) | Web | |

  Excavator rows use `machine_id`: Daily sheet when machine days are open to the role, else Machine with fleet read, else web on the route. Employee rows use their route. The `/tenant/staff/{id}/accountability` path also deep-links (notification link) to the Employee screen; without the permission it opens the Accountability dashboard.
- **Employee accountability (`GET /employees/{staff_member_id}/accountability?date_from&date_to`, `tenant.accountability.employee.read`):** from a People scorecard person (row `owner.emp.open`, same period as that screen), from Cash held by employee rows, and by link. Period chips as the dashboard. Cards: identity (name, code, roles, phone, inactive pill), figures (one row per list: count, and money totals per currency for money rows), cash held per currency (`outstanding`, caption in transit / floats / claimed / retained when non-zero), then one list per non-empty group in the DTO order. Records open their route by the table above, else web, else plain. `truncated` non-empty: footnote `owner.emp.truncated`. `scorecard_items` shown only when `scorecard_visible`.
- **Find a reference (`GET /lookup?reference=`, `tenant.lookup.read`, online only):** More entry `owner.lookup.more` after Accountability. Text field + Search (trimmed; empty disabled; ≤100 characters). One card per match: title `owner.lookup.type.{record_type}` (unknown: humanized), reference, status (humanized); rows Recorded by + when, Decided by + when, Customer, Machine, Staff, Amount, Balance (`balance_outstanding` with `balance_unit`: MONEY as money, HOURS as `{n} h`), Hours remaining; empty rows hidden. Opens the record by the table above, else web. No matches: `owner.lookup.empty`. A refusal from the server (an error with a code) shows its message; no connection or an unreadable reply: `owner.lookup.offline`.
- **Outstanding approvals (tile and group):** the old tile now also shows each new count present and non-zero, labels `owner.mgmt.kind.*`. The group shows `by_kind` rows (label, count, caption `owner.mgmt.oldest`) opening per the table.
- **Supervisor (capability `SYNC_OPEN_INVOICES`; `CASH_DETAILS_V2` gates the picker as before):** `SyncData.open_invoices` is a full snapshot: on every bootstrap and every changes page where the capability is announced, replace the local set (nothing delivered → none). Stored encrypted with the sync references. **Pays for** now lists, for the chosen customer and the form's currency only, purchases then open invoices (`field.collection.invoiceRow`). Choosing an invoice sends `CASH_COLLECTION.allocations: [{invoice_id, amount}]` with `amount = min(collection amount, invoice balance)`; choosing a purchase sends `purchase_id` as before (one or the other, never both). The rule `CASH_CUSTODY.collection_link_required` is met by either. The recorder refuses an invoice link with the "server does not accept this yet" message when the server has not announced `SYNC_OPEN_INVOICES` (as it does a purchase link without `CASH_DETAILS_V2`). Changing customer clears the link; changing currency, or a pull that no longer delivers the invoice, drops a chosen invoice. This replaces the Phase 3 note "Invoices are not selectable on the phone".

Screens per app:
| App | Screen | Change |
|---|---|---|
| Owner | Accountability | Period chips; four group cards; old tiles as above; footnote `owner.mgmt.periodNote` |
| Owner | People scorecard person | Row `owner.emp.open` when permitted |
| Owner | Employee accountability (new) | As above |
| Owner | More | `owner.lookup.more` when `tenant.lookup.read` |
| Owner | Find a reference (new) | As above |
| Supervisor | Record cash collection | Open invoices in "Pays for" |

### Supervisor
| Key | English |
|---|---|
| field.collection.invoiceRow | Invoice · {balance} due |
| field.collection.linkEmptyAll | No open purchases or invoices for this customer on this phone. |
| field.collection.invoiceFooter | The cash pays this invoice up to what it still owes; anything above stays as customer credit. |
| field.conflict.OVER_ALLOCATION (updated) | This is more than the purchase or invoice still owes. Record it again with the right amount. |
| field.conflict.ALLOCATION_MISMATCH (updated) | What you chose is for another customer or currency. Record it again and choose another. |
| field.conflict.INVOICE_NOT_OPEN | This invoice is no longer open. Record it again and choose another. |

### Owner
| Key | English |
|---|---|
| owner.mgmt.openWeb | Open on the web |
| owner.mgmt.none | None |
| owner.mgmt.periodNote | Money and hours moved are for the period chosen. Balances and open queues are as they stand now. |
| owner.mgmt.oldest | Oldest {date} |
| owner.mgmt.hours.title | Customer hours |
| owner.mgmt.hours.purchased | Hours purchased |
| owner.mgmt.hours.purchasedValue | Value of hours purchased |
| owner.mgmt.hours.activated | Hours activated |
| owner.mgmt.hours.consumed | Hours consumed |
| owner.mgmt.hours.remaining | Hours remaining |
| owner.mgmt.hours.unpaid | Unpaid purchases |
| owner.mgmt.hours.unconfirmed | Purchases not confirmed |
| owner.mgmt.hours.awaiting | Awaiting activation |
| owner.mgmt.hours.byCustomer | Remaining by customer |
| owner.mgmt.hours.customersShown | Showing {shown} of {total} customers. |
| owner.mgmt.ops.title | Excavator operations |
| owner.mgmt.ops.operating | Operating hours |
| owner.mgmt.ops.customer | Customer hours |
| owner.mgmt.ops.authorized | Authorized non-customer hours |
| owner.mgmt.ops.unexplained | Unexplained hours |
| owner.mgmt.ops.discrepancies | Meter discrepancies |
| owner.mgmt.ops.pendingReports | Daily reports to review |
| owner.mgmt.ops.returnedReports | Daily reports returned |
| owner.mgmt.ops.byExcavator | Hours by excavator |
| owner.mgmt.ops.excavatorRow | Customer {customer} h · Authorized {authorized} h · Unexplained {unexplained} h |
| owner.mgmt.ops.discrepancy.METER_DECREASE | Meter went down |
| owner.mgmt.ops.discrepancy.IMPOSSIBLE_INCREMENT | Impossible increase |
| owner.mgmt.ops.discrepancy.CONTINUITY_GAP | Gap between readings |
| owner.mgmt.ops.discrepancy.TELEMETRY_MISMATCH | Tracker disagrees |
| owner.mgmt.ops.discrepancy.OVERLAPPING_ALLOCATION | Overlapping allocation |
| owner.mgmt.cash.title | Cash accountability |
| owner.mgmt.cash.collected | Cash collected |
| owner.mgmt.cash.transferred | Transferred between staff |
| owner.mgmt.cash.inTransit | In transit |
| owner.mgmt.cash.declared | Declared for remittance |
| owner.mgmt.cash.confirmed | Confirmed by the company |
| owner.mgmt.cash.outstanding | Outstanding with staff |
| owner.mgmt.cash.unconfirmed | Remittances not confirmed |
| owner.mgmt.cash.disputedRemittances | Remittances disputed |
| owner.mgmt.cash.disputedTransfers | Transfers disputed |
| owner.mgmt.cash.held | Cash held by employee |
| owner.mgmt.cash.heldCaption | In transit {a} · Claimed {b} · Float pending {c} · Retained {d} (non-zero parts only) |
| owner.mgmt.exc.title | Exceptions and approvals |
| owner.mgmt.exc.unexplained | Unexplained engine hours |
| owner.mgmt.exc.shortages | Shortages |
| owner.mgmt.exc.overages | Overages |
| owner.mgmt.exc.shortagesPeriod | Shortages opened in period |
| owner.mgmt.exc.overagesPeriod | Overages opened in period |
| owner.mgmt.exc.unconfirmedPayments | Payments not confirmed |
| owner.mgmt.exc.attempts | Refused attempts |
| owner.mgmt.exc.attemptsCaption | Denied {denied} · Second person required {sod} |
| owner.mgmt.exc.missingReports | Daily reports missing |
| owner.mgmt.exc.overdueRemittances | Remittances overdue today |
| owner.mgmt.exc.changeover | Changeover jobs waiting |
| owner.mgmt.exc.changeoverCaption | Oldest {days} days |
| owner.mgmt.exc.changeoverRow | {job} · {machine} · {customer} |
| owner.mgmt.exc.changeoverDays | {days} days |
| owner.mgmt.exc.approvals | Outstanding approvals ({total}) |
| owner.mgmt.exc.pending | Pending adjustments ({total}) |
| owner.mgmt.exc.variances | Unresolved variances ({total}) |
| owner.mgmt.exc.variance.TRANSFER | Cash transfers |
| owner.mgmt.exc.variance.REMITTANCE | Remittances |
| owner.mgmt.exc.variance.FLOAT | Floats |
| owner.mgmt.exc.variance.CUSTOMER_HOUR | Customer hours |
| owner.mgmt.exc.variance.REVENUE_DIFFERENCE | Revenue differences |
| owner.mgmt.kind.adjustment_requests | Adjustment requests |
| owner.mgmt.kind.hours_transfers | Hours transfers |
| owner.mgmt.kind.hours_cancellations | Hours cancellations |
| owner.mgmt.kind.credit_arrangements | Credit arrangements |
| owner.mgmt.kind.discounts | Discounts |
| owner.mgmt.kind.meter_corrections | Meter corrections |
| owner.mgmt.kind.allocation_corrections | Allocation corrections |
| owner.mgmt.kind.classifications | Engine-hour classifications |
| owner.mgmt.kind.non_revenue_approvals | Non-revenue time |
| owner.mgmt.kind.custody_adjustments | Custody adjustments |
| owner.mgmt.kind.write_offs | Write-offs |
| owner.mgmt.kind.variance_closures | Variance closures |
| owner.mgmt.kind.meter_baselines | Meter baselines |
| owner.mgmt.kind.meter_resets | Meter resets |
| owner.mgmt.kind.cash_retentions | Cash retentions |
| owner.mgmt.kind.partial_reasons | Partial remittance reasons |
| owner.mgmt.kind.approval_requests | Expense approvals |
| owner.mgmt.kind.payments_to_verify | Payments to verify |
| owner.mgmt.kind.remittances_to_verify | Remittances to verify |
| owner.mgmt.kind.jobs_awaiting_approval | Jobs awaiting approval |
| owner.mgmt.kind.daily_reports_to_review | Daily reports to review |
| owner.mgmt.kind.case_closures | Case closures |
| owner.mgmt.kind.revenue_decisions | Revenue decisions |
| owner.emp.open | Employee accountability |
| owner.emp.title | Employee accountability |
| owner.emp.code | Employee code |
| owner.emp.roles | Roles |
| owner.emp.phone | Phone |
| owner.emp.inactive | Inactive |
| owner.emp.figures | Figures |
| owner.emp.cashHeld | Cash held now |
| owner.emp.cashCaption | In transit {a} · Claimed {b} · Float pending {c} · Retained {d} (non-zero parts only) |
| owner.emp.count | {count} |
| owner.emp.countMoney | {count} · {money} |
| owner.emp.truncated | Some lists are shortened. Open the web for all records. |
| owner.emp.list.collections | Collections |
| owner.emp.list.floats | Floats |
| owner.emp.list.transfersIn | Transfers in |
| owner.emp.list.transfersOut | Transfers out |
| owner.emp.list.remittances | Remittances |
| owner.emp.list.spending | Spending |
| owner.emp.list.retentions | Retentions |
| owner.emp.list.differences | Differences |
| owner.emp.list.custodyAdjustments | Custody adjustments |
| owner.emp.list.reports | Daily reports submitted |
| owner.emp.list.approvals | Approvals made |
| owner.emp.list.adjustmentsRequested | Adjustments requested |
| owner.emp.list.adjustmentsDecided | Adjustments decided |
| owner.emp.list.scorecard | Scorecard items |
| owner.emp.recordRow | {when} · {status} (status hidden when null, humanized) |
| owner.lookup.more | Find a reference |
| owner.lookup.title | Find a reference |
| owner.lookup.hint | Number or outside reference |
| owner.lookup.search | Search |
| owner.lookup.empty | Nothing found for this reference. |
| owner.lookup.offline | Searching needs a connection. Try again when online. |
| owner.lookup.recordedBy | Recorded by |
| owner.lookup.decidedBy | Decided by |
| owner.lookup.customer | Customer |
| owner.lookup.machine | Machine |
| owner.lookup.staff | Employee |
| owner.lookup.amount | Amount |
| owner.lookup.balance | Balance |
| owner.lookup.hoursRemaining | Hours remaining |
| owner.lookup.type.hours_purchase | Hours purchase |
| owner.lookup.type.hire_invoice | Invoice |
| owner.lookup.type.job | Job |
| owner.lookup.type.customer_payment | Collection |
| owner.lookup.type.cash_handover | Remittance |
| owner.lookup.type.cash_transfer | Cash transfer |
| owner.lookup.type.hours_transfer | Hours transfer |
| owner.lookup.type.cash_retention | Cash retention |
| owner.lookup.type.custody_adjustment | Custody adjustment |
| owner.lookup.type.adjustment_request | Adjustment request |
| owner.lookup.type.adjustment_entry | Ledger adjustment |
| owner.lookup.type.anomaly_case | Investigation |
| owner.lookup.type.cash_variance | Variance |
| owner.lookup.type.daily_report | Daily report |
| owner.lookup.type.meter_correction | Meter correction |
| owner.lookup.type.classification | Engine-hour classification |
| owner.lookup.type.non_revenue_approval | Non-revenue approval |
| owner.lookup.type.meter_reset | Meter reset |
| owner.lookup.type.revenue_difference | Revenue difference |
| owner.lookup.type.hours_cancellation | Hours cancellation |
| owner.lookup.type.approval_request | Expense approval |
| owner.lookup.type.expense | Expense |

## Go-live fixes — payments to confirm

The boss confirms or rejects CLAIMED customer payments from the phone, as on the web (`GET /customer-payments?status=CLAIMED`,
`GET /customer-payments/{id}`, `GET /customer-payments/{id}/evidence`, `POST /customer-payments/{id}/decision`). Online only.
Android: `PaymentReviewText`; iOS: `PaymentReviewText`.

Gating: the Approvals section needs `tenant.finance.read` and `tenant.finance.verify`; the screen needs `tenant.finance.read`;
deciding needs `tenant.finance.verify` and is blocked offline or on saved data. The person who recorded the payment sees the
payment and `owner.payments.own` instead of the buttons; the server refuses them too (`SEGREGATION_OF_DUTIES`).

Deep links: the notification `CUSTOMER_PAYMENT_TO_VERIFY` (entity `customer_payment`, id = the payment) opens the payment;
`/tenant/customer-payments/{id}` opens the payment; `/tenant/customer-payments` opens Approvals; dashboard route
`/tenant/customer-payments?status=CLAIMED` opens Approvals.

### Owner
| Key | English |
|---|---|
| owner.payments.section | Payments to confirm |
| owner.payments.empty | No customer payments waiting. |
| owner.payments.screenTitle | Customer payment |
| owner.payments.card | Payment |
| owner.payments.customerFallback | A customer |
| owner.payments.headline | {customer} paid {amount} |
| owner.payments.received | Received {date} |
| owner.payments.recordedByLine | Recorded by {name} |
| owner.payments.field.customer | Customer |
| owner.payments.field.amount | Amount |
| owner.payments.field.method | Method |
| owner.payments.field.reference | Reference |
| owner.payments.field.collectionNumber | Collection number |
| owner.payments.field.receivedAt | Received |
| owner.payments.field.receivedBy | Received by |
| owner.payments.field.recordedBy | Recorded by |
| owner.payments.field.recordedAt | Recorded |
| owner.payments.field.note | Note |
| owner.payments.field.status | Status |
| owner.payments.field.decidedBy | Decided by |
| owner.payments.field.decisionNote | Decision note |
| owner.payments.field.reversed | Reversed |
| owner.payments.method.CASH | Cash |
| owner.payments.method.BANK | Bank transfer |
| owner.payments.method.MOBILE_MONEY | Mobile money |
| owner.payments.status.CLAIMED | Waiting to be confirmed |
| owner.payments.status.VERIFIED | Confirmed |
| owner.payments.status.REJECTED | Rejected |
| owner.payments.links.purchases | Hours purchases |
| owner.payments.links.invoices | Invoices |
| owner.payments.link | {number} · {amount} |
| owner.payments.evidence.title | Evidence |
| owner.payments.evidence.photo | photo {n} |
| owner.payments.evidence.none | No evidence photos attached. |
| owner.payments.evidence.failed | Evidence photos could not be loaded. Pull to try again. |
| owner.payments.decision | Decision |
| owner.payments.explanation | Confirm only when the money has been received (bank statement, mobile money record or cash counted). Confirmed money reduces what the customer owes. Rejecting releases what it was linked to. |
| owner.payments.confirm | Confirm |
| owner.payments.reject | Reject |
| owner.payments.cancel | Cancel |
| owner.payments.confirmTitle | Confirm this payment? |
| owner.payments.rejectTitle | Reject this payment? |
| owner.payments.noteOptional | Note (optional) |
| owner.payments.reasonRequired | Reason (required) |
| owner.payments.errReasonShort | Write at least 3 characters. |
| owner.payments.confirmed | Payment confirmed. |
| owner.payments.rejected | Payment rejected. |
| owner.payments.own | You recorded this payment, so someone else must confirm or reject it. |
| owner.payments.alreadyDecided | Someone already decided this payment. Reload to see it. |

## DEC-033 — petty cash funds

The holder's petty cash in the Supervisor app (offline first, sync capability `OP_PETTY_CASH`) and approvals of fundings,
top-ups and fund adjustments in the Owner app (online). Android: `PettyCashTexts` (Supervisor), `PettyCashReviewText`
(Owner), `ExpenseFlags` (both, `core:domain`); iOS: the same names.

Rules shared by both apps:
- **Gating (Supervisor):** the whole feature (Money tab section, screens, the "Petty cash" paid-from option) needs the sync
  capability `OP_PETTY_CASH`, the permission `tenant.pettycash.read` and `PETTY_CASH` not in `/me disabled_capabilities`.
  Counting also needs `tenant.pettycash.count`. "Petty cash" as paid-from also needs at least one fund I hold or an advance I
  received. Advances appear only when the `PETTY_CASH` policy snapshot has `advances_enabled`.
- **Snapshot (Supervisor):** `petty_cash_funds`, `petty_cash_awaiting`, `petty_cash_holder_changes`, `petty_cash_advances` are
  full snapshots on every bootstrap and delta: the local set is replaced (cleared when the server stops announcing
  `OP_PETTY_CASH`). The `PETTY_CASH` policy snapshot (tenant scope) gives `count_witness_required`, `return_evidence_required`,
  `advances_enabled`, `max_expense_amount` (missing keys read as off / none). Figures are the server's (`balance`,
  `available_to_spend`, ...); the phone never computes a fund balance.
- **Operations (outbox, client ids and device times as every field op):** `PETTY_CASH_ACKNOWLEDGEMENT` (entity = movement id,
  one answer per movement), `PETTY_CASH_TOP_UP_REQUEST` / `PETTY_CASH_RETURN` / `PETTY_CASH_COUNT` (entity = the form's client
  id, sent as `client_id`), `PETTY_CASH_HOLDER_CHANGE_ACKNOWLEDGEMENT` (entity = holder change id),
  `PETTY_CASH_ADVANCE_CLEARANCE` (entity = advance id). Return and count photos: blob purpose `PETTY_CASH_EVIDENCE`, sent as
  `evidence_upload_ids` (the op waits for every upload, at most 10). An item answered on this phone (not refused) leaves
  "Waiting for you" / "Advances" and shows under "Recorded on this phone" with its sync state.
- **Expense paid from petty cash:** `EXPENSE.paid_from = PETTY_CASH` with `petty_cash_fund_id` (required) and
  `petty_cash_advance_id` (optional; only advances of that fund given to me). The currency is the fund's (not editable). Amount
  above the fund's (or the advance's remaining) available: still saved offline, with `field.pettyCash.expense.overspend` as the
  approval note. Above `max_expense_amount` (fund currency = base currency): `field.pettyCash.expense.aboveMaximum`. A fund I
  do not hold (only through an advance given to me) requires the advance (`field.pettyCash.expense.advanceRequired`).
- **Forms:** acknowledge = amount received (0 or more, prefilled with the issued amount) or dispute with a reason (as cash
  acknowledgements). Top-up: amount optional (empty = the server's suggestion), more than 0 when given; when the amount is above
  `approved_limit - balance` the reason for going above is required (at least 3 characters). Return: amount more than 0
  (prefilled with available to spend when above 0), method (`CASH_TO_OFFICE`, `BANK_DEPOSIT`, `MOBILE_MONEY`), deposit account
  (optional; active synced accounts in the fund's currency, hidden when `DEPOSIT_ACCOUNTS` is off), reference, note, photos (at
  least one when `return_evidence_required`). Count: counted amount 0 or more, note, photos (optional); when
  `count_witness_required` a witness is chosen from the colleagues who may witness a count, offline: sync capability
  `SYNC_PETTY_CASH_WITNESSES` brings `SyncData.petty_cash_witnesses` (`{user_id, name}`, never me; sent while I hold a fund and
  may count), a full snapshot that replaces the local set on every pull and is cleared with the other petty cash sets when
  `OP_PETTY_CASH` goes away. The picker is searchable (`field.pettyCash.count.witness`, none = `field.pettyCash.count.witnessNone`,
  empty list = `field.pettyCash.count.witnessEmpty`). A server without `SYNC_PETTY_CASH_WITNESSES` keeps the online name search
  (`GET /tenant/people?q=`, at least 2 characters). Without a witness the count still saves, with the note
  `field.pettyCash.count.noWitness` (a self-count). After sync, "Recorded on this phone" adds a line under a synced count:
  `field.pettyCash.count.witnessDropped` when a witness was chosen but the server recorded none (the witness lost the
  permission before the phone synced), else `field.pettyCash.count.recordedSelf` when the server marked it a self-count. Holder change: accept, or decline with a reason.
  Clear advance (fund holder, advances given to someone else): change handed back 0 or more, prefilled with `remaining`.
- **Give an advance (fund holder, offline):** each fund on My petty cash gets `field.pettyCash.action.giveAdvance` when the
  server announces `OP_PETTY_CASH_ADVANCE` and the `PETTY_CASH` policy has `advances_enabled`. The form (`PETTY_CASH_ADVANCE`
  `{client_id, fund_id, recipient_staff_id, amount, purpose}`, entity = the form's client id) names the recipient from the cash
  holders list the phone saves for cash transfers (`GET /cash/custodians`, read online and kept encrypted; needs
  `tenant.collection.record`; now also read while petty cash is on and CASH_CUSTODY is off), never the fund's holder and never
  me; the amount (more than 0) and the purpose (at least 3 characters). Above the fund's available to spend:
  `field.pettyCash.give.overspend` when the policy's `overspend_allowed_offline` is on (missing = on, the platform default),
  else `field.pettyCash.give.overspendBlocked` and saving is blocked. It shows under "Recorded on this phone"
  (`field.pettyCash.outbox.giveAdvance`) and, after the next pull, in Advances as "Given to {name}".
- **Expense flags (`control_flags`)**, shown neutrally wherever an expense is shown (Supervisor Money rows and expense detail;
  Owner field spend rows and the expense card of an approval): header `expense.flags.title`, one line per flag; unknown flags
  are humanized.
- **Owner approvals (online):** Approvals section `owner.pettyCash.section` lists `GET /petty-cash/movements?status=PROPOSED`
  (FUNDING and TOP_UP) and `GET /petty-cash/adjustments?status=PENDING`; visible with `tenant.pettycash.read` and
  `tenant.pettycash.approve`, `PETTY_CASH` not switched off, shown only when something waits. The record screen (by id) has
  the facts, the expenses behind a top-up (`GET /petty-cash/movements/{id}/expenses`, best effort) and Approve / Reject
  (`POST .../decision {approve, note?}`; reject needs a reason of at least 3 characters). The proposer (`created_by` = me)
  sees `owner.pettyCash.own` instead of the buttons. Every refusal shows the server's message as it is (the server also
  refuses the fund's holder); `PETTY_CASH_ALREADY_DECIDED` shows `owner.pettyCash.alreadyDecided` and reloads.
- **Deep links:** Owner: entity `petty_cash_movement` / `petty_cash_adjustment` (+ id) and `/tenant/finance/petty-cash/movements/{id}`,
  `/tenant/finance/petty-cash/adjustments/{id}` open the record; other `/tenant/finance/petty-cash` links open Approvals.
  Supervisor: `petty_cash_movement` waiting for my acknowledgement opens the acknowledge form, `petty_cash_holder_change`
  waiting for me opens the take-over form, any other petty cash entity opens My petty cash.

Screens per app:
| App | Screen | Change |
|---|---|---|
| Supervisor | Money tab | Section "Petty cash" with the row "My petty cash" (footer: how many items wait) |
| Supervisor | My petty cash | Funds with figures and actions, Waiting for you, Advances, Recorded on this phone |
| Supervisor | Acknowledge petty cash, Request a top-up, Return money, Record a count, Take over a fund, Clear an advance | Forms (offline) |
| Supervisor | Record expense | "Petty cash" paid-from, fund and advance pickers, overspend / maximum notes |
| Supervisor | Money rows, expense detail | "Petty cash" paid-from, flags ("To check") |
| Owner | Approvals | Section "Petty cash to approve" |
| Owner | Petty cash request / Fund adjustment | Facts, expenses behind a top-up, Approve / Reject |
| Owner | Field spend rows, approval expense card | Flags ("To check") |

### Shared (both apps)
| Key | English |
|---|---|
| expense.flags.title | To check |
| expense.flags.OVERSPEND | Recorded above what the fund had available |
| expense.flags.SPENT_FROM_COLLECTIONS | Paid from collected cash |
| expense.flags.ABOVE_PETTY_CASH_MAXIMUM | Above the petty cash maximum per expense |
| expense.paidFrom.PETTY_CASH | Petty cash |

### Supervisor
| Key | English |
|---|---|
| field.pettyCash.section | Petty cash |
| field.pettyCash.row | My petty cash |
| field.pettyCash.rowWaiting | {n} waiting for you |
| field.pettyCash.title | My petty cash |
| field.pettyCash.empty.title | No petty cash fund |
| field.pettyCash.empty.message | Petty cash funds you hold appear here after a sync. |
| field.pettyCash.fundHeader | {code} · {name} |
| field.pettyCash.balance | Balance |
| field.pettyCash.available | Available to spend |
| field.pettyCash.pendingSpending | Expenses awaiting approval |
| field.pettyCash.awaitingAck | Money on its way to you |
| field.pettyCash.returnsClaimed | Returns awaiting confirmation |
| field.pettyCash.limit | Approved limit |
| field.pettyCash.low | Below the low-balance level |
| field.pettyCash.lastCount | Last count |
| field.pettyCash.notCounted | Not counted yet |
| field.pettyCash.nextCount | Next count due |
| field.pettyCash.asOf | As of {date}. Figures from the last sync. |
| field.pettyCash.action.topUp | Request a top-up |
| field.pettyCash.action.return | Return money to the office |
| field.pettyCash.action.count | Record a count |
| field.pettyCash.waiting | Waiting for you |
| field.pettyCash.waiting.funding | Funding {number} · {amount} |
| field.pettyCash.waiting.topUp | Top-up {number} · {amount} |
| field.pettyCash.waiting.holderChange | Take over {fund} from {name} |
| field.pettyCash.someone | someone |
| field.pettyCash.advances | Advances |
| field.pettyCash.advance.row | {number} · {amount} |
| field.pettyCash.advance.detail | Remaining {amount} · due {date} |
| field.pettyCash.advance.overdue | Overdue |
| field.pettyCash.advance.toMe | Given to you |
| field.pettyCash.advance.fromMe | Given to {name} |
| field.pettyCash.onPhone | Recorded on this phone |
| field.pettyCash.outbox.ack | Petty cash acknowledgement |
| field.pettyCash.outbox.topUp | Petty cash top-up request |
| field.pettyCash.outbox.return | Petty cash return |
| field.pettyCash.outbox.count | Petty cash count |
| field.pettyCash.outbox.holderChange | Petty cash fund take-over |
| field.pettyCash.outbox.advance | Petty cash advance cleared |
| field.pettyCash.title.ack | Acknowledge petty cash |
| field.pettyCash.title.topUp | Request a top-up |
| field.pettyCash.title.return | Return money |
| field.pettyCash.title.count | Record a count |
| field.pettyCash.title.holderChange | Take over a fund |
| field.pettyCash.title.advance | Clear an advance |
| field.pettyCash.notFound | This is no longer waiting on this phone. Pull to sync. |
| field.pettyCash.unavailable | Petty cash is not available on this phone. Sync, or ask your office. |
| field.pettyCash.fund | Fund |
| field.pettyCash.ack.funding | Funding from the office |
| field.pettyCash.ack.topUp | Top-up from the office |
| field.pettyCash.ack.number | Number |
| field.pettyCash.ack.issued | Issued |
| field.pettyCash.ack.issuedAt | Issued at |
| field.pettyCash.ack.issuedBy | Issued by |
| field.pettyCash.ack.reference | Reference |
| field.pettyCash.ack.amount | Amount received |
| field.pettyCash.ack.footer | Count the money before you acknowledge. A different amount is recorded as a difference for the office to review. |
| field.pettyCash.ack.acknowledge | Acknowledge |
| field.pettyCash.ack.dispute | Dispute |
| field.pettyCash.ack.disputeReason | To dispute, write in the note why. |
| field.pettyCash.ack.waiting | You already answered on this phone. It is sent when the phone syncs. |
| field.pettyCash.note | Note (optional) |
| field.pettyCash.topUp.amount | Amount (optional) |
| field.pettyCash.topUp.amountFooter | Leave it empty to ask for the approved spending since the last top-up. |
| field.pettyCash.topUp.aboveReason | Reason for going above the limit |
| field.pettyCash.topUp.aboveFooter | This is more than brings the fund to its limit ({amount}); say why. |
| field.pettyCash.topUp.footer | Someone else approves the top-up. The money counts in your fund only after you acknowledge it. |
| field.pettyCash.topUp.send | Send request |
| field.pettyCash.return.amount | Amount returned |
| field.pettyCash.return.method | How |
| field.pettyCash.return.method.CASH_TO_OFFICE | Cash to office |
| field.pettyCash.return.method.BANK_DEPOSIT | Bank deposit |
| field.pettyCash.return.method.MOBILE_MONEY | Mobile money |
| field.pettyCash.return.account | Deposit account (optional) |
| field.pettyCash.return.noAccount | No account |
| field.pettyCash.return.reference | Reference (optional) |
| field.pettyCash.return.footer | The fund goes down only when the office confirms what it received. |
| field.pettyCash.return.evidenceRequired | Your company requires a photo of the slip or the cash. |
| field.pettyCash.count.amount | Cash counted |
| field.pettyCash.count.footer | Count every note and coin in the fund. A difference from the expected amount goes to the office to review. |
| field.pettyCash.count.witness | Witness |
| field.pettyCash.count.witnessSearch | Search a colleague by name |
| field.pettyCash.count.witnessNone | No witness |
| field.pettyCash.count.witnessFooter | Your company asks for a witness: someone else who can count petty cash watches the count. |
| field.pettyCash.count.witnessOffline | Connect to choose a witness. |
| field.pettyCash.count.witnessNoResults | No one found. |
| field.pettyCash.count.noWitness | Without a witness this count is recorded as counted by you alone. |
| field.pettyCash.count.witnessEmpty | No colleague who can witness a count is on this phone. Sync first. |
| field.pettyCash.count.recordedSelf | Recorded as counted by you alone. |
| field.pettyCash.count.witnessDropped | The witness could no longer witness counts, so this count was recorded without a witness. |
| field.pettyCash.holder.from | From |
| field.pettyCash.holder.requestedBy | Requested by |
| field.pettyCash.holder.requestedAt | Requested |
| field.pettyCash.holder.footer | Until you accept, {name} stays accountable for the fund. Count the cash before you accept. |
| field.pettyCash.holder.accept | Take over the fund |
| field.pettyCash.holder.decline | Decline |
| field.pettyCash.holder.declineReason | To decline, write in the note why. |
| field.pettyCash.advance.recipient | Given to |
| field.pettyCash.advance.amount | Advance |
| field.pettyCash.advance.purpose | Purpose |
| field.pettyCash.advance.approved | Approved spending |
| field.pettyCash.advance.pending | Spending awaiting approval |
| field.pettyCash.advance.remaining | Remaining |
| field.pettyCash.advance.due | Due |
| field.pettyCash.advance.change | Change handed back |
| field.pettyCash.advance.footer | Count the change you take back. A difference is recorded for the office to review. |
| field.pettyCash.advance.pendingWarning | Expenses of this advance are still waiting for approval. It can be cleared once they are decided. |
| field.pettyCash.advance.clear | Clear advance |
| field.pettyCash.err.amount | Enter the amount (more than 0). |
| field.pettyCash.err.counted | Enter the cash counted (0 or more). |
| field.pettyCash.err.change | Enter the change handed back (0 or more). |
| field.pettyCash.err.aboveReason | Enter the reason for going above the limit (at least 3 characters). |
| field.pettyCash.err.evidence | Photograph the slip or the cash. |
| field.pettyCash.err.reason | Enter a reason (at least 3 characters). |
| field.pettyCash.expense.section | Petty cash fund |
| field.pettyCash.expense.fund | Fund |
| field.pettyCash.expense.fundEmpty | No petty cash fund on this phone. Sync first. |
| field.pettyCash.expense.fundOption | Available {amount} |
| field.pettyCash.expense.advance | Advance (optional) |
| field.pettyCash.expense.advanceRequiredLabel | Advance |
| field.pettyCash.expense.noAdvance | Not from an advance |
| field.pettyCash.expense.advanceOption | Remaining {amount} |
| field.pettyCash.expense.footer | Available to spend: {amount}. The currency is the fund's. |
| field.pettyCash.expense.fundRequired | Choose the petty cash fund. |
| field.pettyCash.expense.advanceRequired | Choose the advance this was paid from. |
| field.pettyCash.expense.currency | The fund holds {currency}. |
| field.pettyCash.expense.overspend | Above what the fund has available ({amount}): it is kept for approval and marked for the approver to check. |
| field.pettyCash.expense.aboveMaximum | Above the petty cash maximum per expense ({amount}): a manager must approve it. |
| field.pettyCash.conflict.PETTY_CASH_INSUFFICIENT | The fund did not have enough available. Check the fund and record the expense again if needed. |
| field.pettyCash.conflict.PETTY_CASH_FUND_INACTIVE | This petty cash fund is no longer active. |
| field.pettyCash.conflict.PETTY_CASH_DISABLED | Petty cash is switched off for your company. |
| field.pettyCash.conflict.PETTY_CASH_ALREADY_ACKNOWLEDGED | This was already answered. |
| field.pettyCash.conflict.PETTY_CASH_ALREADY_DECIDED | This was already decided. |
| field.pettyCash.conflict.PETTY_CASH_NOTHING_TO_TOP_UP | Nothing to top up: no approved spending since the last top-up, or the fund is at its limit. |
| field.pettyCash.conflict.PETTY_CASH_ABOVE_CAP_REASON_REQUIRED | The amount is above the fund's limit; send the request again with a reason. |
| field.pettyCash.conflict.PETTY_CASH_ADVANCE_EXPENSES_PENDING | Expenses of this advance are still waiting for approval. |
| field.pettyCash.conflict.PETTY_CASH_ADVANCE_CLEARED | This advance is already cleared. |
| field.pettyCash.conflict.PETTY_CASH_ADVANCES_DISABLED | Advances are switched off for your company. |
| field.pettyCash.conflict.PETTY_CASH_ADVANCE_TO_HOLDER | An advance goes to someone other than the fund's holder. |
| field.pettyCash.action.giveAdvance | Give an advance |
| field.pettyCash.title.giveAdvance | Give an advance |
| field.pettyCash.give.recipient | Given to |
| field.pettyCash.give.recipientEmpty | No colleague is saved on this phone yet. Connect, then open this form again. |
| field.pettyCash.give.amount | Amount |
| field.pettyCash.give.purpose | Purpose |
| field.pettyCash.give.footer | The advance leaves the fund now. The colleague clears it with receipts and the change. |
| field.pettyCash.give.overspend | Above what the fund has available ({amount}): it is recorded when the phone syncs and marked for the office to check. |
| field.pettyCash.give.overspendBlocked | Above what the fund has available ({amount}). Your company does not allow this offline. |
| field.pettyCash.give.save | Give advance |
| field.pettyCash.outbox.giveAdvance | Petty cash advance given |
| field.pettyCash.err.recipient | Choose who receives the advance. |
| field.pettyCash.err.purpose | Enter the purpose (at least 3 characters). |

### Owner
| Key | English |
|---|---|
| owner.pettyCash.section | Petty cash to approve |
| owner.pettyCash.empty | No petty cash requests waiting. |
| owner.pettyCash.kind.FUNDING | Funding |
| owner.pettyCash.kind.TOP_UP | Top-up |
| owner.pettyCash.kind.ADJUSTMENT | Fund adjustment |
| owner.pettyCash.title.movement | Petty cash request |
| owner.pettyCash.title.adjustment | Fund adjustment |
| owner.pettyCash.headline | {kind} {amount} · {fund} |
| owner.pettyCash.fundFallback | A fund |
| owner.pettyCash.proposedBy | Proposed by {name} |
| owner.pettyCash.card | Request |
| owner.pettyCash.field.fund | Fund |
| owner.pettyCash.field.holder | Holder |
| owner.pettyCash.field.kind | Kind |
| owner.pettyCash.field.number | Number |
| owner.pettyCash.field.amount | Amount |
| owner.pettyCash.field.suggested | Suggested |
| owner.pettyCash.field.cap | Brings the fund to its limit |
| owner.pettyCash.field.aboveCapReason | Reason for going above the limit |
| owner.pettyCash.field.reason | Reason |
| owner.pettyCash.field.note | Note |
| owner.pettyCash.field.proposedBy | Proposed by |
| owner.pettyCash.field.proposedAt | Proposed |
| owner.pettyCash.field.status | Status |
| owner.pettyCash.field.decidedBy | Decided by |
| owner.pettyCash.field.decisionNote | Decision note |
| owner.pettyCash.status.PROPOSED | Waiting for approval |
| owner.pettyCash.status.PENDING | Waiting for approval |
| owner.pettyCash.status.APPROVED | Approved |
| owner.pettyCash.status.REJECTED | Rejected |
| owner.pettyCash.expenses | Spending behind this top-up |
| owner.pettyCash.expensesNone | No expenses listed. |
| owner.pettyCash.expensesFailed | The expenses could not be loaded. Pull to try again. |
| owner.pettyCash.expenseLine | {description} · {amount} |
| owner.pettyCash.decision | Decision |
| owner.pettyCash.explanation.movement | Approving lets the office hand the money over. It counts in the fund only after the holder acknowledges it. |
| owner.pettyCash.explanation.adjustment | Approving changes the fund balance by this amount. |
| owner.pettyCash.approve | Approve |
| owner.pettyCash.reject | Reject |
| owner.pettyCash.cancel | Cancel |
| owner.pettyCash.approveTitle | Approve this request? |
| owner.pettyCash.rejectTitle | Reject this request? |
| owner.pettyCash.noteOptional | Note (optional) |
| owner.pettyCash.reasonRequired | Reason (required) |
| owner.pettyCash.errReasonShort | Write at least 3 characters. |
| owner.pettyCash.approved | Request approved. |
| owner.pettyCash.rejected | Request rejected. |
| owner.pettyCash.own | You proposed this, so someone else must approve or reject it. |
| owner.pettyCash.alreadyDecided | Someone already decided this. Reload to see it. |

## Supervisor — customers (add and edit details)

Supervisors add customers and keep their details current from the phone (`tenant.customer.details`; `tenant.customer.write`
also allows payment terms). Online only, like the Owner approvals: nothing is queued. Android: `CustomerTexts`; iOS:
`CustomerTexts`.

Rules shared by both apps:
- **Entry:** the Money tab gets a section `field.customers.section` with the row `field.customers.row`, shown only to a user
  holding `tenant.customer.details` or `tenant.customer.write`.
- **List:** `GET /tenant/customers?q=&page_size=50` (active only), searchable by name or code; a row is the name with
  "{code} · {contact}" below. Offline: `field.customers.offline` (no saved copy is shown). A row opens the customer
  (`GET /tenant/customers/{id}`) with Edit details.
- **Add / edit:** code (required, at most 32), name (required, at most 200), tax ID (at most 64), contact name (at most 200),
  phone (at most 40), email (at most 320; when given it needs one "@" with text on both sides). Blank optional fields are sent
  as null. Payment terms: with `tenant.customer.write` an editable whole number 0–365 days (30 for a new customer); without it
  read-only "{n} days · Set by the office", sent unchanged (30 for a new customer). Edit sends the `version` last read.
- **Refusals** show the server's message as it is. `STALE_VERSION` shows `field.customers.stale` and reloads the customer.
  Offline (no connection) shows `field.customers.offline` and keeps the form.
- **Pickers:** sync delivers only the customers on my jobs' contracts, so a new customer would not reach the hours sale and
  cash collection pickers through sync. After a save, and whenever the Customers list loads, the active customers read are
  saved into the phone's synced customer list (the same records the pickers read). Job requests pick a contract, so a new
  customer appears there only once the office gives it a contract.

### Supervisor
| Key | English |
|---|---|
| field.customers.section | Customers |
| field.customers.row | Customers |
| field.customers.title | Customers |
| field.customers.search | Search by name or code |
| field.customers.empty | No customers found. |
| field.customers.offline | Customers need a connection. Connect to see, add or edit them. |
| field.customers.loadFailed | The customers could not be loaded. Pull to try again. |
| field.customers.add | Add a customer |
| field.customers.titleAdd | Add a customer |
| field.customers.titleEdit | Edit customer |
| field.customers.titleDetail | Customer |
| field.customers.edit | Edit details |
| field.customers.code | Code |
| field.customers.name | Name |
| field.customers.taxId | Tax ID (optional) |
| field.customers.contactName | Contact name (optional) |
| field.customers.phone | Phone (optional) |
| field.customers.email | Email (optional) |
| field.customers.label.taxId | Tax ID |
| field.customers.label.contact | Contact |
| field.customers.label.phone | Phone |
| field.customers.label.email | Email |
| field.customers.terms | Payment terms |
| field.customers.termsDays | {n} days |
| field.customers.termsByOffice | {n} days · Set by the office |
| field.customers.footer | Contracts, rates and payment terms stay with the office. Once saved, the customer is on this phone for hours sales and cash collections. |
| field.customers.saved | Customer saved. |
| field.customers.stale | Someone else changed this customer. Reload to see it. |
| field.customers.errCode | Enter a code (at most 32 characters). |
| field.customers.errName | Enter the name (at most 200 characters). |
| field.customers.errEmail | Enter a valid email address. |
| field.customers.errTerms | Enter payment terms between 0 and 365 days. |
| field.customers.errLong | Shorten the tax ID, contact name or phone. |
