import AssetaModel
import CryptoKit
import Foundation

/// In-memory stand-in for `/api/v1/sync` that mirrors the backend semantics in
/// `backend/src/asseta/modules/sync/{push,blobs,service}.py`: idempotent ops (DUPLICATE replays the
/// stored outcome), DEFERRED for unmet dependencies (not stored), QUARANTINED for read-only tenants
/// (re-applied when re-sent after reactivation), resumable chunked blobs with SHA-256 verification.
final class FakeSyncServer: @unchecked Sendable {
    struct StoredOp { var status: String; var result: [String: Any]; var error: [String: Any]? }
    struct Blob { var sha256: String; var size: Int; var chunks: [Int: Data] = [:]; var attachmentID: UUID?; var purpose: String? = nil }

    private let lock = NSLock()
    // Failure injection and behaviour switches.
    var offline = false
    var unavailable503 = 0
    var revoked = false
    var readOnly = false
    var dropNextPushResponse = false
    var corruptNextComplete = false
    var failChunkPut: (index: Int, times: Int)?
    var chunkSize = 1000
    /// Scripted outcomes per op id, consumed in order ("DEFERRED", "CONFLICT", "REJECTED").
    var script: [UUID: [String]] = [:]
    var knownContent: [String: UUID] = [:]
    var serverTime = Date(timeIntervalSince1970: 1_792_000_000)
    var cursor: Int64 = 100
    var jobs: [[String: Any]] = []
    /// Whether an accepted JOB_REQUEST's job is delivered by the next pull (false: the pull misses it).
    var deliverRequestedJobs = true
    var requestedJobNumber = 104
    var machines: [[String: Any]] = []
    var snapshots: [[String: Any]] = []
    var customers: [[String: Any]] = []
    var expenseCategories: [[String: Any]] = []
    var cashCustody: [[String: Any]] = []
    /// Advertised protocol capabilities (nil: an older server that sends none).
    var capabilities: [String]? = ["SUPERVISOR_INBOX_V1", "OP_METER_RESET_REQUEST", "OP_JOB_REQUEST"]
    /// Supervisor inbox lists sent with every bootstrap/changes (`my_expenses` → rows); empty: not sent.
    var inbox: [String: [[String: Any]]] = [:]
    /// Meter reset requests received (payload by server id), resolved like the server's MeterResetOp.
    private(set) var resets: [UUID: [String: Any]] = [:]

    // Observations.
    private(set) var requests: [URLRequest] = []
    private(set) var stored: [UUID: StoredOp] = [:]
    private(set) var applyOrder: [UUID] = []
    private(set) var pushedBatchSizes: [Int] = []
    private(set) var chunkPuts: [(session: UUID, index: Int)] = []
    private(set) var sessionsStarted = 0
    var blobs: [UUID: Blob] = [:]
    private(set) var registrations: [[String: Any]] = []
    /// Payloads of applied (ACKED) operations, by op id.
    private(set) var appliedPayloads: [UUID: [String: Any]] = [:]

    func mutate(_ body: (FakeSyncServer) -> Void) { lock.withLock { body(self) } }
    func read<T>(_ body: (FakeSyncServer) -> T) -> T { lock.withLock { body(self) } }

    func handle(_ request: URLRequest) throws -> (Int, Data) {
        try lock.withLock { try route(request) }
    }

    private func route(_ request: URLRequest) throws -> (Int, Data) {
        requests.append(request)
        if offline { throw URLError(.notConnectedToInternet) }
        if unavailable503 > 0 {
            unavailable503 -= 1
            return error(503, "DEPENDENCY_UNAVAILABLE", "Try later")
        }
        let path = request.url!.path
        if revoked && path.hasPrefix("/api/v1/sync") {
            return error(403, "DEVICE_REVOKED", "This device was revoked; local data must be wiped", issue: "WIPE_LOCAL_DATA")
        }
        let body = request.httpBody.flatMap { try? JSONSerialization.jsonObject(with: $0) } as? [String: Any] ?? [:]
        switch (request.httpMethod ?? "GET", path) {
        case ("POST", "/api/v1/sync/devices"):
            registrations.append(body)
            return json(201, deviceSession(body["device_id"] as? String ?? ""))
        case ("GET", "/api/v1/sync/bootstrap"):
            var body: [String: Any] = ["server_time": iso(serverTime), "cursor": cursor, "protocol_version": 1,
                                       "device_session": deviceSession("d"), "data": data(), "policy_snapshots": snapshots]
            if let capabilities { body["capabilities"] = capabilities }
            return json(200, body)
        case ("GET", "/api/v1/sync/changes"):
            var body: [String: Any] = ["server_time": iso(serverTime), "cursor": cursor, "has_more": false, "data": data(),
                                       "policy_snapshots": snapshots]
            if let capabilities { body["capabilities"] = capabilities }
            return json(200, body)
        case ("POST", "/api/v1/sync/push"):
            return try push(body)
        case ("POST", "/api/v1/sync/blobs"):
            return startBlob(body)
        default:
            return try blobRoute(request, path: path)
        }
    }

    // MARK: - Push

    private func push(_ body: [String: Any]) throws -> (Int, Data) {
        let ops = body["operations"] as? [[String: Any]] ?? []
        pushedBatchSizes.append(ops.count)
        var results: [[String: Any]] = []
        for op in ops {
            let id = UUID(uuidString: op["id"] as! String)!
            results.append(apply(id: id, op: op))
        }
        if dropNextPushResponse {
            dropNextPushResponse = false
            throw URLError(.networkConnectionLost) // applied server-side, response lost
        }
        return json(200, ["server_time": iso(serverTime), "clock_offset_s": 0.0, "clock_skew_alert": false,
                          "results": results, "protocol_version": 1])
    }

    private func apply(id: UUID, op: [String: Any]) -> [String: Any] {
        if let existing = stored[id], existing.status != "QUARANTINED" || readOnly {
            var out: [String: Any] = ["id": id.uuidString.lowercased(), "status": "DUPLICATE", "result": existing.result]
            out["error"] = existing.error ?? NSNull()
            return out
        }
        let deps = (op["depends_on"] as? [String] ?? []).compactMap(UUID.init(uuidString:))
        let unmet = deps.filter { stored[$0]?.status != "ACKED" }
        if !unmet.isEmpty {
            return ["id": id.uuidString.lowercased(), "status": "DEFERRED",
                    "error": ["code": "DEPENDENCY_PENDING", "depends_on": unmet.map { $0.uuidString.lowercased() }]]
        }
        if readOnly {
            let error: [String: Any] = ["code": "SUBSCRIPTION_READ_ONLY", "message": "Tenant is read-only"]
            stored[id] = StoredOp(status: "QUARANTINED", result: ["error": error], error: error)
            return ["id": id.uuidString.lowercased(), "status": "QUARANTINED", "result": ["error": error], "error": error]
        }
        if var queue = script[id], !queue.isEmpty {
            let scripted = queue.removeFirst()
            script[id] = queue
            switch scripted {
            case "DEFERRED":
                return ["id": id.uuidString.lowercased(), "status": "DEFERRED", "error": ["code": "DEPENDENCY_PENDING"]]
            case "ATTACHMENT_PENDING":
                return ["id": id.uuidString.lowercased(), "status": "DEFERRED", "error": ["code": "ATTACHMENT_PENDING"]]
            case "CONFLICT":
                let error: [String: Any] = ["code": "INVALID_JOB_TRANSITION", "message": "Job is CANCELLED"]
                let result: [String: Any] = ["error": error, "server_state": ["job_status": "CANCELLED", "job_version": 7]]
                stored[id] = StoredOp(status: "CONFLICT", result: result, error: error)
                return ["id": id.uuidString.lowercased(), "status": "CONFLICT", "result": result, "error": error]
            default:
                let error: [String: Any] = ["code": "VALIDATION_FAILED", "message": "reading: invalid"]
                stored[id] = StoredOp(status: "REJECTED", result: ["error": error], error: error)
                return ["id": id.uuidString.lowercased(), "status": "REJECTED", "result": ["error": error], "error": error]
            }
        }
        let payload = op["payload"] as? [String: Any] ?? [:]
        for field in ["photo_attachment_id", "signature_attachment_id"] {
            if let text = payload[field] as? String,
               !blobs.values.contains(where: { $0.attachmentID?.uuidString.lowercased() == text }),
               !knownContent.values.contains(where: { $0.uuidString.lowercased() == text }) {
                let error: [String: Any] = ["code": "NOT_FOUND", "message": "Photo attachment not found"]
                stored[id] = StoredOp(status: "REJECTED", result: ["error": error], error: error)
                return ["id": id.uuidString.lowercased(), "status": "REJECTED", "result": ["error": error], "error": error]
            }
        }
        if op["op_type"] as? String == "EXPENSE" {
            // Mirrors push.py: an incomplete upload defers (not stored); an unknown one is rejected.
            let uploads = (payload["receipt_upload_ids"] as? [String] ?? []).compactMap(UUID.init(uuidString:))
            if uploads.contains(where: { blobs[$0] != nil && blobs[$0]?.attachmentID == nil }) {
                return ["id": id.uuidString.lowercased(), "status": "DEFERRED", "error": ["code": "ATTACHMENT_PENDING"]]
            }
            if uploads.contains(where: { blobs[$0] == nil }) || payload["client_id"] == nil {
                let error: [String: Any] = ["code": "RECEIPT_NOT_FOUND", "message": "Receipt upload not found"]
                stored[id] = StoredOp(status: "REJECTED", result: ["error": error], error: error)
                return ["id": id.uuidString.lowercased(), "status": "REJECTED", "result": ["error": error], "error": error]
            }
        }
        if op["op_type"] as? String == "METER_RESET_REQUEST" {
            // Mirrors push.py `_meter_reset`: the evidence upload must be complete; the reset gets a server id.
            guard let upload = (payload["evidence_upload_id"] as? String).flatMap(UUID.init(uuidString:)),
                  let attachment = blobs[upload]?.attachmentID else {
                let error: [String: Any] = ["code": "ATTACHMENT_NOT_FOUND", "message": "Evidence upload not found"]
                stored[id] = StoredOp(status: "REJECTED", result: ["error": error], error: error)
                return ["id": id.uuidString.lowercased(), "status": "REJECTED", "result": ["error": error], "error": error]
            }
            let reset = UUID()
            resets[reset] = payload
            let result: [String: Any] = ["entity": ["id": reset.uuidString.lowercased(), "status": "PENDING",
                                                    "evidence_attachment_id": attachment.uuidString.lowercased()]]
            stored[id] = StoredOp(status: "ACKED", result: result, error: nil)
            appliedPayloads[id] = payload
            applyOrder.append(id)
            return ["id": id.uuidString.lowercased(), "status": "ACKED", "result": result, "error": NSNull()]
        }
        if op["op_type"] as? String == "HOURS_PURCHASE" {
            // Mirrors push.py `_hours_purchase`: incomplete evidence uploads defer; an unknown one is rejected.
            let uploads = (payload["evidence_upload_ids"] as? [String] ?? []).compactMap(UUID.init(uuidString:))
            if uploads.contains(where: { blobs[$0] != nil && blobs[$0]?.attachmentID == nil }) {
                return ["id": id.uuidString.lowercased(), "status": "DEFERRED", "error": ["code": "ATTACHMENT_PENDING"]]
            }
            if uploads.contains(where: { blobs[$0] == nil }) {
                let error: [String: Any] = ["code": "ATTACHMENT_NOT_FOUND", "message": "Evidence upload not found"]
                stored[id] = StoredOp(status: "REJECTED", result: ["error": error], error: error)
                return ["id": id.uuidString.lowercased(), "status": "REJECTED", "result": ["error": error], "error": error]
            }
        }
        if op["op_type"] as? String == "METER_CORRECTION",
           let text = (payload["replacement"] as? [String: Any])?["photo_attachment_id"] as? String,
           !blobs.values.contains(where: { $0.attachmentID?.uuidString.lowercased() == text }) {
            let error: [String: Any] = ["code": "NOT_FOUND", "message": "Photo attachment not found"]
            stored[id] = StoredOp(status: "REJECTED", result: ["error": error], error: error)
            return ["id": id.uuidString.lowercased(), "status": "REJECTED", "result": ["error": error], "error": error]
        }
        if op["op_type"] as? String == "JOB_REQUEST" {
            // Mirrors JobService.request_job: client_id becomes the job id, numbered by the server, PENDING_APPROVAL.
            let jobID = payload["client_id"] as? String ?? id.uuidString.lowercased()
            requestedJobNumber += 1
            let job: [String: Any] = ["id": jobID, "contract_id": payload["contract_id"] ?? NSNull(),
                                      "job_number": "J-2026-\(requestedJobNumber)", "machine_id": payload["machine_id"] ?? NSNull(),
                                      "job_site_id": payload["job_site_id"] ?? NSNull(), "supervisor_id": NSNull(),
                                      "status": "PENDING_APPROVAL", "planned_start": payload["planned_start"] ?? NSNull(),
                                      "planned_end": payload["planned_end"] ?? NSNull(), "currency": "TZS", "hourly_rate": "0",
                                      "minimum_hours": "0", "rate_source": "PENDING_PRICE", "approved_at": NSNull(),
                                      "started_at": NSNull(), "completed_at": NSNull(), "version": 1,
                                      "requested_by_staff_id": "dddddddd-0000-4000-8000-00000000000d",
                                      "requested_by_name": "Juma Field", "request_note": payload["note"] ?? NSNull()]
            if deliverRequestedJobs { jobs.append(job) }
            let result: [String: Any] = ["entity": job]
            stored[id] = StoredOp(status: "ACKED", result: result, error: nil)
            appliedPayloads[id] = payload
            applyOrder.append(id)
            return ["id": id.uuidString.lowercased(), "status": "ACKED", "result": result, "error": NSNull()]
        }
        let result: [String: Any] = ["entity": ["id": id.uuidString.lowercased(), "version": 3]]
        stored[id] = StoredOp(status: "ACKED", result: result, error: nil)
        appliedPayloads[id] = payload
        applyOrder.append(id)
        return ["id": id.uuidString.lowercased(), "status": "ACKED", "result": result, "error": NSNull()]
    }

    // MARK: - Blobs

    private func startBlob(_ body: [String: Any]) -> (Int, Data) {
        sessionsStarted += 1
        let sha = body["sha256"] as? String ?? ""
        let id = UUID()
        blobs[id] = Blob(sha256: sha, size: body["size_bytes"] as? Int ?? 0, attachmentID: knownContent[sha],
                         purpose: body["purpose"] as? String)
        return json(201, blobDTO(id))
    }

    private func blobRoute(_ request: URLRequest, path: String) throws -> (Int, Data) {
        let parts = path.split(separator: "/").map(String.init) // api v1 sync blobs {id} chunks {i} | complete
        guard parts.count >= 6, parts[3] == "blobs", let id = UUID(uuidString: parts[4]), var blob = blobs[id] else {
            return error(404, "NOT_FOUND", "Upload session not found")
        }
        if parts[5] == "chunks", parts.count == 7, let index = Int(parts[6]) {
            if let failure = failChunkPut, failure.index == index, failure.times > 0 {
                failChunkPut = (index, failure.times - 1)
                throw URLError(.networkConnectionLost)
            }
            chunkPuts.append((id, index))
            if blob.attachmentID == nil { blob.chunks[index] = request.httpBody ?? Data() }
            blobs[id] = blob
            return json(200, blobDTO(id))
        }
        guard parts[5] == "complete" else { return error(404, "NOT_FOUND", "?") }
        if blob.attachmentID != nil { return json(200, blobDTO(id)) }
        let total = (blob.size + chunkSize - 1) / chunkSize
        guard blob.chunks.keys.sorted() == Array(0..<total) else { return error(409, "UPLOAD_INCOMPLETE", "Upload incomplete") }
        var data = (0..<total).reduce(into: Data()) { $0.append(blob.chunks[$1]!) }
        if corruptNextComplete { corruptNextComplete = false; data.append(0) }
        let digest = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
        guard digest == blob.sha256 else {
            blob.chunks = [:]
            blobs[id] = blob
            return error(422, "CHECKSUM_MISMATCH", "Checksum mismatch; upload restarted")
        }
        blob.attachmentID = UUID()
        blobs[id] = blob
        return json(200, blobDTO(id))
    }

    private func blobDTO(_ id: UUID) -> [String: Any] {
        let blob = blobs[id]!
        return ["id": id.uuidString.lowercased(), "chunk_size": chunkSize, "total_chunks": (blob.size + chunkSize - 1) / chunkSize,
                "received_chunks": blob.chunks.keys.sorted(), "status": blob.attachmentID == nil ? "OPEN" : "COMPLETE",
                "attachment_id": blob.attachmentID.map { $0.uuidString.lowercased() as Any } ?? NSNull(),
                "expires_at": iso(serverTime.addingTimeInterval(7 * 86400))]
    }

    // MARK: - Helpers

    private func data() -> [String: Any] {
        var data: [String: Any] = ["jobs": jobs, "machines": machines, "sites": [], "customers": customers, "contracts": [],
                                   "staff": [], "expense_categories": expenseCategories, "cash_custody": cashCustody]
        for (key, rows) in inbox { data[key] = rows }
        return data
    }

    private func deviceSession(_ deviceID: String) -> [String: Any] {
        ["id": UUID().uuidString.lowercased(), "device_id": deviceID, "platform": "IOS", "app_version": "1",
         "status": "ACTIVE", "registered_at": iso(serverTime), "last_sync_at": NSNull(),
         "offline_grant_until": iso(serverTime.addingTimeInterval(72 * 3600)), "last_clock_offset_s": NSNull(),
         "revoked_at": NSNull(), "revoke_reason": NSNull()]
    }

    private func error(_ status: Int, _ code: String, _ message: String, issue: String? = nil) -> (Int, Data) {
        let details: [[String: Any]] = issue.map { [["field": NSNull(), "issue": $0]] } ?? []
        return json(status, ["error": ["code": code, "message": message, "correlation_id": "c0ffee00", "details": details]])
    }

    private func json(_ status: Int, _ object: [String: Any]) -> (Int, Data) {
        (status, try! JSONSerialization.data(withJSONObject: object))
    }

    func iso(_ date: Date) -> String { AssetaJSON.formatInstant(date) }
}
