import AssetaModel
@testable import AssetaNetwork
import AssetaTestSupport
import Foundation
import Testing

struct APIClientTests {
    let base = URL(string: "https://api.example.test")!
    let tenant = UUID(uuidString: "11111111-1111-4111-8111-111111111111")!

    struct Body: Codable, Sendable { let name: String }
    struct Created: Decodable, Sendable, Equatable { let id: String }

    @Test func meSendsAuthAndCorrelationButNoTenant() async throws {
        let transport = MockTransport { _ in (200, Fixtures.json(Fixtures.meJSON)) }
        let client = APIClient(baseURL: base, transport: transport, tokens: StaticTokenProvider(token: "t1"))
        let me = try await client.me()
        #expect(me.tenants.count == 2)
        let request = try #require(transport.requests.first)
        #expect(request.url?.absoluteString == "https://api.example.test/api/v1/me")
        #expect(request.httpMethod == "GET")
        #expect(request.value(forHTTPHeaderField: "Authorization") == "Bearer t1")
        #expect(request.value(forHTTPHeaderField: "X-Tenant-ID") == nil)
        #expect(request.value(forHTTPHeaderField: "Idempotency-Key") == nil)
        let cid = try #require(request.value(forHTTPHeaderField: "X-Correlation-ID"))
        #expect(UUID(uuidString: cid) != nil)
    }

    @Test func rawDataReturnsTheBodyBytes() async throws {
        let pdf = Data("%PDF-1.7".utf8)
        let transport = MockTransport { _ in (200, pdf) }
        let client = APIClient(baseURL: base, transport: transport, tokens: StaticTokenProvider(token: "t"), tenantID: tenant)
        let raw = try await client.send(APIRequest<RawData>.get("/api/v1/tenant/customers/x/hours-statement.pdf"))
        #expect(raw.data == pdf)
    }

    @Test func correlationIDIsUniquePerRequest() async throws {
        let transport = MockTransport { _ in (200, Fixtures.json(Fixtures.meJSON)) }
        let client = APIClient(baseURL: base, transport: transport, tokens: StaticTokenProvider(token: "t"))
        _ = try await client.me()
        _ = try await client.me()
        let ids = transport.requests.compactMap { $0.value(forHTTPHeaderField: "X-Correlation-ID") }
        #expect(Set(ids).count == 2)
    }

    @Test func mutationSendsTenantIdempotencyAndBody() async throws {
        let transport = MockTransport { _ in (201, Fixtures.json(#"{"id":"x"}"#)) }
        let client = APIClient(baseURL: base, transport: transport, tokens: StaticTokenProvider(token: "t"))
            .withTenant(tenant)
        let key = UUID()
        let result = try await client.send(
            try APIRequest<Created>.mutation(.post, "/api/v1/things", body: Body(name: "n"), idempotencyKey: key)
        )
        #expect(result == Created(id: "x"))
        let request = try #require(transport.requests.first)
        #expect(request.value(forHTTPHeaderField: "X-Tenant-ID") == tenant.uuidString.lowercased())
        #expect(request.value(forHTTPHeaderField: "Idempotency-Key") == key.uuidString.lowercased())
        #expect(request.value(forHTTPHeaderField: "Content-Type") == "application/json")
        #expect(request.httpBody == Data(#"{"name":"n"}"#.utf8))
    }

    @Test func tenantScopedRequestWithoutTenantFailsLocally() async {
        let transport = MockTransport { _ in (200, Data()) }
        let client = APIClient(baseURL: base, transport: transport, tokens: StaticTokenProvider(token: "t"))
        await #expect(throws: APIError.tenantRequired) {
            try await client.send(APIRequest<EmptyResponse>.get("/api/v1/machines"))
        }
        #expect(transport.requests.isEmpty)
    }

    @Test func decodesErrorEnvelopeIntoTypedError() async {
        let body = #"{"error":{"code":"PERMISSION_DENIED","message":"No","correlation_id":"abc","details":[{"field":"x","issue":"bad"}]}}"#
        let transport = MockTransport { _ in (403, Fixtures.json(body)) }
        let client = APIClient(baseURL: base, transport: transport, tokens: StaticTokenProvider(token: "t"))
        await #expect(throws: APIError.server(status: 403, body: ErrorBody(
            code: "PERMISSION_DENIED", message: "No", correlationID: "abc",
            details: [ErrorDetail(field: "x", issue: "bad")]))) {
            try await client.me()
        }
    }

    @Test func nonEnvelopeErrorKeepsLocalCorrelationID() async throws {
        let fixed = UUID()
        let transport = MockTransport { _ in (502, Fixtures.json("<html>bad gateway</html>")) }
        let client = APIClient(baseURL: base, transport: transport, tokens: StaticTokenProvider(token: "t"),
                               makeCorrelationID: { fixed })
        do {
            _ = try await client.me()
            Issue.record("expected failure")
        } catch let error as APIError {
            #expect(error == .unexpectedStatus(status: 502, correlationID: fixed.uuidString.lowercased()))
            #expect(error.isRetryable)
        }
    }

    @Test func retriesOnceWithRefreshedTokenOn401() async throws {
        let transport = MockTransport { request in
            request.value(forHTTPHeaderField: "Authorization") == "Bearer new"
                ? (200, Fixtures.json(Fixtures.meJSON))
                : (401, Fixtures.json(#"{"error":{"code":"NOT_AUTHENTICATED","message":"x","correlation_id":"c"}}"#))
        }
        let tokens = StaticTokenProvider(token: "old", refreshed: "new")
        let client = APIClient(baseURL: base, transport: transport, tokens: tokens)
        _ = try await client.me()
        #expect(transport.requests.count == 2)
        #expect(await tokens.refreshCount == 1)
    }

    @Test func transportErrorsAreTyped() async {
        let transport = MockTransport { _ in throw URLError(.notConnectedToInternet) }
        let client = APIClient(baseURL: base, transport: transport, tokens: StaticTokenProvider(token: "t"))
        do {
            _ = try await client.me()
            Issue.record("expected failure")
        } catch let error as APIError {
            #expect(error.code == "TRANSPORT_FAILED")
            #expect(error.isRetryable)
            #expect(error.correlationID != nil)
        } catch {
            Issue.record("untyped error \(error)")
        }
    }

    @Test func malformedSuccessBodyIsDecodingError() async {
        let transport = MockTransport { _ in (200, Fixtures.json(#"{"nope":1}"#)) }
        let client = APIClient(baseURL: base, transport: transport, tokens: StaticTokenProvider(token: "t"))
        do {
            _ = try await client.me()
            Issue.record("expected failure")
        } catch let error as APIError {
            #expect(error.code == "DECODING_FAILED")
        } catch {
            Issue.record("untyped error \(error)")
        }
    }
}
