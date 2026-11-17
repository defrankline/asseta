import AssetaModel
import Foundation

/// What leaving a form (the header's Back, swipe-back; Android: system Back, the bar's Back or Cancel) does.
public enum LeaveAction: Sendable, Equatable {
    /// Nothing entered, or already saved: leave.
    case leave
    /// Work was entered: ask "Discard …?" (Keep editing / Discard) before it is thrown away.
    case ask
    /// A save is under way: stay until it is queued.
    case stay
}

/// Leaving a machine report or a sale with entered data never throws the work away silently (same rules as Android
/// `FormLeave`).
public enum FormLeave {
    public static let reportTitle = "Discard this report?"
    public static let reportBody = "The photo and readings you entered will be lost."
    public static let saleTitle = "Discard this sale?"
    public static let saleBody = "The customer, hours and payments you entered will be lost."
    public static let keepEditing = "Keep editing"
    public static let discard = "Discard"

    public static func decide(saving: Bool, saved: Bool, entered: Bool) -> LeaveAction {
        if saved { return .leave }
        if saving { return .stay }
        return entered ? .ask : .leave
    }

    /// A machine report holds entered data once it has a photo, a typed reading, a note, or lines other than those it
    /// opened with (a correction opens with the rejected report's lines and reading: those are not new input, so pass
    /// an empty `typedReading` for a correction). Lines compare by content, not by their row ids.
    public static func reportEntered(hasPhoto: Bool, typedReading: String, lines: [ReportLineDraft],
                                     startingLines: [ReportLineDraft], note: String) -> Bool {
        hasPhoto || !blank(typedReading) || !blank(note) || lines.map(content) != startingLines.map(content)
    }

    /// A sale holds entered data once a customer, walk-in name or phone, machine, hours, note, payment photo or cash
    /// holder is set, or the payment lines differ from the opening one (one Cash line following the total, nothing
    /// typed).
    public static func saleEntered(_ draft: HoursSaleDraft, photoCount: Int, holderChosen: Bool) -> Bool {
        draft.customerID != nil || !blank(draft.walkInName) || !blank(draft.walkInPhone) || draft.machineID != nil
            || !blank(draft.hoursText) || !blank(draft.note) || photoCount > 0 || holderChosen
            || draft.payments.count != 1
            || draft.payments.contains { $0.method != "CASH" || !$0.followsTotal || !blank($0.reference) }
    }

    private static func blank(_ text: String) -> Bool { text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }

    private static func content(_ line: ReportLineDraft) -> [String] {
        [line.kind.rawValue, line.customerID?.uuidString ?? "", line.reasonID?.uuidString ?? "", line.hoursText, line.note]
    }
}
