import AssetaModel
import AssetaNetwork
import AssetaStore // UUID.lowercased
import Foundation

// Cash records the Owner app opens exactly from a notification or the dashboard (DEC-030 G4/G5): one transfer, one
// float, the overdue-remittance flags of the tenant's daily cut-off (contracts/openapi.json).

extension SnapshotKey {
    public static func overdueRemittances(day: String) -> SnapshotKey { SnapshotKey("remittance_overdue.\(day)") }
    public static func overdueRemittance(_ id: UUID) -> SnapshotKey { SnapshotKey("remittance_overdue.\(id.lowercased)") }
    public static func cashTransfer(_ id: UUID) -> SnapshotKey { SnapshotKey("cash_transfer.\(id.lowercased)") }
    public static func cashFloat(_ id: UUID) -> SnapshotKey { SnapshotKey("cash_float.\(id.lowercased)") }
    public static func handover(_ id: UUID) -> SnapshotKey { SnapshotKey("cash_handover.\(id.lowercased)") }
}

extension OwnerAPI {
    /// Overdue-remittance flags of one tenant-local day (`YYYY-MM-DD`), newest first.
    public static func remittanceOverdue(day: String, pageSize: Int = 100) -> APIRequest<Page<RemittanceOverdueDTO>> {
        .get("\(tenant)/cash/remittance-overdue", query: paging(1, pageSize) + compact([("day_from", day), ("day_to", day)]))
    }

    public static func remittanceOverdue(_ id: UUID) -> APIRequest<RemittanceOverdueDTO> {
        .get("\(tenant)/cash/remittance-overdue/\(id.lowercased)")
    }

    public static func cashTransfer(_ id: UUID) -> APIRequest<CashTransferDTO> { .get("\(tenant)/cash/transfers/\(id.lowercased)") }

    public static func cashFloat(_ id: UUID) -> APIRequest<CashFloatDTO> { .get("\(tenant)/cash/floats/\(id.lowercased)") }

    /// One cash handover (remittance) by id.
    public static func cashHandover(_ id: UUID) -> APIRequest<CashHandoverDTO> { .get("\(tenant)/cash/handovers/\(id.lowercased)") }
}

/// Labelled values of the cash record screens (same order and wording as Android).
public enum CashRecordPresentation {
    typealias T = OwnerAccountabilityTexts

    static func fields(_ pairs: [(String, String?)]) -> [DecisionField] { PendingDecision.fields(pairs) }

    /// "TZS 50,000.00", one line per currency.
    public static func amounts(_ items: [RemittanceOverdueDTO.Amount]) -> String {
        items.isEmpty ? T.dashNone : items.map { OwnerFormat.money($0.amount, currency: $0.currency) }.joined(separator: "\n")
    }

    /// Row of the overdue list: the custodian, what they still hold and the cut-off they missed.
    public static func overdueRow(_ o: RemittanceOverdueDTO) -> (title: String, amounts: String, line: String) {
        (DisplayName.or(o.staffMemberName, id: o.staffMemberID), amounts(o.amounts), T.overdueLine(hour: o.cutoffHour, day: o.localDay))
    }

    public static func overdue(_ o: RemittanceOverdueDTO, timeZone: TimeZone = .current) -> [DecisionField] {
        fields([(T.fieldCustodian, DisplayName.or(o.staffMemberName, id: o.staffMemberID)), (T.fieldDay, o.localDay),
                (T.fieldCutoff, "\(T.twoDigits(o.cutoffHour)):00"), (T.fieldNotRemitted, amounts(o.amounts)),
                (T.fieldFlagged, OwnerFormat.stamp(o.flaggedAt, timeZone: timeZone))])
    }

    public static func transfer(_ t: CashTransferDTO, timeZone: TimeZone = .current) -> [DecisionField] {
        fields([(T.fieldFrom, DisplayName.or(t.fromStaffName, id: t.fromStaffID)),
                (T.fieldTo, DisplayName.or(t.toStaffName, id: t.toStaffID)),
                (T.fieldAmount, OwnerFormat.money(t.amountDeclared, currency: t.currency)),
                (T.fieldReceived, t.amountReceived.map { OwnerFormat.money($0, currency: t.currency) }),
                (T.fieldStatus, OwnerFormat.humanize(t.status)),
                (T.fieldTransferred, OwnerFormat.stamp(t.transferredAt, timeZone: timeZone)),
                (T.fieldRecordedBy, DisplayName.optional(t.recordedByName, id: t.recordedBy)),
                (T.fieldAcknowledgedBy, DisplayName.optional(t.acknowledgedByName, id: t.acknowledgedBy)),
                (T.fieldNote, t.note), (T.fieldDecisionNote, t.ackNote)])
    }

    public static func float(_ f: CashFloatDTO, timeZone: TimeZone = .current) -> [DecisionField] {
        fields([(T.fieldCustodian, DisplayName.or(f.staffMemberName, id: f.staffMemberID)),
                (T.fieldAmount, OwnerFormat.money(f.amount, currency: f.currency)),
                (T.fieldReceived, f.amountReceived.map { OwnerFormat.money($0, currency: f.currency) }),
                (T.fieldStatus, f.ackStatus.map(OwnerFormat.humanize)),
                (T.fieldIssued, OwnerFormat.stamp(f.occurredAt, timeZone: timeZone)),
                (T.fieldRecordedBy, f.createdByName), (T.fieldAcknowledgedBy, f.acknowledgedByName), (T.fieldNote, f.note)])
    }

    /// The tenant-local day of `date` (`YYYY-MM-DD`), for "today's" overdue flags.
    public static func localDay(_ date: Date, timeZone: TimeZone = .current) -> String {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        let c = calendar.dateComponents([.year, .month, .day], from: date)
        return String(format: "%04d-%02d-%02d", c.year ?? 0, c.month ?? 0, c.day ?? 0)
    }
}
