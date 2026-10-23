import AssetaModel
import AssetaStore
import Foundation

/// Turns the supervisor inbox lists of a pull (`SyncData.my_*`) into `inbox_record` rows (the same
/// columns as Android `InboxWriter`): the server JSON plus the id, client id, job, machine, status,
/// time and sync revision lists filter and sort on.
public enum InboxWriter {
    /// The server's inbox window (bootstrap ships the last 30 days plus everything still open).
    public static let window: TimeInterval = 30 * 86400

    public static func records(_ data: SyncData) throws -> [InboxRecord] {
        var out: [InboxRecord] = []
        for (list, rows) in data.inbox {
            for row in rows {
                guard let record = try record(list, row) else { continue }
                out.append(record)
            }
        }
        return out
    }

    static func record(_ list: SyncData.InboxList, _ row: JSONValue) throws -> InboxRecord? {
        func uuid(_ key: String) -> UUID? { row[key]?.stringValue.flatMap(UUID.init(uuidString:)) }
        func text(_ key: String) -> String? { row[key]?.stringValue }
        guard let id = uuid("id"), let revision = row["sync_revision"]?.intValue else { return nil }
        let kind: InboxRecord.Kind
        var clientID = uuid("client_id")
        var status = text("status")
        let at: String?
        switch list {
        case .meterCaptures:
            kind = .meterCapture
            clientID = id
            status = text("review_status") == "PENDING_REVIEW" ? "PENDING_REVIEW" : text("state")
            at = text("captured_at")
        case .meterResets: kind = .meterReset; at = text("created_at")
        case .jobActivities: kind = .jobActivity; status = nil; at = text("started_at")
        case .acknowledgements: kind = .acknowledgement; status = nil; at = text("captured_at")
        case .expenses: kind = .expense; at = text("incurred_at")
        case .fuelEvents: kind = .fuelEvent; status = nil; at = text("occurred_at")
        case .cashCollections: kind = .cashCollection; at = text("received_at")
        case .cashHandovers: kind = .cashHandover; at = text("handed_at")
        }
        return InboxRecord(kind: kind, id: id, clientID: clientID, jobID: uuid("job_id"), machineID: uuid("machine_id"),
                           status: status, occurredAt: at.flatMap(AssetaJSON.parseInstant) ?? Date(timeIntervalSince1970: 0),
                           syncRevision: Int64(revision), json: try row.jsonString())
    }
}
