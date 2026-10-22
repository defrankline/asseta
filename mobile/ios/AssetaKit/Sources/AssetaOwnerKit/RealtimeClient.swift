import AssetaModel
import AssetaNetwork
import Foundation

/// Foreground realtime feed over `/api/v1/ws` (sub-protocol `asseta.v1`, token offered as
/// `bearer.<jwt>`, never in the URL). Emits decoded server frames; answers pings, refreshes the
/// token on `reauth_required`, and reconnects with backoff until stopped. Delivery is best effort:
/// on every `auth_ok` the app re-reads the inbox, which stays the durable record.
public actor RealtimeClient {
    public static let subprotocol = "asseta.v1"

    private let baseURL: URL
    private let tenantID: UUID
    private let tokens: any AccessTokenProvider
    private let session: URLSession
    private var task: URLSessionWebSocketTask?
    private var loop: Task<Void, Never>?
    private var continuation: AsyncStream<RealtimeEvent>.Continuation?
    private var currentToken = ""

    public init(baseURL: URL, tenantID: UUID, tokens: any AccessTokenProvider,
                session: URLSession = URLSession(configuration: .ephemeral)) {
        self.baseURL = baseURL
        self.tenantID = tenantID
        self.tokens = tokens
        self.session = session
    }

    /// Starts (or restarts) the connection loop and returns its event stream.
    public func start() -> AsyncStream<RealtimeEvent> {
        stop()
        let (stream, continuation) = AsyncStream<RealtimeEvent>.makeStream(bufferingPolicy: .bufferingNewest(100))
        self.continuation = continuation
        loop = Task { [weak self] in await self?.run() }
        return stream
    }

    public func stop() {
        loop?.cancel()
        loop = nil
        task?.cancel(with: .goingAway, reason: nil)
        task = nil
        continuation?.finish()
        continuation = nil
    }

    private func run() async {
        var attempt = 0
        while !Task.isCancelled {
            let outcome = await connectOnce()
            if Task.isCancelled { break }
            switch outcome {
            case .accessDenied:
                stop()
                return
            case .connectedThenClosed:
                attempt = 0
            case .failed:
                attempt += 1
            }
            try? await Task.sleep(for: .seconds(Self.backoff(attempt: attempt)))
        }
    }

    enum Outcome { case connectedThenClosed, failed, accessDenied }

    private func connectOnce() async -> Outcome {
        guard let token = try? await tokens.validAccessToken() else { return .failed }
        currentToken = token
        let socket = session.webSocketTask(with: Self.socketURL(baseURL: baseURL),
                                           protocols: Self.protocols(token: token))
        task = socket
        socket.resume()
        var connected = false
        do {
            try await send(["type": "subscribe", "scope": ["kind": "tenant", "tenantId": tenantID.uuidString.lowercased()]])
            while !Task.isCancelled {
                let message = try await socket.receive()
                let data: Data
                switch message {
                case let .string(text): data = Data(text.utf8)
                case let .data(bytes): data = bytes
                @unknown default: continue
                }
                guard let event = try? RealtimeEvent.decode(data) else { continue }
                switch event {
                case .authOK: connected = true
                case .ping: try await send(["type": "pong"])
                case .reauthRequired: try await reauthenticate()
                case let .authError(code, _):
                    continuation?.yield(event)
                    return Self.isAccessDenied(code: code) ? .accessDenied : .failed
                default: break
                }
                continuation?.yield(event)
            }
        } catch {
            if socket.closeCode.rawValue == 4403 { return .accessDenied }
        }
        socket.cancel(with: .goingAway, reason: nil)
        return connected ? .connectedThenClosed : .failed
    }

    private func reauthenticate() async throws {
        let fresh = try await tokens.refreshedAccessToken(rejected: currentToken)
        currentToken = fresh
        try await send(["type": "auth", "token": fresh])
    }

    private func send(_ object: [String: Any]) async throws {
        let data = try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
        try await task?.send(.string(String(decoding: data, as: UTF8.self)))
    }

    // MARK: - Pure helpers

    /// `http(s)://host[/base]` → `ws(s)://host[/base]/api/v1/ws`.
    public static func socketURL(baseURL: URL) -> URL {
        var components = URLComponents(url: baseURL.appendingPathComponent("api/v1/ws"), resolvingAgainstBaseURL: false)!
        components.scheme = components.scheme == "http" ? "ws" : "wss"
        return components.url!
    }

    public static func protocols(token: String) -> [String] { [subprotocol, "bearer.\(token)"] }

    /// 1, 2, 4 … capped at 60 s; attempt 0 (clean close after a working session) waits 1 s.
    public static func backoff(attempt: Int) -> Double {
        min(60, pow(2, Double(max(0, attempt - 1))))
    }

    /// 4403-class codes: access is gone, so reconnecting would only fail again.
    public static func isAccessDenied(code: String) -> Bool {
        ["TENANT_ACCESS_DENIED", "MANDATE_REQUIRED", "MANDATE_ENDED", "TENANT_ACCESS_BLOCKED", "PLATFORM_REQUIRED",
         "PERMISSION_DENIED"].contains(code)
    }
}
