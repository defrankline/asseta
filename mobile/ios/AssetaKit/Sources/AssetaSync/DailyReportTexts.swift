import AssetaModel
import Foundation

/// Wording of the daily report and changeover field screens, copied exactly from
/// `docs/requirements/accountability-mobile-strings.md`, section "DEC-032 Phase 1" (Android `DailyReportTexts`).
public enum DailyReportTexts {
    public static let menu = "Daily reports" // field.report.menu
    public static let action = "Daily report for this machine" // field.report.action
    public static let listTitle = "Daily reports" // field.report.listTitle
    public static let sectionReturned = "Sent back to you" // field.report.sectionReturned
    public static let sectionMine = "My reports" // field.report.sectionMine
    public static let empty = "No daily reports yet" // field.report.empty
    public static let emptyHint = "Reports you send for your machines appear here." // field.report.emptyHint
    public static let staleFooter = "Connect to see the office's latest answers." // field.report.staleFooter
    public static func rowLine(total: String, billable: String) -> String { "\(total) h in total · \(billable) h billable" } // field.report.rowLine

    /// field.report.status.* (unknown → humanized wire value).
    public static func status(_ wire: String) -> String {
        switch wire {
        case DailyReportStatuses.submitted: "Sent"
        case DailyReportStatuses.reviewed: "Reviewed"
        case DailyReportStatuses.returned: "Sent back"
        case DailyReportStatuses.superseded: "Replaced"
        default: FieldRevenueTexts.humanize(wire)
        }
    }
    public static let statusWaiting = "Waiting to sync" // field.report.status.waiting
    public static let statusNotAccepted = "Not accepted" // field.report.status.notAccepted

    public static let formTitle = "Daily report" // field.report.formTitle
    public static let resubmitTitle = "Send report again" // field.report.resubmitTitle
    public static let machine = "Machine" // field.report.machine
    public static let day = "Day" // field.report.day
    public static let readings = "Readings" // field.report.readings
    public static let opening = "Opening reading" // field.report.opening
    public static let closing = "Closing reading" // field.report.closing
    public static let chooseReading = "Choose a reading" // field.report.chooseReading
    public static func readingOption(reading: String, dateTime: String) -> String { "\(reading) · \(dateTime)" } // field.report.readingOption
    public static func readingNotSynced(reading: String, dateTime: String) -> String { "\(reading) · \(dateTime) · not synced yet" } // field.report.readingNotSynced
    public static let noReadings = "No readings for this day on this phone. Capture a reading first." // field.report.noReadings
    public static let total = "Hours between the readings" // field.report.total
    public static let readingsFooter = "Taken from your readings. You can choose others." // field.report.readingsFooter
    public static let billable = "Billable hours (optional)" // field.report.billable
    public static let billableFooter = "Left empty, the billable hours are the total minus the unbillable hours." // field.report.billableFooter
    public static let unbillable = "Unbillable hours" // field.report.unbillable
    public static let reason = "Reason" // field.report.reason
    public static let chooseReason = "Choose a reason" // field.report.chooseReason
    public static let reasonHours = "Hours" // field.report.reasonHours
    public static let addReason = "Add a reason" // field.report.addReason
    public static let removeReason = "Remove" // field.report.removeReason
    public static let reasonsEmpty = "Your company has no unbillable reasons yet. Ask the office." // field.report.reasonsEmpty
    public static let notAccounted = "Not accounted for" // field.report.notAccounted
    public static let note = "Note (optional)" // field.report.note
    public static let photoOptional = "Photo (optional)" // field.report.photoOptional
    public static let photoRequired = "Photo (required)" // field.report.photoRequired
    public static let photoFooter = "Stored encrypted on this phone and uploaded before the report is sent." // field.report.photoFooter
    public static let takePhoto = "Take photo" // field.report.takePhoto
    public static let addPhoto = "Add another photo" // field.report.addPhoto
    public static let removePhoto = "Remove" // field.report.removePhoto
    public static let send = "Send report" // field.report.send
    public static let repeatWarning = "A report for this machine and day was already sent. A repeat is kept and flagged for review." // field.report.repeatWarning
    public static let resubmitFooter = "This replaces the report that was sent back." // field.report.resubmitFooter
    public static let officeNote = "The office's note" // field.report.officeNote

    public static let errOpening = "Choose the opening reading." // field.report.error.opening
    public static let errClosing = "Choose the closing reading." // field.report.error.closing
    public static let errSameReading = "Choose two different readings." // field.report.error.sameReading
    public static let errBillable = "Enter the billable hours as a number (0 or more, at most 2 decimal places)." // field.report.error.billable
    public static let errReasonMissing = "Choose a reason for each line of unbillable hours." // field.report.error.reasonMissing
    public static let errReasonHours = "Enter the hours for each reason (more than 0, at most 2 decimal places)." // field.report.error.reasonHours
    public static let errReasonRepeated = "Each reason can be used once." // field.report.error.reasonRepeated
    public static func errExceeds(_ total: String) -> String { "Billable and unbillable hours are more than the \(total) h between the readings." } // field.report.error.exceeds
    public static let errPhoto = "Your company requires a photo with this report." // field.report.error.photo

    public static let detailTitle = "Daily report" // field.report.detailTitle
    public static let totalHours = "Total hours" // field.report.totalHours
    public static let billableHours = "Billable hours" // field.report.billableHours
    public static let unbillableHours = "Unbillable hours" // field.report.unbillableHours
    public static let openingValue = "Opening reading" // field.report.opening.value
    public static let closingValue = "Closing reading" // field.report.closing.value
    public static let submitted = "Sent" // field.report.submitted
    public static let submittedBy = "Sent by" // field.report.submittedBy
    public static let reviewedBy = "Reviewed by" // field.report.reviewedBy
    public static let returnedBy = "Sent back by" // field.report.returnedBy
    public static let flagLate = "Sent after the daily cut-off" // field.report.flagLate
    public static let flagRepeat = "Repeat report for this day" // field.report.flagRepeat
    public static let allocations = "Hours by customer" // field.report.allocations
    public static let resubmit = "Correct and send again" // field.report.resubmit
    public static let notFound = "Report not available" // field.report.notFound
    public static let notFoundHint = "Connect to load it, or it is no longer on this phone." // field.report.notFoundHint
    public static let outbox = "Daily report" // field.report.outbox
    public static let waitingPhotos = "Waiting for its photos to upload" // field.report.waitingPhotos
    public static let statusLabel = "Status" // field.report.statusLabel
    public static let noteLabel = "Note" // field.report.noteLabel
    public static let photos = "Photos" // field.report.photos
    public static let syncSection = "Sync" // field.report.sync
    public static let onThisPhone = "On this phone" // field.report.onThisPhone

    /// Hours with 2 decimals at most and no trailing zeros, in a plain format (Android `DailyReportTexts.hours`).
    public static func hours(_ value: Decimal) -> String {
        var v = value, rounded = Decimal()
        NSDecimalRound(&rounded, &v, 2, .bankers)
        return AccountabilityRules.plain(rounded)
    }

    // Changeover
    public static let changeoverAction = "Record changeover" // field.changeover.action
    public static let changeoverTitle = "Changeover reading" // field.changeover.title
    public static let changeoverFooter = "Take this reading when the machine moves to the next customer while this job is still running." // field.changeover.footer
    public static let changeoverNextCustomer = "Next customer" // field.changeover.nextCustomer
    public static let changeoverChooseCustomer = "Choose the customer" // field.changeover.chooseCustomer
    public static let changeoverNextJob = "Next job (optional)" // field.changeover.nextJob
    public static let changeoverNextJobRequired = "Next job (required)" // field.changeover.nextJobRequired
    public static let changeoverChooseJob = "Choose the job" // field.changeover.chooseJob
    public static let changeoverNoJobs = "No job for this customer on this phone yet. Ask the office to create it." // field.changeover.noJobs
    public static let changeoverErrorCustomer = "Choose the next customer." // field.changeover.errorCustomer
    public static let changeoverErrorJob = "Choose the next job. Your company bills the hours after a changeover to that job." // field.changeover.errorJob
    public static let changeoverOutbox = "Changeover reading" // field.changeover.outbox
    /// Recorder refusals, same wording as Android `CaptureMeterReading` / `DailyReportCapture`.
    public static let changeoverNotRunning = "A changeover can be recorded only while this job is running."
    public static let readingNotAccepted = "One of these readings was not accepted by the server. Choose another reading."

    /// field.allocation.kind.* (unknown → humanized wire value).
    public static func allocationKind(_ wire: String) -> String {
        switch wire {
        case AllocationKinds.customerWork: "Customer work"
        case AllocationKinds.authorizedActivity: "Authorized activity"
        case AllocationKinds.unexplained: "Unexplained"
        default: FieldRevenueTexts.humanize(wire)
        }
    }

    /// field.conflict.* of the daily report and changeover operations; nil = not one of these codes.
    public static func conflict(_ code: String?) -> String? {
        switch code {
        case "REPORT_READINGS_INVALID": "The readings in this report are no longer valid or do not fit the day. Send the report again with other readings."
        case "REPORT_HOURS_EXCEED_TOTAL": "Billable and unbillable hours are more than the hours between the readings. Send the report again."
        case "REPORT_ID_CONFLICT": "This report could not be saved because its id is already used. Send the report again."
        case "REPORT_NOT_SUPERSEDABLE": "That report can no longer be replaced. It may have been reviewed already."
        case "REPORT_EVIDENCE_REQUIRED": "Your company requires a photo with this report. Send the report again with a photo."
        case "REASON_NOT_ALLOWED": "One of the reasons is no longer in use. Send the report again with another reason."
        case "CHANGEOVER_NOT_ALLOWED": "This job was no longer running, so the changeover was not accepted."
        case "CHANGEOVER_SAME_CUSTOMER": "The machine is already working for this customer, so the changeover was not accepted."
        case "CHANGEOVER_JOB_REQUIRED": "Your company bills the hours after a changeover to the next job. Record the changeover again and choose the job."
        case "CHANGEOVER_JOB_INVALID": "That job can no longer follow this one. It must still be waiting for approval, on this machine, for that customer."
        default: nil
        }
    }
}
