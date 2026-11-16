import AssetaModel
@testable import AssetaSync
import Foundation
import Testing

/// The Supervisor machine report reads like Android (`ReportTexts`, `MachineReportRules`, `MachineReportScreen`).
@Suite("Machine report: same wording and rules as Android")
struct MachineReportParityTests {
    @Test func readingProblemsOfStepOne() {
        #expect(MachineReportRules.readingProblem(previous: 1210, reading: nil) == "Enter the new reading.")
        #expect(MachineReportRules.readingProblem(previous: 1210, reading: 1200)
            == "The new reading is below the last reading. Check the number, or ask the office about a meter reset.")
        #expect(MachineReportRules.readingProblem(previous: 1210, reading: 1210)
            == "No difference since the last reading? Nothing to report.")
        #expect(MachineReportRules.readingProblem(previous: 1210, reading: 1510) == nil)
        // An opening report has no previous reading: any valid reading goes.
        #expect(MachineReportRules.readingProblem(previous: nil, reading: 0) == nil)
    }

    @Test func machineStatesAndOutboxTitle() {
        #expect(MachineReportStanding.opening.label == "First reading needed")
        #expect(MachineReportStanding.awaitingApproval(notSent: true).label == "Awaiting approval")
        #expect(MachineReportStanding.awaitingApproval(notSent: false).label == "Awaiting approval")
        #expect(MachineReportStanding.rejected(reportID: UUID()).label == "Rejected · redo the split")
        #expect(MachineReportStanding.due.label == "Report due")
        #expect(MachineReportStanding.upToDate.label == "Up to date")
        #expect(FieldAccountabilityTexts.operationTitle(.machineReport, payload: .object(["opening": .bool(true)])) == "Machine report")
        #expect(FieldAccountabilityTexts.operationTitle(.machineReport, payload: nil) == "Machine report")
    }

    @Test func lastReadingSourceTimeAndPhotoCaption() {
        #expect(MachineReportTexts.source("BASELINE") == "baseline")
        #expect(MachineReportTexts.source("RESET") == "meter reset")
        #expect(MachineReportTexts.source("REPORT") == "approved")
        #expect(MachineReportTexts.source(nil) == "approved")
        let utc = TimeZone(identifier: "UTC")!
        let at = ISO8601DateFormatter().date(from: "2026-11-12T17:30:00Z")!
        #expect(MachineReportRules.dayTime(at, timeZone: utc) == "12 Nov, 17:30")
        #expect(MachineReportTexts.photoCaption(readByPhone: true, gps: MachineReportTexts.gpsAccuracy(6.4))
            == "Meter photo · read by the phone · GPS ±6 m")
        #expect(MachineReportTexts.photoCaption(readByPhone: false, gps: nil) == "Meter photo")
        #expect(MachineReportTexts.photoCaption(readByPhone: false, gps: MachineReportTexts.gpsAccuracy(nil)) == "Meter photo · GPS")
    }

    @Test func readingsAndHoursUseUSGrouping() {
        #expect(MachineReportRules.readingText(1210, decimalPlaces: 1) == "1,210.0")
        #expect(MachineReportRules.hoursText(Decimal(string: "3182.8")!) == "3,182.8")
        #expect(MachineReportTexts.reconcileTitle("EX-01", MachineReportRules.hoursText(1210), MachineReportRules.hoursText(1510))
            == "EX-01 · 1,210 → 1,510")
    }

    @Test func stepTextsAndRejection() {
        #expect(MachineReportTexts.step(1, MachineReportTexts.stepReading) == "Step 1 of 3 · New reading")
        #expect(MachineReportTexts.step(2, MachineReportTexts.stepSplit) == "Step 2 of 3 · Account for hours")
        #expect(MachineReportTexts.step(3, MachineReportTexts.stepReview) == "Step 3 of 3 · Review & submit")
        #expect(MachineReportTexts.rejected("Wrong customer") == "Rejected: Wrong customer. Split the same reading again.")
        #expect(MachineReportTexts.rejected("  ") == "Rejected. Split the same reading again.")
        #expect(MachineReportTexts.rejected(nil) == "Rejected. Split the same reading again.")
        #expect(MachineReportTexts.periodLine(nil, "13 Nov, 08:10") == "13 Nov, 08:10 · photo + GPS")
        #expect(MachineReportTexts.periodLine("12 Nov, 17:30", "13 Nov, 08:10") == "12 Nov, 17:30 → 13 Nov, 08:10 · photo + GPS")
        #expect(MachineReportTexts.leftToAccount(-2) == "2 h more than the meter shows")
    }

    @Test func refusalsOfAReportReadInPlainWords() {
        #expect(FieldAccountabilityTexts.conflictText("REPORT_PENDING")
            == "Another report on this machine waits for approval. Send this one after it is decided.")
        #expect(FieldAccountabilityTexts.conflictText("REASON_NOT_FOUND") == "A reason you chose is no longer in use. Redo the split.")
        #expect(FieldAccountabilityTexts.conflictText("INVOICE_PAID") == "This invoice is already paid. The payment is kept for review.")
        #expect(FieldAccountabilityTexts.conflictText("HOURS_NOT_AVAILABLE")
            == "A customer no longer has enough usable hours. Redo the split.")
        #expect(FieldAccountabilityTexts.conflictText("VALIDATION_FAILED") == nil)
    }
}
