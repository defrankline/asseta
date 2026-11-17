import AssetaModel
import AssetaNetwork
import AssetaStore // UUID.lowercased
import Foundation

// ADR-008 machine reports on the Owner app as on Android (`ui/reports/ReportPresentation.kt`, `ReportApprovalScreen.kt`):
// list rows, the read line with the phone's OCR, the GPS line, the tracker sentence, why no buttons, done and refusal
// messages.

/// Machine-report wording of the Owner app (Android `ReportTexts`).
public enum ReportTexts {
    public static let screenTitle = "Machine report"
    public static let kind = "MACHINE REPORT"
    public static let customers = "CUSTOMERS"
    public static let nonProductive = "NON-PRODUCTIVE"
    public static let reasonLabel = "Reason (needed to reject)"
    public static let reasonPlaceholder = "e.g. Idle hours too high, explain"
    public static let noteLabel = "Supervisor's note"
    public static let approve = "Approve"
    public static let reject = "Reject"
    public static let cancel = "Cancel"
    public static let confirmReject = "Reject this report?"
    public static let confirmRejectText = "The supervisor is told your reason and corrects the split on the same reading."
    public static let approved = "Report approved. The customers' hours are used."
    public static let rejected = "Report rejected. The supervisor will correct it."
    public static let ownReport = "You submitted this report, so someone else must approve or reject it."
    public static let noPermission = "Only people allowed to approve machine reports can decide it."
    /// The photo button: "View meter photo" / "Meter photo (online only)".
    public static let viewPhoto = "meter photo"
    public static let noTracker = "No tracker data for this period."
    public static let statusApproved = "Approved"
    public static let statusRejected = "Rejected"
    public static let statusWaiting = "Awaiting approval"
    public static let notFoundTitle = "Report not found"
    public static let notFoundMessage = "It may have been removed, or you can no longer see it."
    public static let firstReading = "First reading — starting point"
    public static let openingNote = "The machine's first reading, so there are no hours to split. Approving it makes this reading the starting point; the next report counts hours from it."
    public static let openingApproved = "Reading approved. The next report counts hours from it."

    /// Plain sentences for the server's refusal codes on approve / reject (else `fallback`).
    public static func refusal(_ code: String?, fallback: String) -> String {
        switch code {
        case "SEGREGATION_OF_DUTIES": "You submitted this report, so you can't decide it. Someone else with approval rights must."
        case "REPORT_NOT_PENDING": "This report was already decided by someone else. It has been refreshed."
        case "REPORT_READINGS_CHANGED":
            "The machine's previous reading changed after this report was sent (a baseline or meter reset). Reject it so the supervisor can send it again."
        case "HOURS_NOT_AVAILABLE":
            "A customer no longer has these hours (cancelled or expired). Reject the report so the supervisor can correct it."
        case "REPORT_NOT_FOUND": "This report no longer exists."
        default: fallback
        }
    }
}

/// The reading behind a report (`getMeterCapture`, `tenant.meter.read`): the phone's OCR value and the GPS fix.
public struct ReportCaptureDTO: Codable, Hashable, Sendable {
    public let id: UUID
    public let reading: DecimalString
    public let captureMode: String
    public let ocrValue: String?
    public let photoAttachmentID: UUID?
    /// Kept as text so a status added later never breaks the screen.
    public let gpsStatus: String
    public let latitude: Double?
    public let accuracyM: Double?

    public init(id: UUID = UUID(), reading: Decimal, captureMode: String = "OCR", ocrValue: String? = nil,
                photoAttachmentID: UUID? = nil, gpsStatus: String = "FIX", latitude: Double? = nil, accuracyM: Double? = nil) {
        self.id = id
        self.reading = DecimalString(reading)
        self.captureMode = captureMode
        self.ocrValue = ocrValue
        self.photoAttachmentID = photoAttachmentID
        self.gpsStatus = gpsStatus
        self.latitude = latitude
        self.accuracyM = accuracyM
    }

    enum CodingKeys: String, CodingKey {
        case id, reading, latitude, captureMode = "capture_mode", ocrValue = "ocr_value"
        case photoAttachmentID = "photo_attachment_id", gpsStatus = "gps_status", accuracyM = "accuracy_m"
    }
}

extension OwnerAPI {
    /// `GET /meter-captures/{id}` (`tenant.meter.read`).
    public static func reportCapture(_ id: UUID) -> APIRequest<ReportCaptureDTO> { .get("\(tenant)/meter-captures/\(id.lowercased)") }
}

extension SnapshotKey {
    public static func reportCapture(_ id: UUID) -> SnapshotKey { SnapshotKey("meter-capture.\(id.lowercased)") }
}

/// Pure presentation of machine reports (Android `ReportPresentation`).
public enum ReportPresentation {
    public static func machine(_ r: MachineReportDTO) -> String { r.machineCode ?? r.machineName ?? r.reportNumber }

    public static func customerLines(_ r: MachineReportDTO) -> [MachineReportDTO.Line] { r.lines.filter { $0.lineKind == .customer } }

    public static func nonProductiveLines(_ r: MachineReportDTO) -> [MachineReportDTO.Line] {
        r.lines.filter { $0.lineKind == .nonProductive }
    }

    /// "EX-01 · 300 h · Daudi Mollel" (an opening report has no hours: "EX-01 · Daudi Mollel").
    public static func rowTitle(_ r: MachineReportDTO) -> String {
        [machine(r), r.isOpening ? nil : OwnerFigures.hours(r.hours.value), r.submittedByName.flatMap { $0.isBlank ? nil : $0 }]
            .compactMap { $0 }.joined(separator: " · ")
    }

    /// Short reason ("transit", "breakdown"): the code in words, else the name.
    public static func reasonShort(_ l: MachineReportDTO.Line) -> String {
        l.reasonCode.map { $0.lowercased().replacingOccurrences(of: "_", with: " ") } ?? l.reasonName?.lowercased() ?? "non-productive"
    }

    /// "220 h to 2 customers · 80 h non-productive"; one customer is named ("38 h Mji Mpya Housing"), one reason too
    /// ("4 h transit"). Without lines (a list row may carry none): the totals. An opening report: "First reading —
    /// starting point".
    public static func split(_ r: MachineReportDTO) -> String {
        if r.isOpening { return ReportTexts.firstReading }
        let customers = customerLines(r)
        let reasons = nonProductiveLines(r)
        let customerHours = r.customerHours.value
        let idle = r.nonProductiveHours.value
        var parts: [String] = []
        if customerHours > 0 {
            switch customers.count {
            case 1: parts.append("\(OwnerFigures.hours(customerHours)) \(customers[0].customerName ?? "a customer")")
            case 0: parts.append("\(OwnerFigures.hours(customerHours)) to customers")
            default: parts.append("\(OwnerFigures.hours(customerHours)) to \(customers.count) customers")
            }
        }
        if idle > 0 {
            parts.append(reasons.count == 1 ? "\(OwnerFigures.hours(idle)) \(reasonShort(reasons[0]))" : "\(OwnerFigures.hours(idle)) non-productive")
        }
        return parts.isEmpty ? OwnerFigures.hours(r.hours.value) : parts.joined(separator: " · ")
    }

    /// "1,210 → 1,510 h"; an opening report has one reading: "1,520.4 h".
    public static func readings(_ r: MachineReportDTO) -> String {
        if r.isOpening { return "\(OwnerFigures.hoursNumber(r.endReading.value)) h" }
        return "\(OwnerFigures.hoursNumber(r.startReading.value)) → \(OwnerFigures.hoursNumber(r.endReading.value)) h"
    }

    /// "300 h · read by phone 1510.0 ✓" (or "typed by hand"); just the hours without the reading. An opening report:
    /// "First reading — starting point · typed by hand".
    public static func readLine(_ r: MachineReportDTO, capture: ReportCaptureDTO?) -> String {
        let hours = r.isOpening ? ReportTexts.firstReading : OwnerFigures.hours(r.hours.value)
        guard let capture else { return hours }
        let how: String?
        if let ocr = capture.ocrValue, !ocr.isBlank {
            how = "read by phone \(ocr)" + (OwnerFigures.dec(ocr) == capture.reading.value
                ? " ✓" : " · typed \(OwnerFigures.hoursNumber(capture.reading.value))")
        } else if capture.captureMode == "MANUAL" {
            how = "typed by hand"
        } else {
            how = nil
        }
        return [hours, how].compactMap { $0 }.joined(separator: " · ")
    }

    /// "GPS: ±6 m" or "GPS: no fix"; nil without the reading.
    public static func gpsLine(_ capture: ReportCaptureDTO?) -> String? {
        guard let capture else { return nil }
        if capture.latitude != nil, let accuracy = capture.accuracyM { return "GPS: ±\(Int(accuracy.rounded())) m" }
        if capture.latitude != nil { return "GPS: position recorded" }
        return "GPS: \(capture.gpsStatus.lowercased().replacingOccurrences(of: "_", with: " "))"
    }

    /// "· 140 → 20 h left" from the customer's available hours before this report (submitted reports only).
    public static func beforeAfter(_ l: MachineReportDTO.Line) -> String? {
        guard let before = l.availableHours?.value else { return nil }
        let after = max(before - l.hours.value, 0)
        return "· \(OwnerFigures.hoursNumber(before)) → \(OwnerFigures.hoursNumber(after)) h left"
    }

    /// “Hydraulic hose replaced on site” (curly quotes, as the design).
    public static func quoted(_ note: String?) -> String? {
        guard let text = note?.trimmingCharacters(in: .whitespacesAndNewlines), !text.isEmpty else { return nil }
        return "“\(text)”"
    }

    /// The tracker cross-check sentence; an opening report has no period, so it says what approving it does.
    public static func tracker(_ r: MachineReportDTO) -> String {
        if r.isOpening { return ReportTexts.openingNote }
        guard let t = r.tracker, t.available, let tracked = t.trackerHours?.value else { return ReportTexts.noTracker }
        let meter = t.meterHours.value
        return "Tracker engine hours for the same period: \(OwnerFigures.hours(tracked)) (meter \(OwnerFigures.hours(meter)))."
    }

    /// Why the decision buttons are not offered (nil: this person may decide, or the report is already decided).
    public static func cannotDecide(_ decision: MachineReportApproval.Decision) -> String? {
        switch decision {
        case .ownReport: ReportTexts.ownReport
        case .notPermitted: ReportTexts.noPermission
        case .allowed, .decided: nil
        }
    }

    /// The message after a decision (an approved opening report sets the starting point; it uses no hours).
    public static func decided(_ r: MachineReportDTO, approved: Bool) -> String {
        if !approved { return ReportTexts.rejected }
        return r.isOpening ? ReportTexts.openingApproved : ReportTexts.approved
    }

    public static func statusLabel(_ r: MachineReportDTO) -> String {
        switch r.state {
        case .approved?: ReportTexts.statusApproved
        case .rejected?: ReportTexts.statusRejected
        default: ReportTexts.statusWaiting
        }
    }

    /// "Daudi Mollel · today 07:40".
    public static func attentionDetail(_ r: MachineReportDTO, now: Date = Date(), timeZone: TimeZone = .current) -> String {
        [r.submittedByName.flatMap { $0.isBlank ? nil : $0 }, OwnerFigures.relative(r.submittedAt, now: now, timeZone: timeZone)]
            .compactMap { $0 }.joined(separator: " · ")
    }
}

private extension String {
    var isBlank: Bool { trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
}
