import AssetaModel
import Foundation

/// Wording of the accountability field screens (Supervisor app), copied exactly from
/// `docs/requirements/accountability-mobile-strings.md` (Android `FieldAccountabilityTexts` / `AccountabilityMessages`).
/// The comment after each constant is its key in that file.
public enum FieldAccountabilityTexts {
    // Money tab "+" menu
    public static let menuSellHours = "Sell customer hours" // field.menu.sellHours
    public static let menuRequestHoursTransfer = "Request hours transfer" // field.menu.requestHoursTransfer
    public static let menuTransferCash = "Transfer cash to a colleague" // field.menu.transferCash
    public static let menuAskToKeepCash = "Ask to keep cash" // field.menu.askToKeepCash

    // Screen titles
    public static let titleHoursSale = "Sell customer hours"
    public static let titleHoursTransfer = "Request hours transfer"
    public static let titleCashTransfer = "Transfer cash"
    public static let titleAcknowledgeTransfer = "Cash transfer"
    public static let titleAcknowledgeFloat = "Cash float"
    public static let titleRetention = "Ask to keep cash"
    public static let titleDailyReading = "Daily reading"
    public static let titleBaseline = "Propose meter baseline"
    public static let titleCorrection = "Propose reading correction"

    // Common
    public static let cashHolder = "Cash held by"
    public static let me = "Me"
    public static let reasonCategory = "Reason category"
    public static let reasonCategoryOptional = "Reason category (optional)"
    public static let noCategory = "No category"
    public static let reason = "Reason"
    public static let noteOptional = "Note (optional)"
    public static let amount = "Amount"
    public static let currency = "Currency"
    public static let needsRules = "Connect once so this phone can load your company's rules for this."
    public static let serverTooOld = "Your company's server does not accept this from the app yet."
    public static let onlineOnly = "Connect to the internet to send this request."
    public static func lastUpdated(_ time: String) -> String { "Last updated \(time)." }
    public static let errCurrency = "Enter a 3-letter currency code." // field.common.errCurrency
    public static let send = "Send" // field.common.send

    // Sell customer hours
    public static let hoursSectionCustomer = "Customer"
    public static let hoursRegistered = "Registered"
    public static let hoursWalkIn = "Walk-in"
    public static let hoursCustomer = "Customer"
    public static let hoursCustomerEmpty = "Customers appear here after a sync."
    public static let hoursWalkInName = "Customer name"
    public static let hoursWalkInPhone = "Phone (optional)"
    public static let hoursWalkInFooter = "The office gives a walk-in customer a code. A phone number helps find them again."
    public static let hoursSectionHours = "Hours"
    public static let hoursMachine = "Machine"
    public static let hoursHours = "Hours"
    public static let hoursHoursFooter = "The price comes from your company's rate card and any approved discount."
    public static let hoursSectionPayment = "Payment"
    public static let hoursPaidNow = "Paid now"
    public static let hoursNotPaid = "Not paid yet"
    public static let hoursMethodCash = "Cash"
    public static let hoursMethodBank = "Bank"
    public static let hoursMethodMobileMoney = "Mobile money"
    public static let hoursAmountReceived = "Amount received"
    public static let hoursReference = "Reference (required for bank and mobile money)"
    public static let hoursReceived = "Received"
    public static let hoursPaymentFooter = "Hours become available only after someone else verifies this payment."
    public static let hoursNotPaidFooter = "The hours stay inactive until a payment is verified or credit is approved by the office."
    public static let hoursEvidence = "Payment evidence (optional)"
    public static let hoursEvidenceFooter = "Receipt or mobile-money screenshot. Stored encrypted on this phone and uploaded before the sale is sent."
    public static let hoursPhotograph = "Photograph evidence"
    public static let hoursAddPhoto = "Add another photo"
    public static let hoursErrCustomer = "Choose the customer."
    public static let hoursErrWalkInName = "Enter the customer's name."
    public static let hoursErrPhone = "The phone number must have at least 3 characters."
    public static let hoursErrMachine = "Choose the machine."
    public static let hoursErrHours = "Enter the hours (more than 0, at most 2 decimal places)."
    public static let hoursErrAmount = "Enter the amount received (more than 0)."
    public static let hoursErrReference = "Enter the reference for bank and mobile-money payments."
    public static let hoursErrWalkInOff = "Walk-in customers are turned off for your company."
    public static let hoursOff = "Customer hours are turned off for your company."

    // Request hours transfer
    public static let transferPurchase = "Purchase"
    public static func transferPurchaseOption(number: String, hours: String) -> String { "\(number) · \(hours) h left" }
    public static let transferPurchasesEmpty = "No purchases with hours left. Purchases appear here after you connect."
    public static let transferFromMachine = "From machine"
    public static let transferToMachine = "To machine"
    public static let transferHours = "Hours to move"
    public static let transferFooterApproval = "Someone else approves the transfer before the hours move."
    public static let transferFooterDirect = "The hours move when the server accepts the request."
    public static let transferErrPurchase = "Choose the purchase."
    public static let transferErrMachine = "Choose the machine to move the hours to."
    public static let transferErrSameMachine = "Choose a different machine from the one the hours are on."
    public static let transferErrHours = "Enter the hours to move (more than 0, at most 2 decimal places)."
    public static func transferErrTooMany(_ hours: String) -> String { "Only \(hours) h are left on this purchase." }
    public static let transferErrReason = "Enter a reason (at least 3 characters)."
    public static let transferErrCategory = "Choose a reason category."

    // Transfer cash
    public static let cashTransferFrom = "From"
    public static let cashTransferTo = "To"
    public static let cashTransferAmount = "Amount handed over"
    public static let cashTransferWhen = "Transferred"
    public static let cashTransferAmountReceived = "Amount you received"
    public static let cashTransferFooterAck = "The cash stays with the sender until the receiver acknowledges it."
    public static let cashTransferFooterNoAck = "The cash moves to the receiver when the server accepts the transfer."
    public static let cashTransferFooterSelf = "Recording a transfer you receive counts as your acknowledgement."
    public static let cashTransferCustodiansEmpty = "Colleagues who hold cash appear here after you connect."
    public static let cashTransferErrTo = "Choose who receives the cash."
    public static let cashTransferErrSame = "The sender and the receiver must be different people."
    public static let cashTransferErrAmount = "Enter the amount (more than 0)."
    public static let cashTransferErrReceived = "Enter the amount you received (0 or more)."
    public static let currencyError = errCurrency

    // Acknowledge a transfer or a float
    public static let ackSection = "Cash to acknowledge"
    public static func ackTransferFrom(_ name: String) -> String { "Transfer from \(name)" }
    public static let ackFloatFromOffice = "Float from the office"
    public static let ackSomeone = "A colleague"
    public static let ackDeclared = "Declared amount"
    public static let ackSent = "Sent"
    public static let ackIssued = "Issued"
    public static let ackAmountReceived = "Amount received"
    public static let ackAcknowledge = "Acknowledge"
    public static let ackDispute = "Dispute"
    public static let ackDisputeReason = "Why you dispute it"
    public static let ackFooter = "A different amount opens a cash difference for the office to review."
    public static let ackErrReceived = "Enter the amount you received (0 or more)."
    public static let ackErrReason = "Say why you dispute it."
    public static let ackWaiting = "Your answer is waiting to sync."
    public static let ackNotFound = "This item is no longer waiting for you."

    // Money tab "Transfers" segment
    public static let moneyTransfers = "Transfers"
    public static let moneyTransfersEmptyTitle = "No cash transfers"
    public static let moneyTransfersEmptyMessage = "Cash moved between you and colleagues appears here."
    public static func moneyTransferTo(_ name: String) -> String { "To \(name)" }
    public static func moneyTransferFrom(_ name: String) -> String { "From \(name)" }
    public static let moneyStatusPendingAck = "Awaiting acknowledgement"
    public static let moneyStatusAcknowledged = "Acknowledged"
    public static let moneyStatusDisputed = "Disputed"

    // Ask to keep cash
    public static let retentionAmount = "Amount to keep"
    public static let retentionValidUntil = "Keep until (optional)"
    public static let retentionFooter = "Someone else approves this. Until then the full balance is expected when you remit."
    public static let retentionSent = "Request sent for approval."
    public static let retentionErrAmount = "Enter the amount to keep (more than 0)."
    public static let retentionErrReason = "Enter a reason (at least 3 characters)."
    public static let retentionOff = "Your company does not allow keeping cash."
    // Gap pass: offline request and its status
    public static let retentionSaved = "Saved. It is sent when the phone syncs." // field.retention.saved
    public static let retentionViewStatus = "View request status" // field.retention.viewStatus
    public static let titleRetentionStatus = "Request to keep cash" // field.title.retentionStatus
    public static let retentionStatusPending = "Waiting for approval" // field.retention.statusPending
    public static let retentionStatusApproved = "Approved" // field.retention.statusApproved
    public static let retentionStatusRejected = "Rejected" // field.retention.statusRejected
    public static let retentionNotSynced = "This request has not reached the server yet." // field.retention.notSynced
    public static let retentionOffline = "Connect to the internet to see whether it was approved." // field.retention.offline
    public static let retentionNotFound = "This request is not on this phone." // field.retention.notFound
    public static let retentionRequested = "Requested" // field.retention.requested
    public static let retentionDecidedBy = "Decided by" // field.retention.decidedBy
    public static let retentionDecisionNote = "Decision note" // field.retention.decisionNote
    public static let retentionStatus = "Status" // field.retention.status
    public static let moneyRetentions = "Requests to keep cash" // field.money.retentions

    /// A retention's server status in plain words (unknown statuses humanized).
    public static func retentionStatusText(_ status: String) -> String {
        switch status {
        case "PENDING": retentionStatusPending
        case "APPROVED": retentionStatusApproved
        case "REJECTED": retentionStatusRejected
        default: status.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    // Follow-up F2: overdue remittance
    public static let titleRemittanceOverdue = "Overdue remittance" // field.title.remittanceOverdue
    public static let overdueCustodian = "Cash held by" // field.overdue.custodian
    public static let overdueNotRemitted = "Not remitted" // field.overdue.notRemitted
    public static let overdueDay = "Day" // field.overdue.day
    public static let overdueCutoff = "Cut-off" // field.overdue.cutoff
    public static let overdueFlagged = "Flagged" // field.overdue.flagged
    public static let overdueHint = "Remit this cash to the office as soon as you can." // field.overdue.hint

    // DEC-031 D3: held longer than allowed
    public static let overdueReason = "Reason" // field.overdue.reason
    public static let overdueReasonCutoff = "Not remitted by the daily cut-off" // field.overdue.reasonCutoff
    public static let overdueReasonHeld = "Held longer than allowed" // field.overdue.reasonHeld
    public static let overdueHeldSince = "Held since" // field.overdue.heldSince
    public static let overdueAllowed = "Allowed" // field.overdue.allowed
    public static let overdueHeldLineShort = "Held longer than allowed." // field.overdue.heldLineShort

    /// "1 day" / "N days" (field.overdue.days).
    public static func days(_ n: Int) -> String { n == 1 ? "1 day" : "\(n) days" }

    /// "Held since {date}, longer than the allowed {days}." (field.overdue.heldLine)
    public static func overdueHeldLine(date: String, days: Int) -> String {
        "Held since \(date), longer than the allowed \(Self.days(days))."
    }

    // DEC-031 D2: remittance details on "Hand over cash"
    public static let remitMethod = "How was it handed over?" // field.remit.method
    public static let remitMethodCash = "Cash to the office" // field.remit.methodCash
    public static let remitMethodBank = "Bank deposit" // field.remit.methodBank
    public static let remitMethodMobile = "Mobile money" // field.remit.methodMobile
    public static let remitAccount = "Paid into" // field.remit.account
    public static let remitAccountOptional = "Paid into (optional)" // field.remit.accountOptional
    public static let remitAccountNone = "No account" // field.remit.accountNone
    public static let remitAccountsEmpty = "Your company's accounts for this currency appear here after a sync." // field.remit.accountsEmpty
    public static let remitReference = "Transaction reference" // field.remit.reference
    public static let remitReferenceOptional = "Reference (deposit slip, transaction no.) (optional)" // field.remit.referenceOptional
    public static let remitPhotos = "Deposit slip or payment confirmation" // field.remit.photos
    public static let remitPhotosOptional = "Deposit slip or payment confirmation (optional)" // field.remit.photosOptional
    public static let remitPhotosFooter = "Stored encrypted on this phone and uploaded before the handover is sent." // field.remit.photosFooter
    public static let remitPhotograph = "Photograph the slip" // field.remit.photograph
    public static let remitAddPhoto = "Add another photo" // field.remit.addPhoto
    public static let remitRemovePhoto = "Remove" // field.remit.removePhoto
    public static let remitErrAccount = "Choose the company account the money was paid into." // field.remit.errAccount
    public static let remitErrReference = "Enter the transaction reference of the bank deposit or mobile-money payment." // field.remit.errReference
    public static let remitErrEvidence = "Photograph the deposit slip or payment confirmation." // field.remit.errEvidence
    public static let outboxWaitingPhotos = "Waiting for its photos to upload" // field.outbox.waitingPhotos

    /// The method's label (field.remit.method*).
    public static func remitMethodText(_ method: RemittanceMethod) -> String {
        switch method {
        case .cashToOffice: remitMethodCash
        case .bankDeposit: remitMethodBank
        case .mobileMoney: remitMethodMobile
        }
    }

    /// "07:00" (two-digit hour).
    public static func hour(_ h: Int) -> String { String(format: "%02d:00", h) }

    /// "Still held after the 18:00 cut-off on 2026-10-25." (field.overdue.line)
    public static func overdueLine(cutoffHour: Int, day: String) -> String {
        "Still held after the \(hour(cutoffHour)) cut-off on \(day)."
    }

    /// Conflicts and refusals of the accountability ops in plain words (`field.conflict.*`); nil = show the code.
    public static func conflictText(_ code: String?) -> String? {
        switch code {
        case "RETENTION_NOT_ALLOWED": "Your company does not allow keeping cash, so this request was not accepted."
        case "DUPLICATE_RETENTION": "This request to keep cash was already sent."
        case "ENGINE_HOURS_DISABLED": "Your company has switched off engine-hour controls, so this was not accepted."
        case "CASH_CUSTODY_DISABLED": "Your company has switched off cash custody controls, so this was not accepted."
        case "REMITTANCE_REFERENCE_REQUIRED":
            "Your company requires the transaction reference for bank and mobile-money remittances. Record the handover again with the reference."
        case "REMITTANCE_EVIDENCE_REQUIRED":
            "Your company requires a photo of the deposit slip or payment confirmation. Record the handover again with a photo."
        case "REMITTANCE_ACCOUNT_REQUIRED":
            "Your company requires the account the money was paid into. Record the handover again and choose the account."
        case "DEPOSIT_ACCOUNT_INACTIVE": "The account you chose is no longer in use. Record the handover again with another account."
        case "REMITTANCE_ACCOUNT_MISMATCH":
            "The account you chose does not match how the money was handed over. Record the handover again."
        case "DEPOSIT_ACCOUNT_CURRENCY_MISMATCH":
            "The account you chose holds a different currency. Record the handover again with another account."
        default: nil
        }
    }

    // Readings
    public static let meterRecordDaily = "Record daily reading"
    public static let meterProposeBaseline = "Propose meter baseline"
    public static let meterProposeCorrection = "Propose a correction"
    public static let meterKindDaily = "Daily"
    public static let meterKindBaseline = "Baseline"
    public static let meterDailyFooter = "A daily reading outside a job keeps the machine's engine hours accounted for."
    public static let meterBaselineFooter = "Someone else approves the baseline before it counts."
    public static let meterBaselineNote = "Note (optional)"
    public static let meterCorrectionOf = "Reading to correct"
    public static let meterCorrectionReason = "Reason for the correction"
    public static let meterCorrectionFooter = "The corrected reading replaces the old one only after someone else approves it."
    public static let meterErrCorrectionReason = "Enter a reason of at least 10 characters."
    public static let meterCorrectionNotSynced = "A reading can be corrected once the server has it."
    public static let meterCorrectionNotLive = "Only a reading the server still counts can be corrected."
    public static let meterReadingKindDaily = "Daily reading" // field.meter.readingKindDaily
    public static let meterNeedsSync = "Sync once while online before recording this." // field.meter.needsSync
    public static let meterMachineMissing = "This machine is not on this device." // field.meter.machineMissing

    // Sync status titles (outbox)
    public static let outboxHoursSale = "Hours sale"
    public static let outboxHoursTransfer = "Hours transfer request"
    public static let outboxCashTransfer = "Cash transfer"
    public static let outboxTransferAck = "Transfer acknowledgement"
    public static let outboxFloatAck = "Float acknowledgement"
    public static let outboxBaseline = "Meter baseline proposal"
    public static let outboxCorrection = "Reading correction proposal"
    public static let outboxDailyReading = "Daily reading"
    public static let outboxRetention = "Request to keep cash" // field.outbox.retention

    /// Messages of the recorder (same wording as Android `AccountabilityCapture`).
    public static let tooManyEvidence = "At most 10 evidence photos per sale."
    public static let customerGone = "This customer is no longer active. Choose another one."
    public static let machineMissing = "This machine is not on this device."
    public static let alreadySaved = "This is already saved."

    /// Outbox title of an accountability operation (nil for other operations).
    public static func operationTitle(_ type: OperationType, payload: JSONValue?) -> String? {
        switch type {
        case .hoursPurchase: outboxHoursSale
        case .hoursTransferRequest: outboxHoursTransfer
        case .cashTransfer: outboxCashTransfer
        case .cashTransferAcknowledgement: outboxTransferAck
        case .cashFloatAcknowledgement: outboxFloatAck
        case .meterBaseline: outboxBaseline
        case .meterCorrection: outboxCorrection
        case .cashRetentionRequest: outboxRetention
        case .meterCapture where payload?["kind"]?.stringValue == ReadingKind.daily.rawValue: outboxDailyReading
        default: nil
        }
    }

    /// Payment methods of the sale form with their labels.
    public static let paymentMethods: [(wire: String, label: String)] = [
        ("CASH", hoursMethodCash), ("BANK", hoursMethodBank), ("MOBILE_MONEY", hoursMethodMobileMoney),
    ]
}

/// "Overdue remittance" (Supervisor, follow-up F2): wording and rows in the Android order
/// (`RemittanceOverdueText`).
public enum RemittanceOverduePresentation {
    typealias T = FieldAccountabilityTexts

    /// The custodian's name, else the short id.
    public static func name(_ o: RemittanceOverdueDTO) -> String { DisplayName.or(o.staffMemberName, id: o.staffMemberID) }

    /// "TZS 50,000.00, USD 20.00" (the amounts still held when flagged).
    public static func amounts(_ o: RemittanceOverdueDTO) -> String {
        o.amounts.map { money($0.amount.value, currency: $0.currency) }.joined(separator: ", ")
    }

    /// The reason in plain words (field.overdue.reasonCutoff / reasonHeld).
    public static func reason(_ o: RemittanceOverdueDTO) -> String { o.heldTooLong ? T.overdueReasonHeld : T.overdueReasonCutoff }

    /// "20 Oct 2026": the day the oldest unremitted cash was received (nil when the server sent none).
    public static func heldSince(_ o: RemittanceOverdueDTO, timeZone: TimeZone = .current) -> String? {
        o.heldSince.map { day($0, timeZone: timeZone) }
    }

    /// Label/value rows in screen order (`flagged` formats the server timestamp); blank values are left out.
    /// Cash held by, Not remitted, Reason, Day, Cut-off (CUTOFF only), Held since and Allowed (HELD_TOO_LONG only),
    /// Flagged.
    public static func rows(_ o: RemittanceOverdueDTO, flagged: (Date) -> String,
                            timeZone: TimeZone = .current) -> [(label: String, value: String)] {
        var pairs: [(String, String?)] = [(T.overdueCustodian, name(o)), (T.overdueNotRemitted, amounts(o)),
                                          (T.overdueReason, reason(o)), (T.overdueDay, o.localDay)]
        if o.heldTooLong {
            pairs += [(T.overdueHeldSince, heldSince(o, timeZone: timeZone)), (T.overdueAllowed, o.maxHoldingDays.map(T.days))]
        } else {
            pairs.append((T.overdueCutoff, T.hour(o.cutoffHour)))
        }
        pairs.append((T.overdueFlagged, flagged(o.flaggedAt)))
        return pairs.compactMap { label, value in
            guard let value, !value.trimmingCharacters(in: .whitespaces).isEmpty else { return nil }
            return (label: label, value: value)
        }
    }

    /// The reason's line, then the hint: "Still held after the 18:00 cut-off on 2026-10-25. Remit this cash to the
    /// office as soon as you can." / "Held since 2026-10-20, longer than the allowed 3 days. Remit …"
    public static func footer(_ o: RemittanceOverdueDTO, timeZone: TimeZone = .current) -> String {
        "\(line(o, timeZone: timeZone)) \(T.overdueHint)"
    }

    static func line(_ o: RemittanceOverdueDTO, timeZone: TimeZone) -> String {
        guard o.heldTooLong else { return T.overdueLine(cutoffHour: o.cutoffHour, day: o.localDay) }
        guard let since = heldSince(o, timeZone: timeZone), let days = o.maxHoldingDays else { return T.overdueHeldLineShort }
        return T.overdueHeldLine(date: since, days: days)
    }

    /// "24 Oct 2026": the day of `date` in `timeZone` (English month, as Android `OwnerFormat.date`).
    static func day(_ date: Date, timeZone: TimeZone) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = timeZone
        f.dateFormat = "d MMM yyyy"
        return f.string(from: date)
    }

    /// "TZS 50,000.00": the currency code, then the amount with grouping and two decimals (as Android).
    static func money(_ amount: Decimal, currency: String) -> String {
        let number = amount.formatted(.number.precision(.fractionLength(2)).grouping(.automatic)
            .locale(Locale(identifier: "en_US")))
        return "\(currency) \(number)"
    }
}
