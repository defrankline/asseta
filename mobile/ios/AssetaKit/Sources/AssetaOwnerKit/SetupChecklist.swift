import AssetaModel
import AssetaNetwork
import Foundation

// Go-live setup checklist in the Owner app (commit 5a0a2e6; strings doc "Go-live checklist", owner.setup.*): the
// Overview banner from the /me figures, the More entry and the checklist screen. Online only: the owner's choices are
// never queued; the last checklist is kept as the usual read-only offline snapshot.

public enum SetupPermission {
    public static let read = "tenant.setup.read"
    public static let manage = "tenant.setup.manage"
}

extension SnapshotKey {
    public static let setupChecklist = SnapshotKey("setup.checklist")
}

extension OwnerAPI {
    static let setup = "\(tenant)/setup-checklist"

    /// `GET /setup-checklist`.
    public static func setupChecklist() -> APIRequest<SetupChecklistDTO> { .get(setup) }

    /// `POST /steps/{key}/not-needed {reason}` (3 to 500 characters; 422 `SETUP_STEP_REQUIRED` for unskippable steps).
    public static func markStepNotNeeded(_ key: SetupStepKey, reason: String,
                                         idempotencyKey: UUID) throws -> APIRequest<SetupChecklistDTO> {
        try .mutation(.post, "\(setup)/steps/\(key.rawValue)/not-needed",
                      body: SetupNotNeededIn(reason: reason.trimmingCharacters(in: .whitespacesAndNewlines)),
                      idempotencyKey: idempotencyKey)
    }

    /// `DELETE /steps/{key}/not-needed`: the step counts again.
    public static func undoStepNotNeeded(_ key: SetupStepKey, idempotencyKey: UUID) throws -> APIRequest<SetupChecklistDTO> {
        try .mutation(.delete, "\(setup)/steps/\(key.rawValue)/not-needed", body: EmptyBody(), idempotencyKey: idempotencyKey)
    }

    /// `POST /confirm-controls {note?}` ("Our default controls are fine").
    public static func confirmControls(note: String?, idempotencyKey: UUID) throws -> APIRequest<SetupChecklistDTO> {
        try .mutation(.post, "\(setup)/confirm-controls", body: SetupConfirmControlsIn(note: note.nonEmpty),
                      idempotencyKey: idempotencyKey)
    }
}

extension OwnerFeatures {
    /// The go-live checklist screen and its More entry (`tenant.setup.read`).
    public var setupRead: Bool { permissions.contains(SetupPermission.read) }
    /// Mark steps not needed / undo / confirm the controls (`tenant.setup.manage`; the mutation gate applies on top).
    public var setupManage: Bool { permissions.contains(SetupPermission.manage) }
}

/// The banner figures: `/me` first, replaced by the checklist's whenever it is loaded or changed in this session.
public struct SetupProgress: Equatable, Sendable {
    public let stepsDone: Int
    public let stepsTotal: Int?
    public let complete: Bool
    public let dismissed: Bool

    public init(stepsDone: Int, stepsTotal: Int?, complete: Bool, dismissed: Bool) {
        self.stepsDone = stepsDone
        self.stepsTotal = stepsTotal
        self.complete = complete
        self.dismissed = dismissed
    }

    public init(_ tenant: TenantMembership) {
        self.init(stepsDone: tenant.setupStepsDone ?? 0, stepsTotal: tenant.setupStepsTotal,
                  complete: tenant.setupComplete ?? false, dismissed: tenant.setupDismissed ?? false)
    }

    public init(_ checklist: SetupChecklistDTO) {
        self.init(stepsDone: checklist.stepsDone, stepsTotal: checklist.stepsTotal, complete: checklist.complete,
                  dismissed: checklist.dismissed)
    }

    /// Shown when the total is known (null = no `tenant.setup.read`), not complete and not dismissed.
    public var showsBanner: Bool { (stepsTotal ?? 0) > 0 && !complete && !dismissed }

    /// `owner.setup.banner`.
    public var bannerText: String? {
        guard showsBanner, let stepsTotal else { return nil }
        return SetupTexts.banner(done: stepsDone, total: stepsTotal)
    }
}

/// What a step action (or a not-done sub-check) opens: an Owner app screen the role may open, else the web page.
public enum SetupTarget: Equatable, Sendable {
    case app(OwnerRoute, label: String)
    case web(path: String)

    public var label: String {
        switch self {
        case let .app(_, label): label
        case .web: SetupTexts.openWeb
        }
    }
}

public enum SetupPresentation {
    /// Link → app screen (path before `?`; anything else → web), when the role may open it (strings doc table).
    public static func target(link: String, features: OwnerFeatures) -> SetupTarget {
        let pieces = link.split(separator: "?", maxSplits: 1, omittingEmptySubsequences: false)
        let path = pieces.first.map(String.init) ?? link
        let hasQuery = pieces.count > 1
        var app: (OwnerRoute, String)?
        switch path {
        case "/tenant/machines" where !hasQuery && features.fleet: app = (.fleet, SetupTexts.screenFleet)
        case "/tenant/jobs" where features.jobs: app = (.jobs, SetupTexts.screenJobs)
        case "/tenant/approvals" where features.approvals, "/tenant/meter-baselines" where features.approvals:
            app = (.approvals, SetupTexts.screenApprovals)
        case "/tenant/hours" where features.hoursRead, "/tenant/hours/purchases" where features.hoursRead:
            app = (.customerHours, SetupTexts.screenCustomerHours)
        case "/tenant/finance/cash" where !hasQuery && features.finance: app = (.cash, SetupTexts.screenCash)
        default: app = nil
        }
        if let app { return .app(app.0, label: SetupTexts.openScreen(app.1)) }
        return .web(path: link)
    }

    /// The step's action: only while it is to do (none once done, not needed or not applicable).
    public static func action(for step: SetupStepDTO, features: OwnerFeatures) -> SetupTarget? {
        guard step.status == .todo else { return nil }
        return target(link: step.link, features: features)
    }

    /// A sub-check's action: only while it is not done (and its step applies).
    public static func action(for check: SetupCheckDTO, of step: SetupStepDTO, features: OwnerFeatures) -> SetupTarget? {
        guard !check.done, step.status != .notApplicable else { return nil }
        return target(link: check.link, features: features)
    }

    /// `owner.setup.needsAccess` is shown under an action when the user lacks the step's permission.
    public static func needsAccess(_ step: SetupStepDTO, features: OwnerFeatures) -> Bool {
        action(for: step, features: features) != nil && !step.requiredPermission.isEmpty
            && !features.permissions.contains(step.requiredPermission)
    }

    /// "Mark as not needed": `can_mark_not_needed` and status TODO.
    public static func canMarkNotNeeded(_ step: SetupStepDTO) -> Bool { step.canMarkNotNeeded && step.status == .todo }

    /// "Undo": status NOT_NEEDED.
    public static func canUndo(_ step: SetupStepDTO) -> Bool { step.status == .notNeeded }

    /// "Our default controls are fine": CONTROLS_CHOSEN while TODO and the controls were not confirmed yet.
    public static func canConfirmControls(_ step: SetupStepDTO, checklist: SetupChecklistDTO) -> Bool {
        step.key == .controlsChosen && step.status == .todo && checklist.controlsConfirmedAt == nil
    }

    /// The reason can be sent: 3 to 500 characters once trimmed.
    public static func isValidReason(_ text: String) -> Bool {
        let n = text.trimmingCharacters(in: .whitespacesAndNewlines).count
        return n >= 3 && n <= 500
    }

    /// The controls note can be sent: optional, at most 500 characters once trimmed.
    public static func isValidNote(_ text: String) -> Bool { text.trimmingCharacters(in: .whitespacesAndNewlines).count <= 500 }

    /// "{title}" line of a step card: `{order}. {title}`.
    public static func title(_ step: SetupStepDTO) -> String { "\(step.order). \(step.title)" }

    /// `owner.setup.count` when the step has a count.
    public static func count(_ step: SetupStepDTO) -> String? {
        guard let total = step.totalCount else { return nil }
        return SetupTexts.count(done: step.doneCount ?? 0, total: total)
    }

    public static func count(_ check: SetupCheckDTO) -> String? {
        guard let total = check.totalCount else { return nil }
        return SetupTexts.count(done: check.doneCount ?? 0, total: total)
    }

    /// `owner.setup.notNeededBy`.
    public static func notNeededNote(_ step: SetupStepDTO, timeZone: TimeZone = .current) -> String? {
        guard step.status == .notNeeded, let mark = step.notNeeded else { return nil }
        return SetupTexts.notNeededBy(name: mark.markedByName.nonEmpty ?? SetupTexts.someone,
                                      date: OversightPresentation.date(mark.markedAt, timeZone: timeZone), reason: mark.reason.nonEmpty)
    }

    /// `owner.setup.controlsBy` on the CONTROLS_CHOSEN step.
    public static func controlsNote(_ step: SetupStepDTO, checklist: SetupChecklistDTO,
                                    timeZone: TimeZone = .current) -> String? {
        guard step.key == .controlsChosen, let at = checklist.controlsConfirmedAt else { return nil }
        return SetupTexts.controlsBy(name: checklist.controlsConfirmedByName.nonEmpty ?? SetupTexts.someone,
                                     date: OversightPresentation.date(at, timeZone: timeZone))
    }

    /// Refusals: `SETUP_STEP_REQUIRED` has its own wording; the rest the standard one.
    public static func errorMessage(_ error: any Error) -> String {
        if (error as? APIError)?.code == "SETUP_STEP_REQUIRED" { return SetupTexts.stepRequired }
        return DecisionErrorText.message(for: error)
    }
}

// MARK: - Wording (strings doc "Go-live checklist", owner.setup.*)

public enum SetupTexts {
    public static func banner(done: Int, total: Int) -> String { "Get ready to go live — \(done) of \(total) done" }
    public static let bannerCaption = "Open the go-live checklist to see what is left."
    public static let more = "Go-live checklist"
    public static let title = "Go-live checklist"
    public static func progress(done: Int, total: Int) -> String { "\(done) of \(total) done" }
    public static let complete = "Everything is ready. You can go live."
    public static func asOf(_ dateTime: String) -> String { "Checked \(dateTime)" }
    public static let footer = "Each step is checked against your company's records and updates by itself as the work is done. Most steps are done on the web."

    /// `owner.setup.status.*` (unknown values humanized).
    public static func status(_ status: SetupStepStatus) -> String {
        switch status {
        case .done: "Done"
        case .todo: "To do"
        case .notNeeded: "Not needed"
        case .notApplicable: "Does not apply"
        default: status.humanized
        }
    }

    public static func count(done: Int, total: Int) -> String { "\(done) of \(total)" }
    public static let checkDone = "Done"
    public static let checkTodo = "To do"
    public static let optional = "Optional"
    public static func openScreen(_ screen: String) -> String { "Open \(screen)" }
    public static let openWeb = "Open on the web"
    public static let needsAccess = "Someone with access to this screen must do this step."
    public static let markNotNeeded = "Mark as not needed"
    public static func notNeededTitle(_ step: String) -> String { "Mark \"\(step)\" as not needed?" }
    public static let notNeededReason = "Why this step does not apply"
    public static let notNeededHint = "At least 3 characters."
    public static func notNeededBy(name: String, date: String, reason: String?) -> String {
        "Marked not needed by \(name) on \(date)" + (reason.map { ": \($0)" } ?? "")
    }
    public static let undo = "Undo"
    public static let controlsFine = "Our default controls are fine"
    public static let controlsTitle = "Keep the default controls?"
    public static let controlsMessage = "Asseta's default controls stay in place. You can change them on the web at any time."
    public static let controlsNote = "Note (optional)"
    public static let controlsConfirm = "Keep the defaults"
    public static func controlsBy(name: String, date: String) -> String { "Controls confirmed by \(name) on \(date)" }
    public static let cancel = "Cancel"
    public static let stepRequired = "This step is needed before going live, so it cannot be marked as not needed."
    public static let someone = "someone"

    // App screen titles used in `owner.setup.openScreen`.
    public static let screenFleet = "Fleet"
    public static let screenJobs = "Jobs"
    public static let screenApprovals = "Approvals"
    public static let screenCustomerHours = CustomerHoursTexts.more
    public static let screenCash = CashText.title
}
