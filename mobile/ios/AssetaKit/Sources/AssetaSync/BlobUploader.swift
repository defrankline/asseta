import AssetaCapture
import AssetaModel
import AssetaNetwork
import AssetaStore
import Foundation

public enum BlobUploadError: Error, Equatable, Sendable {
    /// The server did not confirm completion after several passes; retried on a later sync.
    case incomplete
    case vanished
}

public enum BlobUploadOutcome: Sendable, Equatable {
    case complete(attachmentID: UUID)
    /// Permanent local problem (evidence file missing or changed, file too large); needs attention.
    case failed(reason: String)
}

/// Resumable, SHA-256-verified evidence upload (`POST /sync/blobs` → `PUT …/chunks/{i}` →
/// `POST …/complete`). The session and received chunk indexes are persisted after every chunk, so
/// an interrupted upload resumes by sending only the missing indexes. Already-known content
/// completes immediately. `CHECKSUM_MISMATCH`, an expired or unknown session restart the upload.
/// Network errors and 5xx propagate (the engine backs off); `DEVICE_REVOKED` propagates.
public struct BlobUploader: Sendable {
    let api: SyncAPI
    let attachments: AttachmentRepository
    let evidence: EvidenceStore
    static let maxRestarts = 2

    public init(api: SyncAPI, attachments: AttachmentRepository, evidence: EvidenceStore) {
        self.api = api
        self.attachments = attachments
        self.evidence = evidence
    }

    public func upload(_ attachment: LocalAttachment, now: Date) async throws -> BlobUploadOutcome {
        let data: Data
        do {
            data = try evidence.readVerified(attachment.fileName, sha256: attachment.sha256)
        } catch let error as EvidenceError {
            let reason = "LOCAL_EVIDENCE_UNAVAILABLE: \(error)"
            try attachments.markFailed(id: attachment.id, error: reason)
            return .failed(reason: reason)
        } catch {
            // e.g. NSFileProtectionComplete while locked: transient, try again later.
            throw error
        }
        guard let purpose = BlobPurpose(rawValue: attachment.purpose) else {
            try attachments.markFailed(id: attachment.id, error: "UNKNOWN_PURPOSE")
            return .failed(reason: "UNKNOWN_PURPOSE")
        }
        var restarts = 0
        for _ in 0..<6 {
            guard let current = try attachments.attachment(id: attachment.id) else { throw BlobUploadError.vanished }
            do {
                if let done = try await uploadOnce(current, data: data, purpose: purpose, now: now) { return done }
            } catch let error as APIError where Self.requiresRestart(error) && restarts < Self.maxRestarts {
                restarts += 1
                try attachments.updateSession(id: current.id, sessionID: nil, expiresAt: nil, chunkSize: nil, received: [])
            } catch let error as APIError where error.serverCode == "FILE_TOO_LARGE" {
                try attachments.markFailed(id: current.id, error: "FILE_TOO_LARGE")
                return .failed(reason: "FILE_TOO_LARGE")
            }
        }
        throw BlobUploadError.incomplete
    }

    static func requiresRestart(_ error: APIError) -> Bool {
        guard case let .server(status, body) = error else { return false }
        return ["CHECKSUM_MISMATCH", "UPLOAD_EXPIRED", "BAD_CHUNK"].contains(body.code) || status == 404
    }

    /// One pass; returns a final outcome, or nil when the caller should loop (incomplete upload).
    private func uploadOnce(_ attachment: LocalAttachment, data: Data, purpose: BlobPurpose, now: Date) async throws -> BlobUploadOutcome? {
        var session: (id: UUID, chunkSize: Int, received: Set<Int>)
        if let id = attachment.sessionID, let chunkSize = attachment.chunkSize,
           (attachment.sessionExpiresAt ?? .distantFuture) > now {
            session = (id, chunkSize, attachment.receivedChunks)
        } else {
            let started = try await api.startBlob(BlobStartIn(sha256: attachment.sha256, sizeBytes: Int64(data.count),
                                                              purpose: purpose))
            if let done = try finishIfComplete(started, attachment) { return done }
            session = (started.id, started.chunkSize, Set(started.receivedChunks))
            try persist(attachment, started)
        }
        let total = max(1, (data.count + session.chunkSize - 1) / session.chunkSize)
        for index in 0..<total where !session.received.contains(index) {
            let start = index * session.chunkSize
            let chunk = data.subdata(in: start..<min(start + session.chunkSize, data.count))
            let state = try await api.putChunk(session: session.id, index: index, data: chunk)
            if let done = try finishIfComplete(state, attachment) { return done }
            session.received = Set(state.receivedChunks)
            try persist(attachment, state)
        }
        do {
            let completed = try await api.completeBlob(session: session.id)
            if let done = try finishIfComplete(completed, attachment) { return done }
            try persist(attachment, completed)
            return nil
        } catch let error as APIError where error.serverCode == "UPLOAD_INCOMPLETE" {
            // Our record of received chunks was stale: forget it and re-send (PUT is idempotent).
            try attachments.updateSession(id: attachment.id, sessionID: session.id, expiresAt: attachment.sessionExpiresAt,
                                          chunkSize: session.chunkSize, received: [])
            return nil
        }
    }

    private func finishIfComplete(_ state: BlobSessionDTO, _ attachment: LocalAttachment) throws -> BlobUploadOutcome? {
        guard state.isComplete, let attachmentID = state.attachmentID else { return nil }
        try attachments.markComplete(id: attachment.id, attachmentID: attachmentID, uploadID: state.id)
        return .complete(attachmentID: attachmentID)
    }

    private func persist(_ attachment: LocalAttachment, _ state: BlobSessionDTO) throws {
        try attachments.updateSession(id: attachment.id, sessionID: state.id, expiresAt: state.expiresAt,
                                      chunkSize: state.chunkSize, received: Set(state.receivedChunks))
    }
}
