import Foundation

/// Wording of the Owner app's accountability screens, copied exactly from
/// `docs/requirements/accountability-mobile-strings.md` (Android `OwnerAccountabilityTexts`).
public enum OwnerAccountabilityTexts {
    public static let moreAccountability = "Accountability" // owner.more.accountability

    // Approvals: section headers / empty lines
    public static let approvalsDiscounts = "Customer discounts"
    public static let approvalsDiscountsEmpty = "No discounts waiting."
    public static let approvalsCredit = "Credit arrangements"
    public static let approvalsCreditEmpty = "No credit arrangements waiting."
    public static let approvalsHoursTransfers = "Hours transfers"
    public static let approvalsHoursTransfersEmpty = "No hours transfers waiting."
    public static let approvalsCancellations = "Hours cancellations"
    public static let approvalsCancellationsEmpty = "No cancellations waiting."
    public static let approvalsBaselines = "Meter baselines"
    public static let approvalsBaselinesEmpty = "No baselines waiting."
    public static let approvalsClassifications = "Engine-hour classifications"
    public static let approvalsClassificationsEmpty = "No classifications waiting."
    public static let approvalsCorrections = "Reading corrections"
    public static let approvalsCorrectionsEmpty = "No corrections waiting."
    public static let approvalsWriteOffs = "Cash write-offs"
    public static let approvalsWriteOffsEmpty = "No write-offs waiting."
    public static let approvalsRetentions = "Cash retentions"
    public static let approvalsRetentionsEmpty = "No retention requests waiting."
    public static let approvalsAdjustments = "Custody adjustments"
    public static let approvalsAdjustmentsEmpty = "No adjustments waiting."
    public static func approvalsProposed(_ time: String) -> String { "Proposed \(time)" }

    // Approvals: row headlines
    public static func rowDiscount(_ percent: String) -> String { "\(percent)% discount" }
    public static func rowCredit(_ money: String) -> String { "Credit limit \(money)" }
    public static func rowHoursTransfer(_ hours: String) -> String { "Move \(hours) h to another machine" }
    public static let rowCancellation = "Cancel an hours purchase"
    public static func rowBaseline(reading: String, machine: String) -> String { "Baseline \(reading) h · \(machine)" }
    public static func rowClassification(hours: String, category: String) -> String { "\(hours) h · \(category)" }
    public static func rowCorrection(old: String, new: String, machine: String) -> String { "\(old) → \(new) h · \(machine)" }
    public static func rowWriteOff(_ money: String) -> String { "Write off \(money)" }
    public static func rowRetention(_ money: String) -> String { "Keep \(money)" }
    public static func rowAdjustment(kind: String, money: String) -> String { "\(kind) \(money)" }

    // Decision screen
    public static let decisionTitleDiscount = "Customer discount"
    public static let decisionTitleCredit = "Credit arrangement"
    public static let decisionTitleHoursTransfer = "Hours transfer"
    public static let decisionTitleCancellation = "Hours cancellation"
    public static let decisionTitleBaseline = "Meter baseline"
    public static let decisionTitleClassification = "Engine-hour classification"
    public static let decisionTitleCorrection = "Reading correction"
    public static let decisionTitleWriteOff = "Cash write-off"
    public static let decisionTitleRetention = "Cash retention"
    public static let decisionTitleAdjustment = "Custody adjustment"
    public static let decisionRequest = "Request"
    public static let decisionDecision = "Decision"
    public static let decisionApprove = "Approve"
    public static let decisionReject = "Reject"
    public static let decisionNoteOptional = "Note (optional to approve, required to reject)"
    public static let decisionNoteRequired = "Note (at least 5 characters)"
    public static let decisionOwnRequest = "Someone else must decide your own request"
    public static let decisionConfirmReject = "Reject this request?"
    public static let decisionApproved = "Approved."
    public static let decisionRejected = "Rejected."
    public static let decisionNotFoundTitle = "Request not found"
    public static let decisionNotFoundMessage = "It may already be decided."
    public static let decisionFooter = "The person who proposed a request can't decide it."

    // Decision screen: field labels
    public static let fieldDiscount = "Discount"
    public static let fieldEffectiveFrom = "Effective from"
    public static let fieldEffectiveTo = "Effective to"
    public static let fieldCreditLimit = "Credit limit"
    public static let fieldTerms = "Terms"
    public static let fieldHours = "Hours"
    public static let fieldFromMachine = "From machine"
    public static let fieldToMachine = "To machine"
    public static let fieldMachine = "Machine"
    public static let fieldReading = "Reading"
    public static let fieldOldReading = "Old reading"
    public static let fieldNewReading = "New reading"
    public static let fieldPeriod = "Period"
    public static let fieldCategory = "Category"
    public static let fieldOutcome = "Outcome"
    public static let fieldOutcomeNonCustomer = "Approved non-customer work"
    public static let fieldOutcomeVariance = "Identified difference"
    public static let fieldDeclared = "Declared"
    public static let fieldReceived = "Received"
    public static let fieldDifference = "Difference"
    public static let fieldAmount = "Amount"
    public static let fieldValidUntil = "Valid until"
    public static let fieldKind = "Kind"
    public static let fieldReason = "Reason"
    public static let fieldNote = "Note"
    public static let fieldProposedBy = "Proposed by"
    public static let fieldProposed = "Proposed"
    public static let fieldStatus = "Status"
    public static let fieldSource = "Source"
    public static let fieldCaptured = "Captured" // owner.field.captured
    public static let fieldWhen = "When" // owner.field.when
    // Gap pass (names, records, overdue remittances)
    public static let fieldCustomer = "Customer" // owner.field.customer
    public static let fieldPurchase = "Purchase" // owner.field.purchase
    public static let fieldJob = "Job" // owner.field.job
    public static let fieldCustodian = "Cash held by" // owner.field.custodian
    public static let fieldCounterparty = "Other custodian" // owner.field.counterparty
    public static let fieldRequestedBy = "Requested by" // owner.field.requestedBy
    public static let fieldDecidedBy = "Decided by" // owner.field.decidedBy
    public static let fieldDecisionNote = "Decision note" // owner.field.decisionNote
    public static let fieldFrom = "From" // owner.field.from
    public static let fieldTo = "To" // owner.field.to
    public static let fieldRecordedBy = "Recorded by" // owner.field.recordedBy
    public static let fieldAcknowledgedBy = "Acknowledged by" // owner.field.acknowledgedBy
    public static let fieldTransferred = "Transferred" // owner.field.transferred
    public static let fieldIssued = "Issued" // owner.field.issued
    public static let fieldDay = "Day" // owner.field.day
    public static let fieldCutoff = "Cut-off" // owner.field.cutoff
    public static let fieldNotRemitted = "Not remitted" // owner.field.notRemitted
    public static let fieldFlagged = "Flagged" // owner.field.flagged
    public static func approvalsProposedBy(_ time: String, _ name: String) -> String { "Proposed \(time) by \(name)" } // owner.approvals.proposedBy
    public static let recordTransferTitle = "Cash transfer" // owner.record.transferTitle
    public static let recordFloatTitle = "Cash float" // owner.record.floatTitle
    public static let recordNotFoundTitle = "Record not found" // owner.record.notFoundTitle
    public static let recordNotFoundMessage = "It may have been removed, or you may not have access to it." // owner.record.notFoundMessage
    public static let overdueTitle = "Overdue remittances" // owner.overdue.title
    public static let overdueDetailTitle = "Overdue remittance" // owner.overdue.detailTitle
    public static let overdueEmpty = "No overdue remittances today." // owner.overdue.empty
    /// "Still held after the 18:00 cut-off on 2026-10-25." (`hour` two digits).
    public static func overdueLine(hour: Int, day: String) -> String { // owner.overdue.line
        "Still held after the \(twoDigits(hour)):00 cut-off on \(day)."
    }
    static func twoDigits(_ hour: Int) -> String { hour < 10 ? "0\(hour)" : "\(hour)" }

    public static func outcome(_ raw: String) -> String {
        switch raw {
        case "APPROVED_NON_CUSTOMER": fieldOutcomeNonCustomer
        case "IDENTIFIED_VARIANCE": fieldOutcomeVariance
        default: OwnerFormat.humanize(raw)
        }
    }

    // Remittance confirm
    public static let remitAmountReceived = "Amount received"
    public static let remitAmountReceivedFooter = "Count the cash. A different amount opens a cash difference for review."
    public static let remitExpected = "Expected balance"
    public static let remitShortfall = "Not covered by a retention"
    public static let remitReceivedLabel = "Received"
    public static let remitErrAmount = "Enter the amount received (0 or more)."

    // Accountability dashboard
    public static let dashTitle = "Accountability"
    public static func dashFooter(version: String, time: String) -> String { "Policy \(version) · As of \(time)" }
    public static let dashHiddenNote = "Some tiles are hidden by your company's settings."
    public static let dashEmpty = "Nothing to show."
    public static let dashApprovals = "Outstanding approvals"
    public static let dashApprovalRequests = "Approval requests"
    public static let dashPaymentsToVerify = "Payments to verify"
    public static let dashRemittancesToVerify = "Remittances to verify"
    public static let dashCashRetentions = "Cash retentions"
    public static let dashCustodyAdjustments = "Custody adjustments"
    public static let dashWriteOffs = "Write-offs"
    public static let dashTotal = "Total"
    public static let dashCash = "Cash"
    public static let dashTransfersAwaiting = "Transfers awaiting acknowledgement"
    public static let dashFloatsAwaiting = "Floats awaiting acknowledgement"
    public static let dashRemittancesAwaiting = "Remittances awaiting confirmation"
    public static let dashPartialRemittances = "Partial remittances"
    public static let dashCustodians = "Cash per custodian"
    public static func dashCustodianLine(_ money: String) -> String { "\(money) outstanding" }
    public static func dashInTransit(_ money: String) -> String { "\(money) in transit" }
    public static let dashPayments = "Payments awaiting confirmation"
    public static let dashDiscrepancies = "Discrepancies"
    public static let dashOpenVariances = "Open cash differences"
    public static let dashWriteOffsProposed = "Write-offs proposed"
    public static let dashSyncConflicts = "Sync conflicts to review"
    public static let dashInvestigations = "Investigations"
    public static let dashOpen = "Open"
    public static let dashInReview = "In review"
    public static let dashAttempts = "Refused attempts"
    public static let dashPermissionDenied = "Permission refusals"
    public static let dashSod = "Own-request decisions refused"
    public static func dashWindow(_ days: Int) -> String { "Last \(days) days" }
    public static let dashCustomerHours = "Customer hours"
    public static let dashHoursActivated = "Activated"
    public static let dashHoursConsumed = "Consumed"
    public static let dashHoursRemaining = "Remaining"
    public static let dashHoursAwaiting = "Awaiting activation"
    public static let dashHoursExpired = "Expired"
    public static let dashOpenOverruns = "Hours beyond purchase"
    public static let dashHoursAwaitingTile = "Hours awaiting activation"
    public static let dashPurchasesAwaitingPayment = "Purchases awaiting payment"
    public static let dashPurchasesPartlyActive = "Purchases partly active"
    public static let dashEngineHours = "Engine hours"
    public static let dashMachines = "Machines"
    public static let dashStatusNoBaseline = "No baseline"
    public static let dashStatusReconciled = "Reconciled"
    public static let dashStatusPendingReview = "Pending review"
    public static let dashStatusUnexplained = "Unexplained hours"
    public static let dashUnexplained = "Unexplained engine hours"
    public static func dashUnexplainedLine(hours: String, days: Int) -> String { "\(hours) h · oldest \(days) days" }
    public static let dashMissingReports = "Missing daily reports"
    public static func dashMissingLine(machine: String, day: String) -> String { "\(machine) · \(day)" }
    public static func dashCount(_ count: Int, _ money: String) -> String { "\(count) · \(money)" }
    public static let dashNone = "None"
    public static let dashRemittancesOverdue = "Remittances overdue today" // owner.dash.remittancesOverdue
    public static func dashCutoff(_ hour: Int) -> String { "Cut-off \(twoDigits(hour)):00" } // owner.dash.cutoff

    /// Engine-hour reconciliation statuses with their dashboard labels (unknown ones humanized).
    public static func engineStatus(_ raw: String) -> String {
        switch raw {
        case "NO_BASELINE": dashStatusNoBaseline
        case "RECONCILED": dashStatusReconciled
        case "PENDING_REVIEW": dashStatusPendingReview
        case "UNEXPLAINED": dashStatusUnexplained
        default: OwnerFormat.humanize(raw)
        }
    }
}
