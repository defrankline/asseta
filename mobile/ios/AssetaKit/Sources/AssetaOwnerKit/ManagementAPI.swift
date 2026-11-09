import AssetaModel
import AssetaNetwork
import AssetaStore // UUID.lowercased
import Foundation

// DEC-032 Phase 4 in the Owner app: the management view's requests. Reads may come from the encrypted snapshot cache
// like every Owner screen, except the reference lookup, which is always a live question.

extension SnapshotKey {
    public static func accountabilityPeriod(from: String?, to: String?) -> SnapshotKey {
        from == nil && to == nil ? .accountability : SnapshotKey("accountability.summary.\(from ?? "").\(to ?? "")")
    }
    public static func pendingAdjustments(recordType: String?, all: Bool, query: String?) -> SnapshotKey {
        SnapshotKey("accountability.pending.\(recordType ?? "all").\(all).\(query ?? "")")
    }
    public static func employeeAccountability(_ id: UUID, from: String?, to: String?) -> SnapshotKey {
        SnapshotKey("employee.accountability.\(id.lowercased).\(from ?? "").\(to ?? "")")
    }
}

extension OwnerAPI {
    /// `GET /accountability/pending-adjustments?record_type&all_approvals&q&page&page_size`.
    public static func pendingAdjustments(recordType: String? = nil, allApprovals: Bool = false, query: String? = nil,
                                          page: Int = 1, pageSize: Int = 100) -> APIRequest<Page<PendingItemDTO>> {
        .get("\(tenant)/accountability/pending-adjustments", query: paging(page, pageSize) + compact([
            ("record_type", recordType), ("all_approvals", allApprovals ? "true" : nil), ("q", query.nonEmpty),
        ]))
    }

    /// `GET /employees/{staff_member_id}/accountability?date_from&date_to`.
    public static func employeeAccountability(_ id: UUID, from: String? = nil, to: String? = nil) -> APIRequest<EmployeeAccountabilityDTO> {
        .get("\(tenant)/employees/\(id.lowercased)/accountability", query: compact([("date_from", from), ("date_to", to)]))
    }

    /// `GET /lookup?reference=`: every record a reference number points at.
    public static func lookup(reference: String) -> APIRequest<LookupResultDTO> {
        .get("\(tenant)/lookup", query: [URLQueryItem(name: "reference", value: reference.trimmingCharacters(in: .whitespacesAndNewlines))])
    }
}
