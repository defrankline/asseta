import AssetaModel
import AssetaStore
@testable import AssetaSync
import Foundation
import Testing

/// Inbox rules and wording, identical to Android `InboxRulesTest` / `InboxTextsTest`.
struct InboxRulesTests {
    @Test func localOutboxStatesMapToWaitingNotSyncedAndSynced() {
        #expect(InboxStatusRules.local(.pending) == .waiting)
        #expect(InboxStatusRules.local(.sent) == .waiting)
        #expect(InboxStatusRules.local(.quarantined) == .waiting)
        #expect(InboxStatusRules.local(.failed) == .notSynced)
        #expect(InboxStatusRules.local(.conflict) == .notSynced)
        #expect(InboxStatusRules.local(.acked) == .synced)
        #expect(InboxStatus.waiting.label == "Waiting to sync")
    }

    @Test func readingStatusCombinesStateReviewAndFindings() {
        #expect(InboxStatusRules.reading(state: "ACCEPTED", reviewStatus: "NONE", findingStatuses: []) == .accepted)
        #expect(InboxStatusRules.reading(state: "PROVISIONAL", reviewStatus: "NONE", findingStatuses: []) == .provisional)
        #expect(InboxStatusRules.reading(state: "PROVISIONAL", reviewStatus: "PENDING_REVIEW", findingStatuses: ["OPEN"]) == .flagged)
        #expect(InboxStatusRules.reading(state: "ACCEPTED", reviewStatus: "NONE", findingStatuses: ["EXPLAINED", "OPEN"]) == .flagged)
        #expect(InboxStatusRules.reading(state: "PROVISIONAL", reviewStatus: "REVIEWED", findingStatuses: ["CONFIRMED"]) == .reviewed)
        #expect(InboxStatusRules.reading(state: "REJECTED", reviewStatus: "PENDING_REVIEW", findingStatuses: ["OPEN"]) == .rejected)
        #expect(InboxStatusRules.reading(state: "SUPERSEDED", reviewStatus: "NONE", findingStatuses: []) == .superseded)
        #expect(InboxStatus.flagged.needsAttention && !InboxStatus.reviewed.needsAttention)
    }

    @Test func financeAndResetStatuses() {
        #expect(InboxStatusRules.expense("PENDING_APPROVAL") == .pendingApproval)
        #expect(InboxStatusRules.expense("APPROVED") == .approved)
        #expect(InboxStatusRules.expense("REJECTED") == .rejected)
        #expect(InboxStatusRules.settlement("CLAIMED") == .claimed)
        #expect(InboxStatusRules.settlement("VERIFIED") == .verified)
        #expect(InboxStatusRules.settlement("REJECTED") == .rejected)
        #expect(InboxStatusRules.reset("PENDING") == .pending)
        #expect(InboxStatusRules.reset("APPROVED") == .approved)
        #expect(InboxStatus.claimed.label == "Awaiting verification")
        #expect(InboxStatusRules.combined(local: .acked, server: .approved) == .approved)
        #expect(InboxStatusRules.combined(local: .pending, server: nil) == .waiting)
        #expect(InboxStatusRules.combined(local: .acked, server: nil) == .synced)
    }

    struct S { let id: UUID; let clientID: UUID? }
    struct L: Equatable { let entityID: UUID; let serverID: UUID? }

    @Test func mergesLocalAndServerRecordsByClientIDOrAcknowledgedServerID() {
        let (s1, c1, s2, s3, x2, c9) = (UUID(), UUID(), UUID(), UUID(), UUID(), UUID())
        let server = [S(id: s1, clientID: c1), S(id: s2, clientID: nil), S(id: s3, clientID: UUID())]
        let local = [L(entityID: c1, serverID: nil), L(entityID: x2, serverID: s2), L(entityID: c9, serverID: nil),
                     L(entityID: c1, serverID: nil)]
        let merged = InboxMerge.merge(server: server, local: local, serverKeys: { [$0.id] + ($0.clientID.map { [$0] } ?? []) },
                                      localKey: { LocalKey(entityID: $0.entityID, serverID: $0.serverID) })
        #expect(merged.count == 5)
        #expect(merged[0].local == L(entityID: c1, serverID: nil))
        #expect(merged[1].local == L(entityID: x2, serverID: s2))
        #expect(merged[2].local == nil)
        #expect(merged.dropFirst(3).map(\.local) == [L(entityID: c9, serverID: nil), L(entityID: c1, serverID: nil)])
        #expect(merged.dropFirst(3).allSatisfy { $0.server == nil })
    }

    @Test func workTotalsPerTypeAndMeterHours() {
        let t0 = Date(timeIntervalSince1970: 0)
        let h: TimeInterval = 3600
        let totals = JobFigures.minutesByType(
            [WorkSpan(activityType: "WORK", start: t0, end: t0 + 2 * h),
             WorkSpan(activityType: "STANDBY", start: t0 + 2 * h, end: t0 + 3 * h),
             WorkSpan(activityType: "WORK", start: t0 + 3 * h, end: nil),
             WorkSpan(activityType: "NOTE", start: t0, end: nil)],
            now: t0 + 3 * h + 30 * 60)
        #expect(totals.map(\.type) == ["WORK", "STANDBY"] && totals.map(\.minutes) == [150, 60])
        #expect(JobFigures.duration(minutes: 150) == "2 h 30 min")
        #expect(JobFigures.duration(minutes: 45) == "45 min")
        #expect(JobFigures.meterHours(opening: "100.0", closing: "108.5") == Decimal(string: "8.5"))
        #expect(JobFigures.meterHours(opening: "100", closing: nil) == nil)
        #expect(JobFigures.meterHours(opening: "100", closing: "90") == nil)
    }

    @Test func notificationTargetsOpenTheRelatedItem() {
        let id = UUID()
        #expect(InboxLink.from(entity: "job", id: id.uuidString) == .job(id))
        #expect(InboxLink.from(entity: "expense", id: id.uuidString) == .expense(id))
        #expect(InboxLink.from(entity: "staff_member", id: "s") == .money)
        #expect(InboxLink.from(entity: "screen", id: nil) == InboxLink.none)
    }

    @Test func resetRequestChecks() {
        #expect(ResetRules.validate(oldReading: "9999.9", newReading: "0", reason: "Meter replaced by workshop", hasPhoto: true).isEmpty)
        #expect(ResetRules.validate(oldReading: "x", newReading: "", reason: "short", hasPhoto: false).count == 4)
        #expect(ResetRules.parse("12,5") == "12.5")
    }

    @Test func findingAndTabWording() {
        #expect(FindingTexts.type("METER_DECREASE") == "Reading lower than before")
        #expect(FindingTexts.type("BRAND_NEW") == "Brand new")
        #expect(FindingTexts.review("OPEN") == "Waiting for review")
        #expect(SupervisorTab.allCases.map(\.label) == ["Jobs", "Readings", "Fuel", "Money", "Inbox"])
        #expect(JobSegment.allCases.map(\.label) == ["In progress", "Ready to start", "Recently closed", "My machines"])
        #expect(InboxTexts.segment(.inProgress) == .inProgress)
        #expect(InboxTexts.segment(.approved) == .ready)
        #expect(InboxTexts.segment(.completed) == .closed && InboxTexts.segment(.cancelled) == .closed)
        #expect(InboxTexts.jobsEmpty(.closed).title == "No recently closed jobs")
    }

    @Test func readingGpsAndMoneyWording() {
        #expect(InboxTexts.readingKind("OPENING") == "Opening reading")
        #expect(InboxTexts.readingKind("CLOSING") == "Closing reading")
        #expect(InboxTexts.gps(status: "FIX", latitude: -6.8, longitude: 39.2, accuracyM: 12.4) == "-6.80000, 39.20000 (±12 m)")
        #expect(InboxTexts.gps(status: "TIMEOUT", latitude: nil, longitude: nil, accuracyM: nil) == "No GPS fix within 20 seconds")
        #expect(InboxTexts.confidence(0.92) == "92 %")
        #expect(InboxTexts.money("25000.0000", "TZS") == "25000 TZS")
        #expect(InboxTexts.litres("12.500") == "12.5 L")
        #expect(InboxTexts.hours(Decimal(string: "8.50")!) == "8.5 h")
        #expect(InboxTexts.paidFrom("CASH_CUSTODY") == "My cash")
        #expect(InboxTexts.fuelType("ISSUE") == "Issue")
        #expect(InboxTexts.reviewOutcome("PENDING_REVIEW", findings: 1) == "Waiting for the office to review")
        #expect(InboxTexts.reviewOutcome("NONE", findings: 0) == "No findings")
    }

    @Test func moneyListsAreGroupedByWhoHasTheRecord() {
        let groups = InboxTexts.moneyGroups([InboxStatus.rejected, .waiting, .approved, .pendingApproval, .synced]) { $0 }
        #expect(groups.map(\.title) == ["On this phone", "Pending approval", "Approved", "Rejected"])
        #expect(groups.first?.items == [.waiting, .synced])
        #expect(InboxTexts.inboxBadge(unread: 3, attention: 2) == 5)
        #expect(InboxTexts.attentionTitle(.handover) == "Cash handover")
        #expect(InboxTexts.attentionDetail(.rejected) == "Rejected by the office")
    }
}
