import Foundation
import Testing

/// Contract samples for the Owner DTOs, checked against `contracts/openapi.json` (read in place):
/// every `required` property of the schema (recursively through `$ref`s) must be present in the
/// sample, so a sample cannot silently drift from the server contract.
enum Contract {
    static var repositoryRoot: URL {
        URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
    }

    nonisolated(unsafe) static let schemas: [String: Any] = {
        let url = repositoryRoot.appendingPathComponent("contracts/openapi.json")
        guard let data = try? Data(contentsOf: url),
              let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let components = root["components"] as? [String: Any],
              let schemas = components["schemas"] as? [String: Any] else { return [:] }
        return schemas
    }()

    /// Missing required properties of `schema` in `json`, as dotted paths (empty = conforms).
    static func missingRequired(schema: String, json: String) throws -> [String] {
        let value = try JSONSerialization.jsonObject(with: Data(json.utf8), options: [.fragmentsAllowed])
        var missing: [String] = []
        check(value, schemaName: schema, path: schema, missing: &missing)
        return missing
    }

    private static func check(_ value: Any, schemaName: String, path: String, missing: inout [String]) {
        guard let schema = schemas[schemaName] as? [String: Any] else {
            missing.append("\(path) (schema \(schemaName) not in contract)")
            return
        }
        check(value, schema: schema, path: path, missing: &missing)
    }

    private static func check(_ value: Any, schema: [String: Any], path: String, missing: inout [String]) {
        if let ref = schema["$ref"] as? String {
            check(value, schemaName: String(ref.split(separator: "/").last ?? ""), path: path, missing: &missing)
            return
        }
        if let options = schema["anyOf"] as? [[String: Any]] {
            if value is NSNull { return }
            for option in options where option["type"] as? String != "null" {
                check(value, schema: option, path: path, missing: &missing)
            }
            return
        }
        if let items = schema["items"] as? [String: Any], let array = value as? [Any] {
            for (index, element) in array.enumerated() {
                check(element, schema: items, path: "\(path)[\(index)]", missing: &missing)
            }
            return
        }
        guard let object = value as? [String: Any] else { return }
        let properties = schema["properties"] as? [String: [String: Any]] ?? [:]
        for key in schema["required"] as? [String] ?? [] where object[key] == nil {
            missing.append("\(path).\(key)")
        }
        for (key, property) in properties {
            if let child = object[key] { check(child, schema: property, path: "\(path).\(key)", missing: &missing) }
        }
    }

    static func data(_ json: String) -> Data { Data(json.utf8) }
}

enum Samples {
    static let tenant = "11111111-1111-4111-8111-111111111111"
    static let machine = "aaaaaaaa-0000-4000-8000-000000000001"
    static let job = "bbbbbbbb-0000-4000-8000-000000000001"

    static let overview = """
    {"tenant_id":"\(tenant)","as_of":"2026-10-22T08:00:00.123Z","timezone":"Africa/Dar_es_Salaam",
     "fleet":{"machines":12,"connectivity":{"live":5,"recent":2,"stale":1,"offline":2,"never":1,"no_tracker":1},
              "reported_work_state":{"WORKING":4,"IDLE":8},"engine_on_verified":3,
              "open_alerts":{"critical":1,"warning":2,"info":0},"latest_source_at":"2026-10-22T07:59:10Z"},
     "work":{"jobs_by_status":{"IN_PROGRESS":3,"APPROVED":2},"pending_approvals":2,"readings_needing_review":null,
             "open_exceptions":1,"latest_source_at":"2026-10-22T07:30:00Z"},
     "money":{"month_start":"2026-10-01","currencies":[{"currency":"TZS","receivables_outstanding":"1092500.0000",
              "receivables_overdue":"0.0000","overdue_invoices":0,"verified_receipts_mtd":"500000.0000",
              "approved_expenses_mtd":"150000.0000","cash_with_supervisors":"50000.0000"}],"latest_source_at":null},
     "risk":{"open_cases":{"critical":0,"warning":1,"info":0},"signals_last_7_days":null,"latest_source_at":null}}
    """

    static let overviewFleetOnly = """
    {"tenant_id":"\(tenant)","as_of":"2026-10-22T08:00:00Z","timezone":"UTC",
     "fleet":{"machines":0,"connectivity":{},"reported_work_state":{},"engine_on_verified":0,"open_alerts":{},
              "latest_source_at":null},"work":null,"money":null,"risk":null}
    """

    static func machineJSON(connectivity: String = "LIVE", isLive: Bool = true, lastMessage: String? = "2026-10-22T07:58:00Z",
                            lat: String = "-6.8", alerts: Int = 1) -> String {
        """
        {"machine_id":"\(machine)","asset_code":"EX-01","name":"Excavator 1","machine_status":"ACTIVE",
         "longitude":39.28,"latitude":\(lat),"accuracy_m":8.5,"position_time":"2026-10-22T07:58:00Z",
         "last_message_at":\(lastMessage.map { "\"\($0)\"" } ?? "null"),"last_seen_age_seconds":120,
         "position_source":"TRACKER","position_quality":"GOOD","connectivity":"\(connectivity)","is_live":\(isLive),
         "reported_work_status":"WORKING","observed_engine":"ON","observed_motion":"STATIONARY",
         "location_compliance":"COMPLIANT","tracker_id":null,"tracker_state":"ACTIVE","supervisor":"Sam",
         "operator":null,"open_alerts":\(alerts),"policy_version":"v3"}
        """
    }

    static let history = """
    {"machine_id":"\(machine)","truncated":false,"distance_km":12.4,"policy_version":"v3",
     "points":[{"event_time":"2026-10-22T06:00:00Z","longitude":39.28,"latitude":-6.8,"accuracy_m":null,
                "speed_kmh":12.5,"heading_deg":90,"ignition":true,"quality":"GOOD","is_late":false,
                "received_at":"2026-10-22T06:00:02Z"}],
     "stops":[{"start":"2026-10-22T06:10:00Z","end":"2026-10-22T06:40:00Z","duration_seconds":1800,
               "longitude":39.28,"latitude":-6.81}],
     "site_visits":[{"geofence_id":"cccccccc-0000-4000-8000-000000000001","geofence_name":"Site A",
                     "entered_at":"2026-10-22T06:05:00Z","exited_at":null,"duration_seconds":600}]}
    """

    static let jobDTO = """
    {"id":"\(job)","contract_id":"dddddddd-0000-4000-8000-000000000001","job_number":"J-1001",
     "machine_id":"\(machine)","job_site_id":null,"supervisor_id":null,"status":"IN_PROGRESS",
     "planned_start":"2026-10-20T06:00:00Z","planned_end":null,"currency":"TZS","hourly_rate":"95000.0000",
     "minimum_hours":"0.0000","standby_treatment":"EXCLUDED","standby_rate":null,"mobilization_fee":"0.0000",
     "discount_percent":"0.0000","tax_rate_percent":"15.0000","rate_source":"RATE_CARD",
     "approved_at":"2026-10-19T10:00:00Z","started_at":"2026-10-20T06:05:00Z","completed_at":null,"version":3}
    """

    static let jobsPage = #"{"items":[\#(jobDTO)],"total":1,"page":1,"page_size":50}"#

    static let jobSummary = """
    {"job":\(jobDTO),"opening_reading":"1200.5","closing_reading":null,"meter_hours":null,"nonbillable_hours":"0",
     "standby_hours":"0","billable_hours":null,"open_exceptions":1,"blocking_exceptions":0,"billing_ready":false,
     "charges":{"currency":"TZS","lines":[{"kind":"HIRE","description":"Hire","quantity":"11.5","unit_price":"95000",
       "amount":"1092500"}],"subtotal":"1092500","discount_total":"0","tax_total":"0","total":"1092500"},
     "policy_version":"v2"}
    """

    static func alertJSON(status: String = "OPEN", severity: String = "CRITICAL") -> String {
        """
        {"id":"eeeeeeee-0000-4000-8000-000000000001","machine_id":"\(machine)","tracker_id":null,
         "alert_type":"GEOFENCE_EXIT","severity":"\(severity)","status":"\(status)","event_time":"2026-10-22T07:00:00Z",
         "title":"Left site","evidence":{"distance_m":420.5,"geofence":"Site A"},"policy_version":"v1",
         "created_at":"2026-10-22T07:00:01Z","acknowledged_at":null,"resolved_at":null,"resolution_note":null}
        """
    }

    static let approvalsPage = """
    {"items":[{"id":"ffffffff-0000-4000-8000-000000000001","subject_type":"EXPENSE",
      "subject_id":"ffffffff-0000-4000-8000-000000000002","amount":"250000.0000","currency":"TZS",
      "reason":"Above auto-approve limit","policy_version":"v4","status":"PENDING",
      "requested_by":"ffffffff-0000-4000-8000-000000000003","requested_at":"2026-10-22T05:00:00Z",
      "decided_by":null,"decided_at":null,"decision_note":null}],"total":1,"page":1,"page_size":50}
    """

    static let caseDetail = """
    {"case":{"id":"12121212-0000-4000-8000-000000000001","case_number":"CASE-0007","title":"Fuel above band",
      "subject_type":"MACHINE","subject_id":"\(machine)","machine_id":"\(machine)","job_id":null,
      "staff_member_id":null,"severity":"WARNING","status":"IN_REVIEW","assignee_user_id":null,"assignee_name":null,
      "opened_at":"2026-10-21T09:00:00Z","last_signal_at":"2026-10-22T06:00:00Z","resolved_at":null,
      "resolved_by":null,"latest_outcome":null,"signal_count":2,"policy_version":"v1","version":1},
     "signals":[{"id":"13131313-0000-4000-8000-000000000001","source_type":"RISK_SIGNAL",
       "source_id":"14141414-0000-4000-8000-000000000001","code":"FUEL_ABOVE_BAND","severity":"WARNING",
       "observed_at":"2026-10-22T06:00:00Z","evidence":{"litres":"120.5"},"linked_at":"2026-10-22T06:00:05Z"}],
     "notes":[{"id":"15151515-0000-4000-8000-000000000001","kind":"NOTE","body":"Checking receipts",
       "author_user_id":null,"author_name":"Owner","created_at":"2026-10-22T06:30:00Z"}],
     "outcomes":[]}
    """

    static let capturesPage = """
    {"items":[{"id":"16161616-0000-4000-8000-000000000001","job_id":"\(job)","machine_id":"\(machine)",
      "kind":"OPENING","capture_mode":"AUTOMATIC","reading":"1200.5","ocr_value":"1200.5","ocr_confidence":0.97,
      "manually_corrected":false,"photo_attachment_id":"17171717-0000-4000-8000-000000000001",
      "photo_sha256":"ab","gps_status":"FIX","latitude":-6.8,"longitude":39.28,"accuracy_m":6,
      "location_captured_at":"2026-10-20T06:04:00Z","captured_at":"2026-10-20T06:04:00Z",
      "received_at":"2026-10-20T06:10:00Z","policy_version":"v2","state":"ACCEPTED","tracker_comparison":null,
      "supersedes_id":null}],"total":1,"page":1,"page_size":10}
    """

    static func notificationJSON(entity: String = "case", id: String? = "12121212-0000-4000-8000-000000000001",
                                 path: String? = "/tenant/cases/12121212-0000-4000-8000-000000000001") -> String {
        """
        {"id":"18181818-0000-4000-8000-000000000001","type":"ANOMALY_DETECTED","category":"ANOMALY",
         "severity":"WARNING","priority":"HIGH","title":"Needs review","body":"Fuel above band",
         "created_at":"2026-10-22T06:00:10Z","read_at":null,
         "target":{"entity":"\(entity)","id":\(id.map { "\"\($0)\"" } ?? "null"),"path":\(path.map { "\"\($0)\"" } ?? "null")},
         "tenant_id":"\(tenant)","data":{"kind":"CASE_OPENED"}}
        """
    }

    static let pushDevice = """
    {"id":"19191919-0000-4000-8000-000000000001","tenant_id":"\(tenant)","platform":"IOS","app":"OWNER",
     "token_hint":"…a1b2","app_version":"0.1.0 (1)","device_label":"iPhone","active":true,
     "created_at":"2026-10-22T06:00:00Z","last_registered_at":"2026-10-22T06:00:00Z","deactivated_at":null,
     "deactivation_reason":null}
    """

    static let routing = """
    [{"category":"ACTION","severity":"CRITICAL","push":true,"email":true,"in_app":true,"mandatory_channels":["IN_APP","PUSH"],"source":"SYSTEM"},
     {"category":"ACTION","severity":"WARNING","push":true,"email":false,"in_app":true,"mandatory_channels":["IN_APP"],"source":"SYSTEM"},
     {"category":"ANOMALY","severity":"INFO","push":false,"email":false,"in_app":true,"mandatory_channels":["IN_APP"],"source":"USER"},
     {"category":"BILLING","severity":"WARNING","push":false,"email":true,"in_app":true,"mandatory_channels":["IN_APP"],"source":"TENANT"}]
    """
}
