import AssetaModel
import AssetaStore
@testable import AssetaSync
import Foundation
import Testing

/// Timed work-log entries (local until stopped) and the completion rules that mirror the server.
struct WorkLogTests {
    @Test func runningEntryIsLocalUntilStoppedThenQueuedOnce() throws {
        let h = try SyncHarness()
        let job = SyncFixtures.jobDTO
        let (_, start) = try h.recordOpeningAndStart()
        let entry = try h.recorder.startEntry(job: job, type: .downtime, startedAt: h.clock.wallNow, note: " hose ")
        #expect(try h.recorder.runningEntry(jobID: job.id) == entry)
        #expect(try h.store.outbox.operations(tenantID: SyncFixtures.tenant, jobID: job.id)
            .allSatisfy { $0.opType != OperationType.jobActivity.rawValue })
        #expect(throws: FieldRecorderError.notAllowed("Stop the running entry first.")) {
            try h.recorder.startEntry(job: job, type: .work, startedAt: h.clock.wallNow, note: nil)
        }
        #expect(try h.recorder.workLog(jobID: job.id).map(\.isRunning) == [true])

        h.clock.advance(600)
        let op = try h.recorder.stopEntry(job: job, at: h.clock.wallNow)
        #expect(op.dependencies == [start.id])
        #expect(op.entityID == entry.clientID)
        let payload = try JSONValue.parse(op.payloadJSON)
        #expect(payload["activity_type"]?.stringValue == "DOWNTIME")
        #expect(payload["note"]?.stringValue == "hose")
        #expect(payload["ended_at"]?.stringValue != nil)
        #expect(try h.recorder.runningEntry(jobID: job.id) == nil)
        #expect(throws: FieldRecorderError.self) { try h.recorder.stopEntry(job: job) }
        let log = try h.recorder.workLog(jobID: job.id)
        #expect(log.count == 1 && log[0].type == .downtime && !log[0].isRunning && log[0].endedAt != nil)
    }

    @Test func workMayBeLoggedOnAnApprovedJobAndNotesNeedText() throws {
        let h = try SyncHarness()
        let job = SyncFixtures.jobDTO
        #expect(try h.recorder.progress(jobID: job.id, serverStatus: .approved).canLogActivity)
        #expect(throws: FieldRecorderError.invalid("Write a note first.")) {
            try h.recorder.recordActivity(job: job, type: .note, startedAt: h.clock.wallNow, endedAt: nil, billable: nil,
                                          note: "  ")
        }
        let mobilization = try h.recorder.recordActivity(job: job, type: .mobilization, startedAt: h.clock.wallNow,
                                                         endedAt: h.clock.wallNow.addingTimeInterval(60), billable: true,
                                                         note: nil)
        #expect(mobilization.dependencies.isEmpty)
    }

    @Test func completeNeedsAcknowledgementAndNoRunningEntry() throws {
        let h = try SyncHarness()
        let job = SyncFixtures.jobDTO
        try h.recordOpeningAndStart()
        try h.recorder.startEntry(job: job, type: .work, startedAt: h.clock.wallNow, note: nil)
        let closing = try h.recorder.recordCapture(
            job: job, kind: .closing, mode: .manual, reading: "1240.0", ocr: nil, photo: nil, gps: .failed(.disabled),
            capturedAt: h.clock.wallNow, snapshot: SyncFixtures.meterSnapshot)
        var progress = try h.recorder.progress(jobID: job.id, serverStatus: .approved)
        #expect(progress.canAcknowledge && !progress.canComplete)
        #expect(throws: FieldRecorderError.notAllowed("Get the customer acknowledgement first.")) {
            try h.recorder.recordTransition(job: job, action: .complete)
        }
        let ack = try h.recorder.recordAcknowledgement(job: job, method: .nameConfirmation, signerName: "Ann",
                                                       signerPhone: nil, signature: nil, acknowledgedHours: nil)
        progress = try h.recorder.progress(jobID: job.id, serverStatus: .approved)
        #expect(progress.canComplete && !progress.canAcknowledge)
        #expect(throws: FieldRecorderError.notAllowed("Stop the running work-log entry first.")) {
            try h.recorder.recordTransition(job: job, action: .complete)
        }
        let activity = try h.recorder.stopEntry(job: job, at: h.clock.wallNow)
        let complete = try h.recorder.recordTransition(job: job, action: .complete)
        #expect(Set(complete.dependencies) == [closing.id, ack.id, activity.id])
    }
}

struct CashLineTests {
    @Test func estimatedCashInHandExcludesClaimedHandoversAndPendingSpending() {
        let synced = CashCustodyBalanceDTO(staffMemberID: UUID(), currency: "TZS", outstanding: DecimalString(1000),
                                           claimedUnverifiedHandovers: DecimalString(300),
                                           pendingSpending: DecimalString(50), asOf: Date())
        let line = CashLine(currency: "TZS", synced: synced, pendingCollections: 200, pendingHandovers: 100,
                            pendingCashExpenses: Decimal(string: "20.5")!)
        #expect(line.unverifiedNet == Decimal(string: "79.5")!)
        #expect(line.projected == Decimal(string: "1079.5")!)
        #expect(line.estimatedInHand == Decimal(string: "729.5")!)
        #expect(CashLine(currency: "TZS", synced: nil, pendingCollections: 40).estimatedInHand == 40)
    }

    @Test func collectionForAnotherCustomersJobIsRefused() throws {
        let h = try SyncHarness()
        #expect(throws: FieldRecorderError.invalid("Job J-1001 belongs to another customer.")) {
            try h.recorder.recordCashCollection(customerID: UUID(), amountText: "10", currency: "", reference: nil,
                                                note: nil, jobNumber: "J-1001", jobCustomerID: UUID(), receivedAt: Date())
        }
        #expect(try h.store.outbox.statusCounts(tenantID: SyncFixtures.tenant).values.reduce(0, +) == 0)
    }
}
