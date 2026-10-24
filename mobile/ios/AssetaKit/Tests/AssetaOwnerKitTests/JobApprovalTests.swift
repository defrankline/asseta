@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import Foundation
import Testing

/// Owner approval of jobs requested from the field, identical to Android `JobApprovalTest`.
struct JobApprovalTests {
    static let jobID = UUID(uuidString: "abababab-0000-4000-8000-000000000001")!

    static func job(rateSource: String = "PENDING_PRICE", status: String = "PENDING_APPROVAL", requestedBy: String? = "Juma Field",
                    note: String? = "Clear the access road", requested: Bool = true) throws -> JobDTO {
        try AssetaJSON.decoder().decode(JobDTO.self, from: JSONSerialization.data(withJSONObject: fields(
            rateSource: rateSource, status: status, requestedBy: requestedBy, note: note, requested: requested)))
    }

    static func fields(rateSource: String = "PENDING_PRICE", status: String = "PENDING_APPROVAL", requestedBy: String? = "Juma Field",
                       note: String? = "Clear the access road", requested: Bool = true) -> [String: Any] {
        var fields: [String: Any] = [
            "id": jobID.uuidString.lowercased(), "contract_id": "dddddddd-0000-4000-8000-000000000001",
            "job_number": "J-2026-105", "machine_id": "bbbbbbbb-0000-4000-8000-000000000002", "job_site_id": NSNull(),
            "supervisor_id": "dddddddd-0000-4000-8000-00000000000d", "status": status,
            "planned_start": "2026-10-24T06:00:00Z", "planned_end": NSNull(), "currency": "TZS",
            "hourly_rate": rateSource == "PENDING_PRICE" ? "0" : "95000.0000", "minimum_hours": "0.0000",
            "standby_treatment": "EXCLUDED", "standby_rate": NSNull(), "mobilization_fee": "0.0000",
            "discount_percent": "0.0000", "tax_rate_percent": "15.0000", "rate_source": rateSource,
            "approved_at": NSNull(), "started_at": NSNull(), "completed_at": NSNull(), "version": 1,
            "cancellation_reason": NSNull(), "request_note": note ?? NSNull(), "requested_by_name": requestedBy ?? NSNull(),
        ]
        fields["requested_by_staff_id"] = requested ? "dddddddd-0000-4000-8000-00000000000d" : NSNull()
        return fields
    }

    @Test func fieldRequestsSayWhoAskedForThem() throws {
        let job = try Self.job()
        #expect(job.isFieldRequest && job.needsPrice && job.requestNote == "Clear the access road")
        #expect(JobApprovalText.requestedBy(job) == "Requested from the field by Juma Field")
        #expect(JobApprovalText.requestedBy(try Self.job(requestedBy: nil)) == "Requested from the field by a supervisor")
        #expect(JobApprovalText.requestedBy(try Self.job(rateSource: "RATE_CARD", note: nil, requested: false)) == nil)
    }

    @Test func approvingAJobWithoutAPriceNeedsAnHourlyRate() throws {
        let job = try Self.job()
        #expect(JobApprovalText.hourlyRateLabel(currency: job.currency) == "Hourly rate (TZS)")
        #expect(JobApprovalText.pendingPriceHelper == "No rate card applies — set the price to approve")
        #expect(!JobApprovalText.canApprove(job: job, rateText: ""))
        #expect(!JobApprovalText.canApprove(job: job, rateText: "0"))
        #expect(!JobApprovalText.canApprove(job: job, rateText: "abc"))
        #expect(JobApprovalText.parseRate(" 95,000.50 ") == Decimal(string: "95000.50"))
        #expect(JobApprovalText.rateToSend(job: job, text: "95000") == .some(Decimal(95000)))
        // A priced job keeps its rate: APPROVE goes without hourly_rate.
        let priced = try Self.job(rateSource: "RATE_CARD:x")
        #expect(!priced.needsPrice && JobApprovalText.canApprove(job: priced, rateText: ""))
        #expect(JobApprovalText.rateToSend(job: priced, text: "") == .some(nil))
    }

    @Test func approveAndDeclineSendTheTransition() throws {
        let key = UUID()
        let approve = try OwnerAPI.approveJob(Self.jobID, hourlyRate: Decimal(string: "95000.50"), idempotencyKey: key)
        #expect(approve.method == .post && approve.path == "/api/v1/tenant/jobs/\(Self.jobID.uuidString.lowercased())/transitions")
        #expect(approve.idempotencyKey == key)
        let body = try #require(approve.body.flatMap { try JSONSerialization.jsonObject(with: $0) as? [String: Any] })
        #expect(body["action"] as? String == "APPROVE" && body["hourly_rate"] as? String == "95000.5" && body["reason"] == nil)

        let plain = try OwnerAPI.approveJob(Self.jobID, hourlyRate: nil, idempotencyKey: key)
        let plainBody = try #require(plain.body.flatMap { try JSONSerialization.jsonObject(with: $0) as? [String: Any] })
        #expect(plainBody.keys.sorted() == ["action"])

        let decline = try OwnerAPI.declineJob(Self.jobID, reason: "  No operator free  ", idempotencyKey: key)
        let declineBody = try #require(decline.body.flatMap { try JSONSerialization.jsonObject(with: $0) as? [String: Any] })
        #expect(declineBody["action"] as? String == "CANCEL" && declineBody["reason"] as? String == "No operator free")
        #expect(JobApprovalText.decline == "Decline" && JobApprovalText.reason == "Reason")
        #expect(!JobApprovalText.canDecline(reason: "  ") && JobApprovalText.canDecline(reason: "Busy"))
    }

    @Test func priceRequiredAndStaleDecisionsAreExplained() {
        let price = APIError.server(status: 422, body: ErrorBody(code: "PRICE_REQUIRED", message: "x", correlationID: "c"))
        #expect(JobApprovalText.message(for: price) == "Set an hourly rate before approving this job.")
        #expect(DecisionErrorText.message(for: price) == "Set an hourly rate before approving this job.")
        let stale = APIError.server(status: 422, body: ErrorBody(code: "INVALID_JOB_TRANSITION", message: "x", correlationID: "c"))
        #expect(JobApprovalText.needsReload(stale) && !JobApprovalText.needsReload(price))
    }

    @Test func approvingIsGatedOnTheJobApprovePermission() {
        #expect(OwnerFeatures(permissions: ["tenant.job.read", "tenant.job.approve"]).approveJobs)
        #expect(!OwnerFeatures(permissions: ["tenant.job.read"]).approveJobs)
    }

    @Test func requestedJobSampleMatchesTheContract() throws {
        let json = String(decoding: try JSONSerialization.data(withJSONObject: Self.fields()), as: UTF8.self)
        #expect(try Contract.missingRequired(schema: "JobDto", json: json) == [])
    }
}
