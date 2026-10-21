import AssetaModel
import AssetaNetwork
import AssetaSecurity
import AssetaStore
import Foundation

/// Stable random device identity, generated once and kept in the Keychain (this-device-only, not
/// backed up). It is *not* deleted by a revocation wipe: a revoked device must stay revoked, and a
/// fresh id would let a wiped phone register as a new device.
public enum DeviceIdentity {
    public static let account = "asseta.device.id.v1"

    public static func loadOrCreate(store: any SecretStore) throws -> String {
        if let data = try store.data(for: account), let text = String(data: data, encoding: .utf8),
           UUID(uuidString: text) != nil {
            return text
        }
        let id = UUID().uuidString.lowercased()
        try store.set(Data(id.utf8), for: account)
        return id
    }
}

/// Errors the sync layer surfaces to the app.
public enum SyncError: Error, Equatable, Sendable {
    /// `DEVICE_REVOKED` (details `WIPE_LOCAL_DATA`): local data must be wiped now.
    case deviceRevoked(message: String)
    case notAuthenticated
}

extension APIError {
    /// Any sync call may answer `DEVICE_REVOKED`; that always means wipe.
    public var isDeviceRevoked: Bool {
        if case let .server(_, body) = self {
            return body.code == "DEVICE_REVOKED" || body.details.contains { $0.issue == "WIPE_LOCAL_DATA" }
        }
        return false
    }

    var serverCode: String? {
        if case let .server(_, body) = self { return body.code }
        return nil
    }
}

/// Typed client for `/api/v1/sync`. Every call carries `X-Device-Id`.
public struct SyncAPI: Sendable {
    public let client: APIClient
    public let deviceID: String

    public init(client: APIClient, deviceID: String) {
        self.client = client
        self.deviceID = deviceID
    }

    private var deviceHeader: [String: String] { ["X-Device-Id": deviceID] }

    public func register(appVersion: String) async throws -> DeviceSessionDTO {
        let body = DeviceRegisterIn(deviceID: deviceID, appVersion: String(appVersion.prefix(32)))
        return try await send(try APIRequest<DeviceSessionDTO>.mutation(.post, "/api/v1/sync/devices", body: body,
                                                                       idempotencyKey: UUID()))
    }

    public func bootstrap() async throws -> BootstrapDTO {
        try await send(APIRequest<BootstrapDTO>.get("/api/v1/sync/bootstrap"))
    }

    public func changes(cursor: Int64) async throws -> ChangesDTO {
        try await send(APIRequest<ChangesDTO>.get("/api/v1/sync/changes",
                                                  query: [URLQueryItem(name: "cursor", value: String(cursor))]))
    }

    public func push(_ body: PushIn) async throws -> PushResultDTO {
        try await send(try APIRequest<PushResultDTO>.mutation(.post, "/api/v1/sync/push", body: body,
                                                             idempotencyKey: UUID()))
    }

    public func startBlob(_ body: BlobStartIn) async throws -> BlobSessionDTO {
        try await send(try APIRequest<BlobSessionDTO>.mutation(.post, "/api/v1/sync/blobs", body: body,
                                                              idempotencyKey: UUID()))
    }

    public func putChunk(session: UUID, index: Int, data: Data) async throws -> BlobSessionDTO {
        try await send(APIRequest<BlobSessionDTO>.rawMutation(
            .put, "/api/v1/sync/blobs/\(session.lowercased)/chunks/\(index)", data: data, idempotencyKey: UUID()))
    }

    public func completeBlob(session: UUID) async throws -> BlobSessionDTO {
        try await send(try APIRequest<BlobSessionDTO>.mutation(
            .post, "/api/v1/sync/blobs/\(session.lowercased)/complete", body: EmptyBody(), idempotencyKey: UUID()))
    }

    private func send<R>(_ request: APIRequest<R>) async throws -> R {
        do {
            return try await client.send(request.adding(headers: deviceHeader))
        } catch let error as APIError where error.isDeviceRevoked {
            throw SyncError.deviceRevoked(message: error.localizedDescription)
        } catch APIError.notAuthenticated {
            throw SyncError.notAuthenticated
        }
    }
}

struct EmptyBody: Encodable {}
