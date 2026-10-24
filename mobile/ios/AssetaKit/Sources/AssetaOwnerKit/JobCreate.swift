import AssetaModel
import AssetaNetwork
import AssetaStore // UUID.lowercased
import Foundation

// The boss creates a job and assigns it to a supervisor, as the web "New job" dialog does
// (web/src/pages/tenant/jobs/jobForm.ts): same endpoints, same job number rule (typed, required, at most 32
// characters, no suggestion), same price rule (rate card = `hourly_rate: null`, resolved by the server at the planned
// start; negotiated = the typed rate) and the same defaults for the terms the phone form does not show
// (standby EXCLUDED, mobilization fee, discount and tax 0). Identical to Android `JobCreate`.

/// `GET /tenant/contracts` row, as the web contract picker shows it ("<number> · <reference>").
public struct OwnerContractDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let customerID: UUID
    public let contractNumber: String
    public let reference: String?
    public let currency: String
    public let jobSiteID: UUID?
    public let status: String

    public init(id: UUID, customerID: UUID, contractNumber: String, reference: String?, currency: String,
                jobSiteID: UUID?, status: String) {
        self.id = id
        self.customerID = customerID
        self.contractNumber = contractNumber
        self.reference = reference
        self.currency = currency
        self.jobSiteID = jobSiteID
        self.status = status
    }

    enum CodingKeys: String, CodingKey {
        case id, reference, currency, status
        case customerID = "customer_id", contractNumber = "contract_number", jobSiteID = "job_site_id"
    }

    public var label: String { reference.map { "\(contractNumber) · \($0)" } ?? contractNumber }
}

/// `GET /tenant/staff?kind=SUPERVISOR` row.
public struct OwnerStaffDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let fullName: String
    public let kind: String
    public let employeeCode: String?
    public let isActive: Bool

    public init(id: UUID, fullName: String, kind: String, employeeCode: String?, isActive: Bool) {
        self.id = id
        self.fullName = fullName
        self.kind = kind
        self.employeeCode = employeeCode
        self.isActive = isActive
    }

    enum CodingKeys: String, CodingKey {
        case id, kind
        case fullName = "full_name", employeeCode = "employee_code", isActive = "is_active"
    }
}

extension OwnerMachineDTO {
    /// "<asset code> · <name>", as the web machine picker.
    public var label: String { "\(assetCode) · \(name)" }
}

extension JobSiteDTO {
    /// "<code> · <name>", as the web job-site picker.
    public var label: String { "\(code) · \(name)" }
}

/// `JobIn` (POST /tenant/jobs). Optional fields are sent as explicit nulls, as the web does.
public struct JobCreateIn: Encodable, Hashable, Sendable {
    public let contractID: UUID
    public let jobNumber: String
    public let machineID: UUID
    public let jobSiteID: UUID?
    public let supervisorID: UUID?
    public let plannedStart: Date
    public let plannedEnd: Date?
    /// nil = the rate card in force at the planned start (resolved by the server).
    public let hourlyRate: DecimalString?
    public let minimumHours: DecimalString?

    enum CodingKeys: String, CodingKey {
        case contractID = "contract_id", jobNumber = "job_number", machineID = "machine_id", jobSiteID = "job_site_id"
        case supervisorID = "supervisor_id", plannedStart = "planned_start", plannedEnd = "planned_end"
        case hourlyRate = "hourly_rate", minimumHours = "minimum_hours", standbyTreatment = "standby_treatment"
        case standbyRate = "standby_rate", mobilizationFee = "mobilization_fee", discountPercent = "discount_percent"
        case taxRatePercent = "tax_rate_percent"
    }

    public func encode(to encoder: any Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(contractID.lowercased, forKey: .contractID)
        try c.encode(jobNumber, forKey: .jobNumber)
        try c.encode(machineID.lowercased, forKey: .machineID)
        try c.encode(jobSiteID?.lowercased, forKey: .jobSiteID)
        try c.encode(supervisorID?.lowercased, forKey: .supervisorID)
        try c.encode(plannedStart, forKey: .plannedStart)
        try c.encode(plannedEnd, forKey: .plannedEnd)
        try c.encode(hourlyRate, forKey: .hourlyRate)
        try c.encode(minimumHours, forKey: .minimumHours)
        // The web form's defaults for the terms the phone does not ask for.
        try c.encode("EXCLUDED", forKey: .standbyTreatment)
        try c.encodeNil(forKey: .standbyRate)
        try c.encode("0", forKey: .mobilizationFee)
        try c.encode("0", forKey: .discountPercent)
        try c.encode("0", forKey: .taxRatePercent)
    }
}

extension OwnerAPI {
    static let lookupPageSize = 20

    /// Contracts by number / reference (the web contract picker: page 1, 20 rows, `q`).
    public static func contractOptions(query: String) -> APIRequest<Page<OwnerContractDTO>> {
        .get("\(tenant)/contracts", query: paging(1, lookupPageSize) + compact([("q", Optional(query).nonEmpty)]))
    }

    /// Machines by asset code / name (the web machine picker).
    public static func machineOptions(query: String) -> APIRequest<Page<OwnerMachineDTO>> {
        .get("\(tenant)/machines", query: paging(1, lookupPageSize) + compact([("q", Optional(query).nonEmpty)]))
    }

    /// Staff of kind SUPERVISOR by name (the web supervisor picker).
    public static func supervisorOptions(query: String) -> APIRequest<Page<OwnerStaffDTO>> {
        .get("\(tenant)/staff", query: paging(1, lookupPageSize) + compact([
            ("q", Optional(query).nonEmpty), ("kind", "SUPERVISOR"),
        ]))
    }

    /// Job sites by code / name (a plain list; the web job-site picker).
    public static func jobSiteOptions(query: String) -> APIRequest<[JobSiteDTO]> {
        .get("\(tenant)/job-sites", query: compact([("q", Optional(query).nonEmpty)]))
    }

    /// Creates the job as DRAFT. The key is kept for the whole form visit, so a retry never creates it twice.
    public static func createJob(_ body: JobCreateIn, idempotencyKey: UUID) throws -> APIRequest<JobDTO> {
        try .mutation(.post, "\(tenant)/jobs", body: body, idempotencyKey: idempotencyKey)
    }

    /// DRAFT → PENDING_APPROVAL (`tenant.job.write`).
    public static func submitJob(_ id: UUID, idempotencyKey: UUID) throws -> APIRequest<JobDTO> {
        try .mutation(.post, "\(tenant)/jobs/\(id.lowercased)/transitions", body: JobTransitionIn(action: "SUBMIT"),
                      idempotencyKey: idempotencyKey)
    }
}

/// Where the hourly price comes from.
public enum JobPriceMode: String, CaseIterable, Sendable {
    case rateCard, negotiated

    public var label: String { self == .rateCard ? JobCreateText.rateCard : JobCreateText.negotiated }
}

/// The phone form's values (the web `JobFormValues` without the terms it does not show).
public struct JobCreateForm: Equatable, Sendable {
    public var contract: OwnerContractDTO?
    public var machine: OwnerMachineDTO?
    public var supervisor: OwnerStaffDTO?
    public var site: JobSiteDTO?
    public var plannedStart: Date
    public var plannedEnd: Date?
    public var jobNumber = ""
    public var priceMode: JobPriceMode = .rateCard
    public var hourlyRate = ""
    public var minimumHours = ""

    /// Planned start defaults to now, as on the web.
    public init(now: Date = Date()) { plannedStart = now }

    public enum Field: String, Sendable, CaseIterable {
        case contract, machine, supervisor, jobNumber, plannedEnd, hourlyRate, minimumHours
    }

    /// The first problem per field, in form order; empty = ready to send.
    public func errors() -> [(Field, String)] {
        var errors: [(Field, String)] = []
        if contract == nil { errors.append((.contract, JobCreateText.chooseContract)) }
        if machine == nil { errors.append((.machine, JobCreateText.chooseMachine)) }
        if supervisor == nil { errors.append((.supervisor, JobCreateText.chooseSupervisor)) }
        let number = jobNumber.trimmingCharacters(in: .whitespacesAndNewlines)
        if number.isEmpty {
            errors.append((.jobNumber, JobCreateText.enterJobNumber))
        } else if number.count > JobCreateText.maxJobNumberLength {
            errors.append((.jobNumber, JobCreateText.jobNumberTooLong))
        }
        if let plannedEnd, plannedEnd <= plannedStart { errors.append((.plannedEnd, JobCreateText.endBeforeStart)) }
        if priceMode == .negotiated && JobApprovalText.parseRate(hourlyRate) == nil {
            errors.append((.hourlyRate, JobCreateText.enterHourlyRate))
        }
        if !minimumHours.trimmingCharacters(in: .whitespaces).isEmpty && JobCreateText.parseHours(minimumHours) == nil {
            errors.append((.minimumHours, JobCreateText.invalidMinimumHours))
        }
        return errors
    }

    public func error(_ field: Field) -> String? { errors().first { $0.0 == field }?.1 }

    public var isValid: Bool { errors().isEmpty }

    /// The create body, or nil while the form has errors.
    public func payload() -> JobCreateIn? {
        guard isValid, let contract, let machine, let supervisor else { return nil }
        return JobCreateIn(
            contractID: contract.id,
            jobNumber: jobNumber.trimmingCharacters(in: .whitespacesAndNewlines),
            machineID: machine.id,
            jobSiteID: site?.id,
            supervisorID: supervisor.id,
            plannedStart: plannedStart,
            plannedEnd: plannedEnd,
            hourlyRate: priceMode == .negotiated ? JobApprovalText.parseRate(hourlyRate).map(DecimalString.init) : nil,
            minimumHours: JobCreateText.parseHours(minimumHours).map(DecimalString.init)
        )
    }
}

/// One request of the create sequence.
public enum JobCreateStep: Equatable, Sendable {
    case create, submit, approve
}

/// Progress of one form visit: once the job exists it is never created again; each step keeps its own
/// Idempotency-Key so a retry after a lost response is replayed by the server.
public struct JobCreateProgress: Equatable, Sendable {
    public private(set) var job: JobDTO?
    public private(set) var createKey = UUID()
    public let submitKey = UUID()
    public let approveKey = UUID()

    public init() {}

    /// The steps still to send: create (unless the job exists), SUBMIT while DRAFT, APPROVE when asked for.
    public func remaining(approveNow: Bool) -> [JobCreateStep] {
        var steps: [JobCreateStep] = []
        switch job?.status {
        case nil: steps = [.create, .submit]
        case .draft?: steps = [.submit]
        default: break
        }
        if approveNow, job?.status != .approved { steps.append(.approve) }
        return steps
    }

    mutating func record(_ job: JobDTO) { self.job = job }

    /// A refused create (not a lost response) created nothing; a corrected retry is a new request.
    mutating func createRefused(_ error: any Error) {
        if case .transport? = error as? APIError { return }
        createKey = UUID()
    }
}

/// How a create attempt ended.
public enum JobCreateOutcome: Equatable, Sendable {
    /// Every step went through; the message is the toast.
    case done(JobDTO, message: String)
    /// Nothing was created; the form stays open with the message.
    case notCreated(message: String)
    /// The job exists (DRAFT or PENDING_APPROVAL) but a later step failed: show the job with the message.
    case partly(JobDTO, message: String)
}

public enum JobCreateFlow {
    /// Creates, submits and (when `approveNow`) approves in sequence, resuming after the last step that went through.
    public static func run(form: JobCreateForm, approveNow: Bool, progress: inout JobCreateProgress,
                           isolation: isolated (any Actor)? = #isolation,
                           send: (APIRequest<JobDTO>) async throws -> JobDTO) async -> JobCreateOutcome {
        for step in progress.remaining(approveNow: approveNow) {
            do {
                switch step {
                case .create:
                    guard let body = form.payload() else {
                        return .notCreated(message: form.errors().first?.1 ?? JobCreateText.chooseContract)
                    }
                    progress.record(try await send(OwnerAPI.createJob(body, idempotencyKey: progress.createKey)))
                case .submit:
                    guard let job = progress.job else { break }
                    progress.record(try await send(OwnerAPI.submitJob(job.id, idempotencyKey: progress.submitKey)))
                case .approve:
                    guard let job = progress.job else { break }
                    progress.record(try await send(OwnerAPI.approveJob(job.id, hourlyRate: nil,
                                                                       idempotencyKey: progress.approveKey)))
                }
            } catch {
                guard let job = progress.job else {
                    progress.createRefused(error)
                    return .notCreated(message: JobCreateText.message(for: error))
                }
                return .partly(job, message: JobCreateText.partly(job, step: step, error: error))
            }
        }
        guard let job = progress.job else { return .notCreated(message: JobCreateText.chooseContract) }
        return .done(job, message: JobCreateText.created(job, supervisor: form.supervisor?.fullName, approved: approveNow))
    }
}

/// Wording of the owner's "New job" form. Identical to Android `JobCreateText`.
public enum JobCreateText {
    public static let action = "New job"
    public static let title = "New job"
    public static let contract = "Customer contract"
    public static let machine = "Machine"
    public static let supervisor = "Supervisor"
    public static let site = "Site (optional)"
    public static let plannedStart = "Planned start"
    public static let plannedEnd = "Planned end (optional)"
    public static let jobNumber = "Job number"
    public static let price = "Price"
    public static let rateCard = "Rate card"
    public static let negotiated = "Negotiated rate"
    public static let minimumHours = "Minimum hours (optional)"
    public static let approveNow = "Approve now"
    public static let sendForApproval = "Send for approval"
    public static let createAndApprove = "Create and approve"
    public static let create = "Create"
    public static let cancel = "Cancel"
    public static let choose = "Choose"
    public static let search = "Search"
    public static let noMatches = "No matches."
    public static let noSite = "None"

    public static let chooseContract = "Choose the customer contract."
    public static let chooseMachine = "Choose the machine."
    public static let chooseSupervisor = "Choose the supervisor."
    public static let enterHourlyRate = "Enter the hourly rate."
    public static let endBeforeStart = "The planned end is before the planned start."
    public static let enterJobNumber = "Enter the job number."
    public static let jobNumberTooLong = "The job number is at most 32 characters."
    public static let invalidMinimumHours = "Enter the minimum hours as a number."

    public static let noRate = "No rate card applies to this machine; choose Negotiated rate and enter a price."
    public static let duplicateJob = "That job number is already used."

    /// The server keeps job numbers of at most 32 characters (as the web form).
    public static let maxJobNumberLength = 32

    /// "Hourly rate (TZS)".
    public static func hourlyRateLabel(currency: String?) -> String { JobApprovalText.hourlyRateLabel(currency: currency) }

    /// The primary button: "Create and approve" when approving now, else "Create".
    public static func submitLabel(approveNow: Bool, canApprove: Bool) -> String {
        approveNow && canApprove ? createAndApprove : create
    }

    /// Minimum hours: a plain decimal ≥ 0 (`8`, `7.5`), else nil.
    public static func parseHours(_ text: String) -> Decimal? {
        let cleaned = text.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: ",", with: "")
        guard let value = DecimalString(string: cleaned)?.value, value >= 0 else { return nil }
        return value
    }

    /// "Job <number> created and assigned to <supervisor>." / "Job <number> created and sent for approval."
    public static func created(_ job: JobDTO, supervisor: String?, approved: Bool) -> String {
        guard approved else { return "Job \(job.jobNumber) created and sent for approval." }
        let name = supervisor?.trimmingCharacters(in: .whitespacesAndNewlines)
        return "Job \(job.jobNumber) created and assigned to \((name?.isEmpty ?? true) ? JobApprovalText.unknownRequester : name!)."
    }

    /// Shown on the job when it was created but SUBMIT or APPROVE failed.
    public static func partly(_ job: JobDTO, step: JobCreateStep, error: any Error) -> String {
        let reason = message(for: error)
        return step == .approve
            ? "Job \(job.jobNumber) was created and sent for approval, but not approved: \(reason)"
            : "Job \(job.jobNumber) was created but not sent for approval: \(reason)"
    }

    /// Same hints as the web job form; anything else as the other owner actions.
    public static func message(for error: any Error) -> String {
        switch (error as? APIError)?.code {
        case "NO_RATE": noRate
        case "DUPLICATE_JOB": duplicateJob
        case "MACHINE_BUSY": "This machine already has an approved or running job; complete or cancel that job first."
        case "CONTRACT_NOT_ACTIVE": "Choose an active contract."
        case "MACHINE_INACTIVE": "The chosen machine is retired; choose an active machine."
        case "SITE_INACTIVE": "The chosen job site is inactive; choose an active site."
        case "STAFF_INACTIVE": "The chosen supervisor is inactive; choose an active staff member."
        default: JobApprovalText.message(for: error)
        }
    }
}
