@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import AssetaTestSupport
import Foundation
import Testing

/// The company-closure request in the Owner app (read-only view, cancel with a reason); same cases as Android.
struct CompanyClosureOwnerTests {
    static let tenantID = UUID(uuidString: "11111111-1111-4111-8111-111111111111")!

    static func request(status: String = "REQUESTED", by: String? = "Asha Owner") -> String {
        let name = by.map { "\"\($0)\"" } ?? "null"
        return #"{"id":"cccccccc-0000-4000-8000-000000000001","tenant_id":"11111111-1111-4111-8111-111111111111","#
            + #""tenant_name":"Acme","status":"\#(status)","reason":"Selling the business","requested_by":null,"#
            + #""requested_by_name":\#(name),"requested_at":"2026-11-12T08:00:00Z","waiting_days":30,"#
            + #""scheduled_for":"2026-12-12T08:00:00Z","policy_version":"1","cancelled_by":null,"#
            + #""cancelled_by_name":"Ben Owner","cancelled_at":null,"cancel_reason":"Changed our mind","#
            + #""execute_now_by":null,"execute_now_at":null,"execute_now_reason":null,"started_at":null,"#
            + #""completed_at":null,"attempts":0,"last_error":null,"steps_done":[]}"#
    }

    static func tenant(permissions: [String]) -> TenantMembership {
        TenantMembership(tenantID: tenantID, name: "Acme", status: TenantStatus(rawValue: "ACTIVE"),
                         accessState: TenantAccessState(rawValue: "READ_ONLY"), permissions: permissions, menus: [],
                         accessStateReason: "Company closure requested: all its data will be deleted on 2026-12-12")
    }

    @Test func bannerOpensTheRequestOnlyWithThePermission() {
        #expect(CompanyClosureText.canOpen(Self.tenant(permissions: ["tenant.company.close"])))
        #expect(!CompanyClosureText.canOpen(Self.tenant(permissions: ["tenant.jobs.read"])))
        #expect(CompanyClosureText.bannerAction == "View closure request")
    }

    @Test func statusDecodesAndShowsReadOnlyRows() throws {
        let json = #"{"tenant_id":"11111111-1111-4111-8111-111111111111","company_name":"Acme","waiting_days":30,"#
            + #""request":\#(Self.request())}"#
        let status = try AssetaJSON.decoder().decode(CompanyDeletionStatusDTO.self, from: Data(json.utf8))
        let request = try #require(status.request)
        #expect(CompanyClosureText.canCancel(request))
        let utc = TimeZone(identifier: "UTC")!
        let rows = CompanyClosureText.rows(request, timeZone: utc).map { "\($0.0): \($0.1)" }
        #expect(rows == ["Status: Requested", "Asked by: Asha Owner", "Asked on: 12 Nov 2026",
                         "Deletion date: 12 Dec 2026", "Reason: Selling the business"])
        let cancelled = try AssetaJSON.decoder().decode(CompanyDeletionRequestDTO.self,
                                                        from: Data(Self.request(status: "CANCELLED", by: nil).utf8))
        #expect(!CompanyClosureText.canCancel(cancelled))
        #expect(CompanyClosureText.rows(cancelled, timeZone: utc).map(\.1)
            == ["Cancelled", "Unknown", "12 Nov 2026", "12 Dec 2026", "Selling the business", "Ben Owner", "Changed our mind"])
        #expect(CompanyClosureText.statusLabel(.inProgress) == "Deletion in progress")
        #expect(CompanyClosureText.statusLabel(CompanyDeletionStatus(rawValue: "ON_HOLD")) == "On hold")
        let none = try AssetaJSON.decoder().decode(CompanyDeletionStatusDTO.self, from: Data(
            #"{"tenant_id":"11111111-1111-4111-8111-111111111111","company_name":"Acme","waiting_days":30,"request":null}"#.utf8))
        #expect(none.request == nil && !CompanyClosureText.canCancel(none.request))
    }

    @Test func cancelNeedsAReasonAndAConnection() async throws {
        let transport = MockTransport { _ in (200, Data(Self.request(status: "CANCELLED").utf8)) }
        let client = APIClient(baseURL: URL(string: "https://api.example.test")!, transport: transport,
                               tokens: StaticTokenProvider(token: "t"), tenantID: Self.tenantID)
        #expect(await CompanyClosureCancel.run(client: client, reason: " ab ", isOnline: true)
            == .failed("Enter a reason (at least 3 characters)."))
        #expect(await CompanyClosureCancel.run(client: client, reason: "We keep going", isOnline: false)
            == .failed("Connect to the internet to cancel the closure."))
        #expect(transport.requests.isEmpty)

        guard case let .cancelled(result) = await CompanyClosureCancel.run(client: client, reason: "  We keep going ",
                                                                            isOnline: true) else {
            Issue.record("not cancelled"); return
        }
        #expect(result.status == .cancelled)
        let request = try #require(transport.requests.single)
        #expect(request.httpMethod == "POST")
        #expect(request.url?.path == "/api/v1/tenant/company/deletion-request/cancel")
        #expect(request.value(forHTTPHeaderField: "X-Tenant-ID") == Self.tenantID.uuidString.lowercased())
        let body = try #require(try JSONSerialization.jsonObject(with: request.httpBody ?? Data()) as? [String: Any])
        #expect(body["reason"] as? String == "We keep going")
        #expect(CompanyClosureText.cancelled == "Closure cancelled. The company is back to normal.")
    }

    @Test func cancelShowsTheServerMessage() async {
        let transport = MockTransport { _ in
            (409, Data(#"{"error":{"code":"CLOSURE_NOT_CANCELLABLE","message":"The deletion has started.","correlation_id":"c"}}"#.utf8))
        }
        let client = APIClient(baseURL: URL(string: "https://api.example.test")!, transport: transport,
                               tokens: StaticTokenProvider(token: "t"), tenantID: Self.tenantID)
        #expect(await CompanyClosureCancel.run(client: client, reason: "We keep going", isOnline: true)
            == .failed("The deletion has started."))
    }
}

private extension Array {
    var single: Element? { count == 1 ? first : nil }
}
