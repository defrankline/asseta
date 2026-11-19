#if os(iOS)
import AssetaModel
import AssetaStore
import AssetaSync
import Foundation

/// ADR-008 queries for the Home, Machine report, Money and Dashboard screens (synced snapshots and this phone's outbox).
extension FieldModel {
    var reportStates: [MachineReportStatusDTO] { services?.directory.machineReportStates() ?? [] }
    var reportReasons: [MachineReportReasonDTO] { services?.directory.machineReportReasons() ?? [] }
    var myReports: [MachineReportDTO] { services?.directory.myMachineReports() ?? [] }
    var unsentReports: [UUID: MachineReportPayload] { services?.directory.unsentMachineReports() ?? [:] }
    var openCreditInvoices: [OpenCreditInvoice] { services?.directory.openCreditInvoices() ?? [] }
    /// Customers' usable hours (machine report snapshot): Dashboard "Customer balances".
    var reportHours: [AvailableHoursDTO] { services?.directory.machineReportHours() ?? [] }

    /// The tenant's reminder days (`machine_report_reminder_days`): 3 while the policy is unknown or failed to load,
    /// nil (reminders off) when the tenant set it to null.
    var reportReminderDays: Int? { MachineReportStanding.reminderDays(access.hours) }

    /// Each of my machines with its report status.
    var machineStandings: [(state: MachineReportStatusDTO, standing: MachineReportStanding)] {
        let unsent = unsentReports
        return reportStates.map { ($0, MachineReportStanding.of($0, unsentReport: unsent[$0.machineID] != nil,
                                                                 reminderDays: reportReminderDays)) }
    }

    /// Machines that need a report (Home "Hours to report", the tile's "due" badge).
    var reportsDue: Int { machineStandings.filter(\.standing.needsReport).count }
    /// My reports waiting for a decision (synced and unsent).
    var reportsAwaiting: Int {
        machineStandings.filter { if case .awaitingApproval = $0.standing { true } else { false } }.count
    }

    /// The synced machine (meter precision), else one made from the report status.
    func reportMachine(_ id: UUID) -> MachineDTO? {
        if let machine = machines.first(where: { $0.id == id }) { return machine }
        guard let state = reportStates.first(where: { $0.machineID == id }) else { return nil }
        return MachineDTO(id: id, assetCode: state.machineCode ?? "", name: state.machineName ?? "",
                          meterDecimalPlaces: state.meterDecimalPlaces)
    }

    /// "EX-01" for a machine id (Recent rows).
    func machineCode(_ id: UUID) -> String {
        machines.first { $0.id == id }?.assetCode ?? reportStates.first { $0.machineID == id }?.machineCode ?? ""
    }

    func customerName(_ id: UUID) -> String? { customers.first { $0.id == id }?.name }

    /// Each customer's hours a report on `machineID` may draw on (synced, less what my other unsent reports hold).
    func reportCaps(machineID: UUID) -> [UUID: (name: String, hours: Decimal)] {
        let held = services?.directory.hoursHeldByUnsentReports(excluding: machineID) ?? [:]
        var caps = MachineReportRules.available(services?.directory.machineReportHours() ?? [], machineID: machineID,
                                                heldByUnsent: held)
        for (id, row) in caps where row.name.isEmpty { caps[id] = (customerName(id) ?? "", row.hours) }
        return caps
    }

    /// Every operation of this user on the phone (Money and Recent figures).
    var myOperations: [ClientOperation] {
        guard let services else { return [] }
        return (try? services.store.outbox.operations(tenantID: tenant.tenantID, owner: services.account.subject,
                                                      statuses: Set(ClientOperationStatus.allCases))) ?? []
    }

    var unsentOperations: [ClientOperation] { myOperations.filter { [.pending, .sent, .quarantined].contains($0.status) } }

    /// Money in the company currency for display ("TZS 1,900,000" or plain grouped digits).
    func money(_ value: Decimal, currency: Bool = true) -> String {
        let digits = value.formatted(.number.precision(.fractionLength(0...2)))
        guard currency, let code = baseCurrency, !code.isEmpty else { return digits }
        return "\(code) \(digits)"
    }

    /// Queues a report (and its reading) and syncs.
    func submitReport(machineID: UUID, reading: NewReportReading, report: CheckedReport?, opening: Bool, reportID: UUID) throws {
        try perform {
            try $0.recordMachineReport(machineID: machineID, reading: reading, report: report, opening: opening, reportID: reportID)
        }
    }
}
#endif
