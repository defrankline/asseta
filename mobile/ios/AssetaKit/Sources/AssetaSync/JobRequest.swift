import AssetaModel
import AssetaNetwork
import AssetaStore
import Foundation

/// Wording of the supervisor's job request (Path B: the supervisor asks from the field, the owner approves).
/// Identical to Android `JobRequestTexts`.
public enum JobRequestText {
    public static let button = "Request job"
    public static let formTitle = "Request a job"
    public static let contract = "Customer contract"
    public static let machine = "Machine"
    public static let site = "Site (optional)"
    public static let plannedStart = "Planned start"
    public static let plannedEnd = "Planned end (optional)"
    public static let note = "What the customer asked for"
    public static let submit = "Send for approval"
    public static let notSent = "Waiting for approval (not yet sent)"
    public static let waiting = "Waiting for approval"
    public static let declined = "Declined"
    /// Shown instead of a job number until the server has assigned one.
    public static let unnumbered = "Requested job"
    /// Title of its outbox item.
    public static let operation = "Job request"
    /// The site picker's "none" row: the server uses the contract's site.
    public static let notSet = "Not set"
    public static let footer = "The owner sets the price and approves the job. You can start it once it is approved."
    public static let noContracts = "No contracts on this phone yet. Connect to the internet once to load them."
    public static let noMachines = "No machines on this phone yet. Connect to the internet once to load them."
    public static let unavailableTitle = "Job requests not available"
    public static let neverSynced = "Sync once while online before requesting a job."
    public static let notSupported = "Your company's server does not accept job requests yet."
    public static let clear = "Clear"
    public static let alreadySaved = "This request is already saved."
    public static let chooseContract = "Choose the customer contract."
    public static let chooseMachine = "Choose the machine."
    public static let endBeforeStart = "The planned end is before the planned start."
    public static let noteTooLong = "What the customer asked for: at most 1000 characters."
    public static let noteLimit = 1000
    /// Days an accepted request whose job is not on the phone yet keeps showing (the server's recently-closed window).
    public static let showAcceptedDays = 14.0
}

/// Where a job the supervisor requested stands, for the jobs list chip.
public enum JobRequestState: Sendable, Equatable {
    /// Saved on the phone, not yet accepted by the server.
    case notSent
    /// Accepted by the server, waiting for the owner.
    case waiting
    /// The owner declined it (the job was cancelled), with the reason when known.
    case declined(reason: String?)
    /// The server refused the request (rejected, conflict or held; details on the sync status screen).
    case problem(ClientOperationStatus)

    public var label: String {
        switch self {
        case .notSent: JobRequestText.notSent
        case .waiting: JobRequestText.waiting
        case .declined: JobRequestText.declined
        case let .problem(status): JobRequestState.syncState(status)
        }
    }

    /// Same wording as the sync state labels (Android `FieldTexts.syncState`).
    static func syncState(_ status: ClientOperationStatus) -> String {
        switch status {
        case .pending: "Waiting to sync"
        case .sent: "Sending"
        case .acked: "Synced"
        case .failed: "Rejected"
        case .conflict: "Conflict"
        case .quarantined: "Held"
        }
    }

    /// The chip of a job on the phone: any job waiting for approval, or a requested job the owner declined
    /// (Android `JobRequestTexts.jobChip`); nil shows the normal status.
    static func of(job: JobDTO, requestOp: ClientOperation?) -> JobRequestState? {
        switch job.status {
        case .pendingApproval: return .waiting
        case .cancelled where job.isFieldRequest || requestOp != nil: return .declined(reason: job.cancellationReason)
        default: return nil
        }
    }

    /// A request not on the phone as a job yet, from its outbox status (Android `JobRequestRules.state`).
    static func of(operation: ClientOperationStatus) -> JobRequestState {
        switch operation {
        case .acked: .waiting
        case .pending, .sent: .notSent
        case .failed, .conflict, .quarantined: .problem(operation)
        }
    }
}

extension FieldRecorder {
    /// Nil when job requests can be recorded, else why not (never synced, or a server without OP_JOB_REQUEST).
    public func jobRequestUnavailable() -> String? {
        guard let capabilities = try? store.syncState.value(SyncKey.capabilities, tenant: tenantID.uuidString.lowercased()) else {
            return JobRequestText.neverSynced
        }
        guard capabilities.split(separator: ",").contains(Substring(SyncCapability.jobRequest)) else {
            return JobRequestText.notSupported
        }
        return nil
    }

    /// Queues a `JOB_REQUEST` (works offline). `clientID` is generated once per form visit and becomes the job id,
    /// so a second save of the same visit is refused and a replay on the server returns the same job.
    @discardableResult
    public func requestJob(contractID: UUID?, machineID: UUID?, jobSiteID: UUID?, plannedStart: Date, plannedEnd: Date?,
                           note: String?, at date: Date = Date(), clientID: UUID = UUID()) throws -> ClientOperation {
        if let blocked = jobRequestUnavailable() { throw FieldRecorderError.notAllowed(blocked) }
        guard let contractID else { throw FieldRecorderError.invalid(JobRequestText.chooseContract) }
        guard let machineID else { throw FieldRecorderError.invalid(JobRequestText.chooseMachine) }
        if let plannedEnd, plannedEnd < plannedStart { throw FieldRecorderError.invalid(JobRequestText.endBeforeStart) }
        let trimmed = note?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if trimmed.count > JobRequestText.noteLimit { throw FieldRecorderError.invalid(JobRequestText.noteTooLong) }
        let existing = try store.outbox.operations(tenantID: tenantID, owner: owner?.subject,
                                                   statuses: Set(ClientOperationStatus.allCases))
        if existing.contains(where: { $0.opType == OperationType.jobRequest.rawValue && $0.entityID == clientID }) {
            throw FieldRecorderError.notAllowed(JobRequestText.alreadySaved)
        }
        let payload = JobRequestPayload(clientID: clientID, contractID: contractID, machineID: machineID, jobSiteID: jobSiteID,
                                        plannedStart: plannedStart, plannedEnd: plannedEnd,
                                        note: trimmed.isEmpty ? nil : trimmed)
        return try enqueue(.jobRequest, entityType: "job", entityID: clientID, payload: payload, dependsOn: [],
                           createdAt: date)
    }
}

extension FieldDirectory {
    /// This user's job requests, oldest first.
    func requestOperations() throws -> [ClientOperation] {
        try store.outbox.operations(tenantID: tenantID, owner: owner?.subject, statuses: Set(ClientOperationStatus.allCases))
            .filter { $0.opType == OperationType.jobRequest.rawValue }
    }

    /// Requests to list on their own: not on the phone as a job yet; an accepted one only for
    /// ``JobRequestText/showAcceptedDays`` (its job arrives with sync).
    func pendingRequests(_ requests: [ClientOperation], serverIDs: Set<UUID>) -> [ClientOperation] {
        let now = clock.wallNow
        return requests.filter { op in
            !serverIDs.contains(op.entityID)
                && (op.status != .acked || now.timeIntervalSince(op.createdAtDevice) <= JobRequestText.showAcceptedDays * 86400)
        }
    }

    /// A request the server has not delivered as a job yet, shown as a job from its payload and the cached lookups.
    func localRequestJob(_ op: ClientOperation) -> FieldJob? {
        guard let payload = try? JSONValue.parse(op.payloadJSON),
              let contractID = payload["contract_id"]?.stringValue.flatMap(UUID.init(uuidString:)),
              let machineID = payload["machine_id"]?.stringValue.flatMap(UUID.init(uuidString:)) else { return nil }
        let result = op.serverResultJSON.flatMap { try? JSONValue.parse($0) }
        let number = JobRequestResult.jobNumber(result)
        let siteID = payload["job_site_id"]?.stringValue.flatMap(UUID.init(uuidString:))
        var fields: [String: JSONValue] = [
            "id": .string(op.entityID.uuidString.lowercased()), "contract_id": .string(contractID.uuidString.lowercased()),
            "job_number": .string(number ?? JobRequestText.unnumbered), "machine_id": .string(machineID.uuidString.lowercased()),
            "status": .string(JobStatus.pendingApproval.rawValue), "version": .number(0),
            "planned_start": payload["planned_start"] ?? .string(AssetaJSON.formatInstant(op.createdAtDevice)),
        ]
        if let siteID { fields["job_site_id"] = .string(siteID.uuidString.lowercased()) }
        if let end = payload["planned_end"], end != .null { fields["planned_end"] = end }
        if let note = payload["note"], note != .null { fields["request_note"] = note }
        guard let job = try? JSONValue.object(fields).decode(as: JobDTO.self) else { return nil }
        let lookup = cachedFieldContracts()?.items.first { $0.id == contractID }
        let site: JobSiteDTO? = siteID.flatMap { id in
            (try? store.syncState.entity(type: "site", id: id, tenantID: tenantID))
                .flatMap { try? AssetaJSON.decoder().decode(JobSiteDTO.self, from: Data($0.json.utf8)) }
                ?? (lookup?.jobSiteID == id ? lookup?.siteName.flatMap { Self.site(id: id, name: $0) } : nil)
        }
        let customer = lookup.flatMap { c in c.customerName.flatMap { Self.customer(id: c.customerID ?? c.id, name: $0) } }
        let machine = (try? store.syncState.entity(type: "machine", id: machineID, tenantID: tenantID))
            .flatMap { try? AssetaJSON.decoder().decode(MachineDTO.self, from: Data($0.json.utf8)) }
            ?? cachedFieldMachines()?.items.first { $0.id == machineID }
        let contract = lookup.flatMap { c in c.customerID.flatMap { ContractDTO.make(id: c.id, customerID: $0, number: c.contractNumber) } }
        return FieldJob(job: job, machine: machine, site: site, customer: customer, contract: contract,
                        request: JobRequestState.of(operation: op.status))
    }

    static func site(id: UUID, name: String) -> JobSiteDTO? {
        try? JSONValue.object(["id": .string(id.uuidString.lowercased()), "code": .string(""), "name": .string(name)])
            .decode(as: JobSiteDTO.self)
    }

    static func customer(id: UUID, name: String) -> CustomerDTO? {
        try? JSONValue.object(["id": .string(id.uuidString.lowercased()), "code": .string(""), "name": .string(name)])
            .decode(as: CustomerDTO.self)
    }

    // MARK: - Lookups for the request form (saved by ``SupervisorOnline``; synced data as the fallback)

    public func cachedFieldContracts() -> FieldLookupCache<FieldContractDTO>? { FieldLookupCache.read(store, tenantID, SyncKey.fieldContracts) }
    public func cachedFieldMachines() -> FieldLookupCache<MachineDTO>? { FieldLookupCache.read(store, tenantID, SyncKey.fieldMachines) }

    /// Contracts a job may be requested for: the saved `/tenant/field/contracts`, else the contracts of synced jobs.
    public func requestContracts() -> [FieldContractDTO] {
        if let saved = cachedFieldContracts() { return saved.items }
        let contracts = ((try? store.syncState.entities(type: "contract", tenantID: tenantID)) ?? [])
            .compactMap { try? AssetaJSON.decoder().decode(ContractDTO.self, from: Data($0.json.utf8)) }
        return contracts.map { contract in
            let customer = (try? store.syncState.entity(type: "customer", id: contract.customerID, tenantID: tenantID))
                .flatMap { try? AssetaJSON.decoder().decode(CustomerDTO.self, from: Data($0.json.utf8)) }
            return FieldContractDTO(id: contract.id, contractNumber: contract.contractNumber, customerID: contract.customerID,
                                    customerName: customer?.name, jobSiteID: nil, siteName: nil, currency: nil)
        }
        .sorted { ($0.customerName ?? "", $0.contractNumber) < ($1.customerName ?? "", $1.contractNumber) }
    }

    /// Machines a job may be requested for: the saved `/tenant/field/machines` plus synced machines.
    public func requestMachines() -> [MachineDTO] {
        var byID: [UUID: MachineDTO] = [:]
        for machine in (try? machines()) ?? [] { byID[machine.id] = machine }
        for machine in cachedFieldMachines()?.items ?? [] { byID[machine.id] = machine }
        return byID.values.sorted { $0.assetCode < $1.assetCode }
    }

    /// Sites offered for the request: synced sites (the contract's own site is the default).
    public func requestSites() -> [JobSiteDTO] {
        ((try? store.syncState.entities(type: "site", tenantID: tenantID)) ?? [])
            .compactMap { try? AssetaJSON.decoder().decode(JobSiteDTO.self, from: Data($0.json.utf8)) }
            .sorted { $0.name < $1.name }
    }
}

extension ContractDTO {
    static func make(id: UUID, customerID: UUID, number: String) -> ContractDTO? {
        try? JSONValue.object(["id": .string(id.uuidString.lowercased()), "customer_id": .string(customerID.uuidString.lowercased()),
                               "contract_number": .string(number)]).decode(as: ContractDTO.self)
    }
}

/// Reading the server's answer to a `JOB_REQUEST` (the created job: id, job_number, status).
enum JobRequestResult {
    static func jobNumber(_ result: JSONValue?) -> String? {
        guard let result else { return nil }
        let body = result["result"] ?? result
        return body["entity"]?["job_number"]?.stringValue ?? body["job"]?["job_number"]?.stringValue
            ?? body["job_number"]?.stringValue
    }
}

/// A saved online lookup list (encrypted in `sync_kv`, cleared with the tenant's state on account switch).
public struct FieldLookupCache<Item: Codable & Sendable>: Codable, Sendable {
    public let items: [Item]
    public let fetchedAt: Date

    enum CodingKeys: String, CodingKey { case items, fetchedAt = "fetched_at" }

    static func read(_ store: LocalStore, _ tenantID: UUID, _ key: String) -> FieldLookupCache? {
        guard let text = try? store.syncState.value(key, tenant: tenantID.uuidString.lowercased()) else { return nil }
        return try? AssetaJSON.decoder().decode(FieldLookupCache.self, from: Data(text.utf8))
    }

    static func write(_ items: [Item], at date: Date, _ store: LocalStore, _ tenantID: UUID, _ key: String) throws {
        let data = try AssetaJSON.encoder().encode(FieldLookupCache(items: items, fetchedAt: date))
        try store.syncState.setValue(String(decoding: data, as: UTF8.self), for: key, tenant: tenantID.uuidString.lowercased())
    }
}

extension SupervisorOnline {
    /// Refreshes the request form's lookups (`/tenant/field/contracts`, `/tenant/field/machines`) and saves them for
    /// offline use. Returns false when either could not be fetched (the saved lists stay).
    @discardableResult
    public func refreshRequestLookups() async -> Bool {
        var ok = true
        do {
            let contracts = try await client.send(APIRequest<[FieldContractDTO]>.get("\(Self.tenant)/field/contracts"))
            try FieldLookupCache.write(contracts, at: now(), store, tenantID, SyncKey.fieldContracts)
        } catch { ok = false }
        do {
            let machines = try await client.send(APIRequest<[MachineDTO]>.get("\(Self.tenant)/field/machines"))
            try FieldLookupCache.write(machines, at: now(), store, tenantID, SyncKey.fieldMachines)
        } catch { ok = false }
        return ok
    }
}
