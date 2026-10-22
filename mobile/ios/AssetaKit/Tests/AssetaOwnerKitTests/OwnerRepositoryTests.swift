@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import AssetaSecurity
import AssetaStore
import AssetaTestSupport
import Foundation
import Testing

/// Network-first reads with the bounded offline fallback, and cache wipes on lost access.
struct OwnerRepositoryTests {
    let tenant = UUID(uuidString: Samples.tenant)!
    static let clock = Date(timeIntervalSince1970: 1_790_000_000)

    func make(_ handler: @escaping MockTransport.Handler) throws -> (OwnerRepository, MockTransport, SnapshotCache) {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("repo-\(UUID().uuidString).sqlite")
        let key = try DatabaseKeyProvider(store: InMemorySecretStore()).loadOrCreateKey()
        let cache = try SnapshotCache(database: try EncryptedDatabase(url: url, key: key))
        let transport = MockTransport(handler: handler)
        let client = APIClient(baseURL: URL(string: "https://api.example.test")!, transport: transport,
                               tokens: StaticTokenProvider(token: "t"), tenantID: tenant)
        let start = Self.clock
        return (OwnerRepository(client: client, cache: cache, tenantID: tenant, now: { start }), transport, cache)
    }

    static func error(_ code: String, _ status: Int) -> (Int, Data) {
        (status, Data(#"{"error":{"code":"\#(code)","message":"m","correlation_id":"c0ffee00-1"}}"#.utf8))
    }

    @Test func successIsReturnedFromServerAndCached() async throws {
        let (repo, transport, cache) = try make { _ in (200, Data(Samples.overview.utf8)) }
        let snapshot = try await repo.load(.overview, OwnerAPI.overview())
        #expect(snapshot.source == .server && !snapshot.isFromCache)
        #expect(transport.requests.first?.value(forHTTPHeaderField: "X-Tenant-ID") == Samples.tenant)
        #expect(try cache.count(tenantID: tenant) == 1)
    }

    @Test func offlineFallsBackToCachedSnapshotMarkedStale() async throws {
        let (repo, transport, _) = try make { _ in (200, Data(Samples.overview.utf8)) }
        let first = try await repo.load(.overview, OwnerAPI.overview())
        transport.setHandler { _ in throw URLError(.notConnectedToInternet) }
        let offline = try await repo.load(.overview, OwnerAPI.overview())
        #expect(offline.isFromCache)
        #expect(abs(offline.fetchedAt.timeIntervalSince(first.fetchedAt)) < 0.001)
        #expect(offline.value.fleet?.machines == 12)
    }

    @Test func serverErrorFallsBackButClientErrorDoesNot() async throws {
        let (repo, transport, _) = try make { _ in (200, Data(Samples.overview.utf8)) }
        _ = try await repo.load(.overview, OwnerAPI.overview())
        transport.setHandler { _ in Self.error("DEPENDENCY_UNAVAILABLE", 503) }
        #expect(try await repo.load(.overview, OwnerAPI.overview()).isFromCache)
        transport.setHandler { _ in Self.error("VALIDATION_FAILED", 422) }
        await #expect(throws: APIError.self) { try await repo.load(.overview, OwnerAPI.overview()) }
    }

    @Test func offlineWithoutCacheThrows() async throws {
        let (repo, _, _) = try make { _ in throw URLError(.notConnectedToInternet) }
        await #expect(throws: APIError.self) { try await repo.load(.fleetMap, OwnerAPI.fleetMap()) }
    }

    @Test func lostTenantAccessWipesTheTenantCache() async throws {
        let (repo, transport, cache) = try make { _ in (200, Data(Samples.overview.utf8)) }
        _ = try await repo.load(.overview, OwnerAPI.overview())
        transport.setHandler { _ in Self.error("TENANT_ACCESS_DENIED", 403) }
        await #expect(throws: APIError.self) { try await repo.load(.fleetMap, OwnerAPI.fleetMap()) }
        #expect(try cache.count(tenantID: tenant) == 0)
    }

    @Test func goneRecordDropsOnlyItsEntry() async throws {
        let (repo, transport, cache) = try make { _ in (200, Data(Samples.overview.utf8)) }
        _ = try await repo.load(.overview, OwnerAPI.overview())
        transport.setHandler { _ in (200, Data(Samples.jobSummary.utf8)) }
        let jobID = UUID(uuidString: Samples.job)!
        _ = try await repo.load(.job(jobID), OwnerAPI.jobSummary(jobID))
        transport.setHandler { _ in Self.error("NOT_FOUND", 404) }
        await #expect(throws: APIError.self) { try await repo.load(.job(jobID), OwnerAPI.jobSummary(jobID)) }
        #expect(try cache.count(tenantID: tenant) == 1)
    }

    @Test func mutationsCarryIdempotencyKeyAndAreNeverCached() async throws {
        let (repo, transport, cache) = try make { _ in (200, Data(Samples.alertJSON(status: "ACKNOWLEDGED").utf8)) }
        let key = UUID()
        let alert = try await repo.send(try OwnerAPI.actOnAlert(UUID(), action: .acknowledge, note: "  ",
                                                                idempotencyKey: key))
        #expect(alert.status == .acknowledged)
        let request = try #require(transport.requests.first)
        #expect(request.httpMethod == "POST")
        #expect(request.value(forHTTPHeaderField: "Idempotency-Key") == key.uuidString.lowercased())
        #expect(String(decoding: request.httpBody ?? Data(), as: UTF8.self) == #"{"action":"ACKNOWLEDGE"}"#)
        #expect(try cache.count(tenantID: tenant) == 0)
    }

    @Test func dispositionTable() {
        let body = { (code: String) in ErrorBody(code: code, message: "", correlationID: "c") }
        #expect(OwnerRepository.disposition(of: .transport(code: -1009, message: "", correlationID: "c")) == .fallBackToCache)
        #expect(OwnerRepository.disposition(of: .server(status: 429, body: body("RATE_LIMITED"))) == .fallBackToCache)
        #expect(OwnerRepository.disposition(of: .server(status: 403, body: body("MANDATE_ENDED"))) == .wipeTenant)
        #expect(OwnerRepository.disposition(of: .server(status: 403, body: body("PERMISSION_DENIED"))) == .dropEntry)
        #expect(OwnerRepository.disposition(of: .notAuthenticated) == .none)
    }

    @Test func requestsUseContractPathsAndQueries() throws {
        let machine = UUID(uuidString: Samples.machine)!
        #expect(OwnerAPI.machine(machine).path == "/api/v1/tenant/fleet/machines/\(Samples.machine)")
        let from = Date(timeIntervalSince1970: 0), to = Date(timeIntervalSince1970: 86_400)
        let history = OwnerAPI.history(machine, from: from, to: to)
        #expect(history.queryItems.map(\.name) == ["from", "to"])
        #expect(history.queryItems.first?.value == "1970-01-01T00:00:00.000Z")
        let jobs = OwnerAPI.jobs(status: .inProgress, machineID: machine, pageSize: 500)
        #expect(jobs.queryItems.contains(URLQueryItem(name: "page_size", value: "200")))
        #expect(jobs.queryItems.contains(URLQueryItem(name: "status", value: "IN_PROGRESS")))
        let decide = try OwnerAPI.decideApproval(machine, approve: true, note: nil, idempotencyKey: UUID())
        #expect(decide.path.hasSuffix("/decision") && decide.method == .post)
        #expect(OwnerAPI.pushDevices().tenantScoped) // binds the device to the open company
    }
}
