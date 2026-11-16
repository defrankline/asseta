import AssetaModel
import AssetaOwnerKit
import Foundation
import Testing

/// Owner DTOs decode the contract-conformant samples (and the samples conform to the contract).
struct ContractDecodingTests {
    static let cases: [(schema: String, json: String)] = [
        ("TenantOverviewDto", Samples.overview),
        ("TenantOverviewDto", Samples.overviewFleetOnly),
        ("MachineMapDto", Samples.machineJSON()),
        ("HistoryDto", Samples.history),
        ("AlertDto", Samples.alertJSON()),
        ("Page_ApprovalRequestDto_", Samples.approvalsPage),
        ("AnomalyCaseDetailDto", Samples.caseDetail),
        ("Page_MeterCaptureDto_", Samples.capturesPage),
        ("NotificationDto", Samples.notificationJSON()),
        ("PushDeviceDto", Samples.pushDevice),
        ("NotificationRoutingDto", Samples.routing),
    ]

    @Test func contractIsAvailable() {
        #expect(Contract.schemas["TenantOverviewDto"] != nil, "contracts/openapi.json not found")
    }

    @Test(arguments: 0..<ContractDecodingTests.cases.count)
    func sampleHasEveryRequiredContractField(_ index: Int) throws {
        let (schema, json) = Self.cases[index]
        #expect(try Contract.missingRequired(schema: schema, json: json) == [])
    }

    @Test func overviewDecodesAllSectionsWithFreshness() throws {
        let overview = try AssetaJSON.decoder().decode(TenantOverviewDTO.self, from: Contract.data(Samples.overview))
        #expect(overview.fleet?.machines == 12)
        #expect(overview.fleet?.connectivity.noTracker == 1)
        #expect(overview.fleet?.openAlerts.total == 3)
        #expect(overview.fleet?.latestSourceAt != nil)
        #expect(overview.work?.pendingApprovals == 2)
        #expect(overview.work?.machineReportsByStatus["APPROVED"] == 5)
        #expect(overview.work?.readingsNeedingReview == nil) // permission-gated count
        #expect(overview.money?.currencies.first?.receivablesOutstanding.value == Decimal(1_092_500))
        #expect(overview.money?.latestSourceAt == nil)
        #expect(overview.risk?.signalsLast7Days == nil)
    }

    @Test func overviewOmittedSectionsAndEmptyCountsDecode() throws {
        let overview = try AssetaJSON.decoder().decode(TenantOverviewDTO.self,
                                                       from: Contract.data(Samples.overviewFleetOnly))
        #expect(overview.work == nil && overview.money == nil && overview.risk == nil)
        #expect(overview.fleet?.connectivity.live == 0)
        #expect(overview.fleet?.openAlerts.total == 0)
    }

    @Test func machineAndHistoryDecode() throws {
        let machine = try AssetaJSON.decoder().decode(MachineMapDTO.self, from: Contract.data(Samples.machineJSON()))
        #expect(machine.connectivity == .live && machine.isLive && machine.hasPosition)
        #expect(machine.observedEngine == .on)
        let history = try AssetaJSON.decoder().decode(HistoryDTO.self, from: Contract.data(Samples.history))
        #expect(history.points.count == 1 && history.stops.first?.durationSeconds == 1800)
        #expect(history.siteVisits.first?.exitedAt == nil)
    }

    @Test func unknownServerEnumValuesStillDecode() throws {
        let json = Samples.machineJSON(connectivity: "SATELLITE_ONLY")
        let machine = try AssetaJSON.decoder().decode(MachineMapDTO.self, from: Contract.data(json))
        #expect(machine.connectivity.rawValue == "SATELLITE_ONLY")
        #expect(machine.connectivity.humanized == "Satellite only")
        let alert = try AssetaJSON.decoder().decode(AlertDTO.self,
                                                    from: Contract.data(Samples.alertJSON(severity: "EMERGENCY")))
        #expect(alert.severity.rank == 2) // unknown ranks like WARNING, never hidden
    }

    /// ADR-008: the job, contract, hire invoice, revenue, non-revenue, unbilled, daily sheet and check-in endpoints are gone;
    /// the meter exception operations were renamed (same paths) and the Owner app calls them by path.
    @Test func removedAndRenamedOperationsFollowTheContract() throws {
        let paths = try Contract.root()["paths"] as? [String: [String: Any]] ?? [:]
        var operationIDs: [String: String] = [:]
        for (path, methods) in paths {
            for (_, op) in methods {
                if let id = (op as? [String: Any])?["operationId"] as? String { operationIDs[id] = path }
            }
        }
        for removed in ["createJob", "requestJob", "listJobs", "getJobSummary", "transitionJob", "listJobCaptures",
                        "listJobActivities", "listJobAcknowledgements", "listFieldContracts", "listHireInvoices",
                        "listUnbilledWork", "recordSiteCheckin", "listSiteCheckins", "listDailyMachineSheet",
                        "getDailyMachineSheetDay", "listRevenueDifferences", "getRevenueDifference",
                        "listNonRevenueApprovals", "decideNonRevenueApproval", "listJobExceptions", "getJobException",
                        "reviewJobException"] {
            #expect(operationIDs[removed] == nil, "\(removed) is still in the contract")
        }
        #expect(operationIDs["listMeterExceptions"] == "/api/v1/tenant/exceptions")
        #expect(operationIDs["getMeterException"] == "/api/v1/tenant/exceptions/{exception_id}")
        #expect(operationIDs["reviewMeterException"] == "/api/v1/tenant/exceptions/{exception_id}/review")
        #expect(OwnerAPI.exceptions(status: "OPEN").path == "/api/v1/tenant/exceptions")
        #expect(OwnerAPI.exceptions(status: "OPEN").queryItems.allSatisfy { $0.name != "job_id" })
        #expect(operationIDs["getEffectivePolicy"] == "/api/v1/tenant/policies/{ptype}/effective")
        #expect(OwnerAPI.customerHoursPolicy().path == "/api/v1/tenant/policies/CUSTOMER_HOURS/effective")
    }

    @Test func moneyAsJSONNumberIsRejected() {
        let bad = Samples.approvalsPage.replacingOccurrences(of: "\"250000.0000\"", with: "250000")
        #expect(throws: DecodingError.self) {
            try AssetaJSON.decoder().decode(Page<ApprovalRequestDTO>.self, from: Contract.data(bad))
        }
    }

    @Test func caseDetailCapturesAndNotificationDecode() throws {
        let detail = try AssetaJSON.decoder().decode(AnomalyCaseDetailDTO.self, from: Contract.data(Samples.caseDetail))
        #expect(detail.case.caseNumber == "CASE-0007" && detail.signals.first?.evidence["litres"]?.stringValue == "120.5")
        let captures = try AssetaJSON.decoder().decode(Page<MeterCaptureDTO>.self,
                                                       from: Contract.data(Samples.capturesPage))
        #expect(captures.items.first?.photoAttachmentID != nil)
        let note = try AssetaJSON.decoder().decode(NotificationDTO.self, from: Contract.data(Samples.notificationJSON()))
        #expect(note.isUnread && note.target?.entity == "case")
        let routing = try AssetaJSON.decoder().decode([NotificationRoutingDTO].self, from: Contract.data(Samples.routing))
        #expect(routing.count == 4 && routing[0].mandatoryChannels.contains("PUSH"))
    }

    @Test func decisionBodiesEncodeWireNames() throws {
        let body = String(decoding: try AssetaJSON.encoder().encode(ApprovalDecisionIn(approve: false, note: "No receipt")),
                          as: UTF8.self)
        #expect(body == #"{"approve":false,"note":"No receipt"}"#)
        let action = String(decoding: try AssetaJSON.encoder().encode(AlertActionIn(action: .resolve, note: "Back on site")),
                            as: UTF8.self)
        #expect(action == #"{"action":"RESOLVE","note":"Back on site"}"#)
        let push = String(decoding: try AssetaJSON.encoder().encode(
            PushDeviceIn(platform: "IOS", app: "OWNER", token: "ab", appVersion: nil, deviceLabel: nil)), as: UTF8.self)
        #expect(push.contains(#""app":"OWNER""#) && push.contains(#""platform":"IOS""#))
    }
}
