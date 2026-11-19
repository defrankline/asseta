import Foundation

// Machine report rules and wording that follow Android word for word (`ReportTexts`, `MachineReportRules`,
// `MachineReportScreen`): step 1 reading problems, the last reading's source and time, the photo caption and the sync
// refusals of a MACHINE_REPORT / CREDIT_INVOICE_PAYMENT.

extension MachineReportRules {
    public static let maxLines = 50

    /// Why step 1 cannot go on, or nil: the reading must be above the previous one (equal = nothing to report); with
    /// no previous reading (an opening report) any valid reading goes.
    public static func readingProblem(previous: Decimal?, reading: Decimal?) -> String? {
        guard let reading else { return MachineReportTexts.errReadingInvalid }
        guard let previous else { return nil }
        if reading < previous { return MachineReportTexts.errReadingLower }
        if reading == previous { return MachineReportTexts.errNothingToReport }
        return nil
    }

    /// "12 Nov, 17:30": a report time in the phone's time zone, English month, 24-hour clock (Android `dayTime`).
    public static func dayTime(_ date: Date, timeZone: TimeZone = .current) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = timeZone
        f.dateFormat = "d MMM, HH:mm"
        return f.string(from: date)
    }
}

extension MachineReportTexts {
    /// Where the last reading comes from: a baseline, a meter reset, else an approved report.
    public static func source(_ previousSource: String?) -> String {
        switch previousSource {
        case "BASELINE": "baseline"
        case "RESET": "meter reset"
        default: sourceApproved
        }
    }

    /// "Meter photo · read by the phone · GPS ±6 m" (the phone part only when the reading came from the photo, the
    /// GPS part only with a fix).
    public static func photoCaption(readByPhone: Bool, gps: String?) -> String {
        ["Meter photo", readByPhone ? "read by the phone" : nil, gps].compactMap { $0 }.joined(separator: " · ")
    }

    /// "GPS ±6 m", or "GPS" when the fix has no accuracy.
    public static func gpsAccuracy(_ meters: Double?) -> String {
        meters.map { "GPS ±\(Int($0.rounded())) m" } ?? "GPS"
    }

    /// Server refusals of a MACHINE_REPORT or CREDIT_INVOICE_PAYMENT kept for review (`field.report.conflict.*`);
    /// nil for other codes.
    public static func conflict(_ code: String?) -> String? {
        switch code {
        case "MACHINE_NOT_ASSIGNED": "This machine is no longer assigned to you. The report is kept for review."
        case "MACHINE_NOT_FOUND": "This machine is no longer on record. The report is kept for review."
        case "REPORT_PENDING": "Another report on this machine waits for approval. Send this one after it is decided."
        case "REPORT_ID_CONFLICT": "This report was already sent with other details. It is kept for review."
        case "BASELINE_REQUIRED": "This machine has no starting reading yet. The office sets it first; the report is kept for review."
        case "READING_NOT_HIGHER": "The new reading is below the machine's last reading. The report is kept for review."
        case "NOTHING_TO_REPORT": "The reading is the same as the last one, so there is nothing to report."
        case "REPORT_SUM_MISMATCH": "The hours do not add up to the meter difference. Redo the split."
        case "HOURS_NOT_AVAILABLE": "A customer no longer has enough usable hours. Redo the split."
        case "HOURS_DISABLED": "Your company has switched off customer hours, so customer lines were not accepted."
        case "REASON_INVALID", "REASON_NOT_FOUND": "A reason you chose is no longer in use. Redo the split."
        case "CUSTOMER_NOT_FOUND": "A customer you chose is no longer on record. Redo the split."
        case "CAPTURE_REJECTED": "The meter reading was not accepted. Take the reading again."
        case "CAPTURE_ALREADY_REPORTED": "This reading already has a report."
        case "CAPTURE_ALREADY_USED": "This reading was already used in another report. Take a new reading."
        case "CORRECTION_NOT_ALLOWED", "CORRECTS_INVALID": "A rejected report can't be corrected; send a new report with a new reading."
        case "HOURS_PRECISION": "The hours have more than 2 decimals."
        case "DUPLICATE_CUSTOMER_LINE": "A customer appears twice. Redo the split."
        case "INVOICE_PAID": "This invoice is already paid. The payment is kept for review."
        case "INVOICE_OVERPAYMENT": "The payment is more than the invoice still owes. It is kept for review."
        case "INVOICE_CANCELLED": "This invoice was cancelled. The payment is kept for review."
        case "INVOICE_NOT_FOUND": "This invoice is no longer on record. The payment is kept for review."
        case "PAYMENT_NOT_PERMITTED": "Bank and mobile-money payments are recorded by the office."
        default: nil
        }
    }
}
