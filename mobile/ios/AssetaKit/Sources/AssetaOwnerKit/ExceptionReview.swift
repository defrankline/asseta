import AssetaModel
import AssetaNetwork
import AssetaStore // UUID.lowercased
import Foundation

/// `ReviewIn`: the outcome of a human review of one meter exception, with a required note (audited).
public struct ExceptionReviewIn: Encodable, Hashable, Sendable {
    public let outcome: String
    public let note: String
}

/// The two review outcomes, worded neutrally as on the web: a review records what was found, not a judgement.
public enum ExceptionReviewOutcome: String, CaseIterable, Sendable, Identifiable {
    case explained = "EXPLAINED", confirmed = "CONFIRMED"

    public var id: String { rawValue }

    public var label: String {
        switch self {
        case .explained: "Explained — a legitimate reason was found"
        case .confirmed: "Discrepancy confirmed — evidence stands as recorded"
        }
    }
}

extension OwnerAPI {
    /// Records the review of an OPEN exception (note 5 to 2000 characters).
    public static func reviewException(_ id: UUID, outcome: ExceptionReviewOutcome, note: String,
                                       idempotencyKey: UUID) throws -> APIRequest<MeterExceptionDTO> {
        try .mutation(.post, "\(tenant)/exceptions/\(id.lowercased)/review",
                      body: ExceptionReviewIn(outcome: outcome.rawValue,
                                              note: note.trimmingCharacters(in: .whitespacesAndNewlines)),
                      idempotencyKey: idempotencyKey)
    }
}

/// Wording and input rules of reviewing exceptions; the dialog mirrors the web `ReviewExceptionDialog`.
/// Identical to Android `ExceptionReviewText`.
public enum ExceptionReviewText {
    public static let sectionTitle = "Exceptions"
    public static let empty = "No open exceptions."
    public static let reviewed = "Exception reviewed."
    public static let review = "Review"
    public static let intro = "Record what the review found. The note is kept in the audit trail together with the original "
        + "evidence, which is never changed."
    public static let outcomeLabel = "Outcome"
    public static let noteLabel = "Review note"
    public static let submit = "Record review"
    public static let chooseOutcome = "Choose an outcome"
    public static let noteRequired = "A review note is required"
    public static let noteTooShort = "At least 5 characters"
    public static let noteTooLong = "At most 2000 characters"
    public static let alreadyReviewed = "Someone else has already reviewed this exception; reload the list."
    public static let notFound = "Exception not found"
    public static let screenTitle = "Meter exception"
    public static let blocksBilling = "Blocks billing until reviewed"
    public static let openJob = "Open job"
    /// At most this many job numbers are looked up for the Approvals section (as Android `MAX_JOB_LOOKUPS`).
    public static let maxJobLookups = 25
    public static let openStatus = "OPEN"
    public static let minNoteLength = 5
    public static let maxNoteLength = 2000

    /// The exception type as words ("Meter decrease"), as the Exceptions list and Android.
    public static func typeLabel(_ type: String) -> String { OwnerFormat.humanize(type) }

    /// "Review · Meter decrease" (the review sheet's title).
    public static func reviewTitle(_ x: MeterExceptionDTO) -> String { "\(review) · \(typeLabel(x.exceptionType))" }

    /// "Meter decrease on J-2026-105"; just the type when the exception has no job (or it is unknown).
    public static func title(_ x: MeterExceptionDTO, jobNumber: String?) -> String {
        guard let jobNumber, !jobNumber.isEmpty else { return typeLabel(x.exceptionType) }
        return "\(typeLabel(x.exceptionType)) on \(jobNumber)"
    }

    /// Why the note is not acceptable yet (as the web form), or nil.
    public static func noteError(_ note: String) -> String? {
        let trimmed = note.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty { return noteRequired }
        if trimmed.count < minNoteLength { return noteTooShort }
        if trimmed.count > maxNoteLength { return noteTooLong }
        return nil
    }

    public static func canReview(outcome: ExceptionReviewOutcome?, note: String) -> Bool {
        outcome != nil && noteError(note) == nil
    }

    /// Codes after which the exception must be reloaded (someone else reviewed it).
    public static func needsReload(_ error: any Error) -> Bool { (error as? APIError)?.code == "ALREADY_REVIEWED" }

    public static func message(for error: any Error) -> String {
        if (error as? APIError)?.code == "ALREADY_REVIEWED" { return alreadyReviewed }
        return DecisionErrorText.message(for: error)
    }
}
