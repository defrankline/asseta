#if os(iOS)
import AssetaModel
import AssetaSync
import Foundation

/// Accountability queries for the views (gating by ``FieldAccess``; the server enforces everything).
extension FieldModel {
    /// Fetches the tenant policies and lists the accountability screens use (saved for offline), then re-reads them.
    func refreshAccountability() async {
        guard let services, isOnline else { return }
        await services.online.refreshAccountability(permissions: tenant.permissions, myStaffID: myStaffID,
                                                    disabledCapabilities: tenant.disabledCapabilities)
        refresh()
    }

    /// My overdue-remittance flag, read online (kept for this session); nil offline or when the server does not show
    /// it to me (404).
    func remittanceOverdue(_ id: UUID) async -> RemittanceOverdueDTO? {
        guard isOnline, let online = services?.online, let dto = try? await online.remittanceOverdue(id) else { return nil }
        savedOverdue[id] = dto
        return dto
    }

    var accountabilityData: AccountabilityDirectory? { services?.accountability }
    var recorder: FieldRecorder? { services?.recorder }

    /// My staff record (from my synced cash custody), when known.
    var myStaffID: UUID? { (try? services?.directory.custodyBalances())?.first?.staffMemberID }

    /// Cash holders as picker options; I am listed first as "Me".
    func custodianOptions() -> [PickerOption] {
        let custodians = services?.accountability.custodians ?? []
        let me = myStaffID
        let mine = me.map { id in
            [PickerOption(id: id, title: FieldAccountabilityTexts.me, subtitle: custodians.first { $0.staffMemberID == id }?.fullName)]
        } ?? []
        return mine + custodians.filter { $0.staffMemberID != me }
            .sorted { $0.fullName.lowercased() < $1.fullName.lowercased() }
            .map { PickerOption(id: $0.staffMemberID, title: $0.fullName, subtitle: $0.employeeCode) }
    }

    /// The server's name for a custodian, else the saved custodian list, else the short id (names, not ids).
    func custodianName(_ id: UUID?, server name: String? = nil) -> String {
        if let name = name?.trimmingCharacters(in: .whitespacesAndNewlines), !name.isEmpty { return name }
        guard let id else { return FieldAccountabilityTexts.ackSomeone }
        return services?.accountability.custodians.first { $0.staffMemberID == id }?.fullName ?? DisplayName.shortID(id)
    }

    /// A machine's capture gate (policy snapshot, offline grant, trusted time).
    func gate(machineID: UUID) -> CaptureGate {
        (try? services?.directory.captureGate(machineID: machineID)) ?? .blocked(.noSnapshot)
    }

    /// A reading of mine by id.
    func reading(_ id: UUID) -> ReadingItem? { inbox.readings.first { $0.id == id } }

    /// Recorded reason for an online-only request.
    var noConnection: Bool { !isOnline }
}
#endif
