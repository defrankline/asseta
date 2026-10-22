import AssetaModel
import AssetaNetwork
import AssetaStore // UUID.lowercased
import Foundation

/// Typed requests of the Owner app. Reads are plain GETs; the only business mutations are the
/// alert action and the approval decision (plus the user's own inbox, routing and push device).
/// Every request is re-authorized by the server; nothing here decides access.
public enum OwnerAPI {
    static let tenant = "/api/v1/tenant"

    public static func overview() -> APIRequest<TenantOverviewDTO> { .get("\(tenant)/overview") }

    public static func fleetMap() -> APIRequest<[MachineMapDTO]> { .get("\(tenant)/fleet/map") }

    public static func machine(_ id: UUID) -> APIRequest<MachineMapDTO> {
        .get("\(tenant)/fleet/machines/\(id.lowercased)")
    }

    /// Track between `from` and `to` (the server allows at most 31 days).
    public static func history(_ id: UUID, from: Date, to: Date) -> APIRequest<HistoryDTO> {
        .get("\(tenant)/fleet/machines/\(id.lowercased)/history", query: [
            URLQueryItem(name: "from", value: AssetaJSON.formatInstant(from)),
            URLQueryItem(name: "to", value: AssetaJSON.formatInstant(to)),
        ])
    }

    public static func jobs(status: JobStatus? = nil, machineID: UUID? = nil, query: String? = nil,
                            page: Int = 1, pageSize: Int = 50) -> APIRequest<Page<JobDTO>> {
        .get("\(tenant)/jobs", query: paging(page, pageSize) + compact([
            ("status", status?.rawValue), ("machine_id", machineID?.lowercased), ("q", query.nonEmpty),
        ]))
    }

    public static func jobSummary(_ id: UUID) -> APIRequest<JobSummaryDTO> { .get("\(tenant)/jobs/\(id.lowercased)") }

    public static func alerts(status: AlertStatus? = nil, machineID: UUID? = nil,
                              page: Int = 1, pageSize: Int = 50) -> APIRequest<Page<AlertDTO>> {
        .get("\(tenant)/alerts", query: paging(page, pageSize) + compact([
            ("status", status?.rawValue), ("machine_id", machineID?.lowercased),
        ]))
    }

    public static func actOnAlert(_ id: UUID, action: AlertAction, note: String?,
                                  idempotencyKey: UUID) throws -> APIRequest<AlertDTO> {
        try .mutation(.post, "\(tenant)/alerts/\(id.lowercased)/action",
                      body: AlertActionIn(action: action, note: note.nonEmpty), idempotencyKey: idempotencyKey)
    }

    public static func approvals(status: ApprovalStatus? = nil, page: Int = 1,
                                 pageSize: Int = 50) -> APIRequest<Page<ApprovalRequestDTO>> {
        .get("\(tenant)/approvals", query: paging(page, pageSize) + compact([("status", status?.rawValue)]))
    }

    public static func decideApproval(_ id: UUID, approve: Bool, note: String?,
                                      idempotencyKey: UUID) throws -> APIRequest<ApprovalRequestDTO> {
        try .mutation(.post, "\(tenant)/approvals/\(id.lowercased)/decision",
                      body: ApprovalDecisionIn(approve: approve, note: note.nonEmpty), idempotencyKey: idempotencyKey)
    }

    public static func cases(status: CaseStatus? = nil, machineID: UUID? = nil, page: Int = 1,
                             pageSize: Int = 50) -> APIRequest<Page<AnomalyCaseDTO>> {
        .get("\(tenant)/cases", query: paging(page, pageSize) + compact([
            ("status", status?.rawValue), ("machine_id", machineID?.lowercased),
        ]))
    }

    public static func caseDetail(_ id: UUID) -> APIRequest<AnomalyCaseDetailDTO> {
        .get("\(tenant)/cases/\(id.lowercased)")
    }

    public static func meterCaptures(machineID: UUID? = nil, jobID: UUID? = nil,
                                     pageSize: Int = 10) -> APIRequest<Page<MeterCaptureDTO>> {
        .get("\(tenant)/meter-captures", query: paging(1, pageSize) + compact([
            ("machine_id", machineID?.lowercased), ("job_id", jobID?.lowercased),
        ]))
    }

    /// Presigned evidence photo URL, fetched on demand only (never cached).
    public static func attachmentURL(_ id: UUID) -> APIRequest<PhotoURLDTO> {
        .get("\(tenant)/attachments/\(id.lowercased)/url")
    }

    public static func notifications(unreadOnly: Bool = false, page: Int = 1,
                                     pageSize: Int = 50) -> APIRequest<Page<NotificationDTO>> {
        .get("\(tenant)/notifications", query: paging(page, pageSize) + compact([
            ("unread_only", unreadOnly ? "true" : nil),
        ]))
    }

    public static func notification(_ id: UUID) -> APIRequest<NotificationDTO> {
        .get("\(tenant)/notifications/\(id.lowercased)")
    }

    public static func unreadCount() -> APIRequest<UnreadCountDTO> { .get("\(tenant)/notifications/unread-count") }

    public static func markRead(_ ids: [UUID], idempotencyKey: UUID) throws -> APIRequest<MarkReadResultDTO> {
        try .mutation(.post, "\(tenant)/notifications/read", body: MarkReadIn(ids: ids), idempotencyKey: idempotencyKey)
    }

    public static func routing() -> APIRequest<[NotificationRoutingDTO]> { .get("\(tenant)/notification-routing") }

    public static func updateRouting(_ changes: [NotificationRoutingChangeIn],
                                     idempotencyKey: UUID) throws -> APIRequest<[NotificationRoutingDTO]> {
        try .mutation(.put, "\(tenant)/notification-routing", body: NotificationRoutingIn(changes: changes),
                      idempotencyKey: idempotencyKey)
    }

    /// Sent with `X-Tenant-ID`, so the device is bound to the open company.
    public static func pushDevices() -> APIRequest<Page<PushDeviceDTO>> {
        .get("/api/v1/me/push-devices", query: paging(1, 50))
    }

    public static func registerPushDevice(_ body: PushDeviceIn, idempotencyKey: UUID) throws -> APIRequest<PushDeviceDTO> {
        try .mutation(.post, "/api/v1/me/push-devices", body: body, idempotencyKey: idempotencyKey)
    }

    public static func deactivatePushDevice(_ id: UUID, idempotencyKey: UUID) throws -> APIRequest<PushDeviceDTO> {
        try .mutation(.delete, "/api/v1/me/push-devices/\(id.lowercased)", body: EmptyBody(),
                      idempotencyKey: idempotencyKey)
    }

    // MARK: - Helpers

    struct EmptyBody: Encodable {}

    static func paging(_ page: Int, _ size: Int) -> [URLQueryItem] {
        [URLQueryItem(name: "page", value: String(max(1, page))),
         URLQueryItem(name: "page_size", value: String(min(200, max(1, size))))]
    }

    static func compact(_ pairs: [(String, String?)]) -> [URLQueryItem] {
        pairs.compactMap { name, value in value.map { URLQueryItem(name: name, value: $0) } }
    }
}

extension Optional where Wrapped == String {
    /// The trimmed text, or `nil` when empty.
    var nonEmpty: String? {
        guard let text = self?.trimmingCharacters(in: .whitespacesAndNewlines), !text.isEmpty else { return nil }
        return text
    }
}
