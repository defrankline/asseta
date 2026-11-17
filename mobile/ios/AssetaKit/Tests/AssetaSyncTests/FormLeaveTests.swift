@testable import AssetaSync
import Foundation
import Testing

/// Leaving a report or a sale with entered data asks first (same cases as Android `FormLeaveTest`).
struct FormLeaveTests {
    static let pwani = UUID(uuidString: "aaaaaaaa-0000-4000-8000-0000000000a1")!

    static func line(_ hours: String = "120") -> ReportLineDraft {
        ReportLineDraft(kind: .customer, customerID: pwani, customerName: "Pwani Road Contractors", hoursText: hours)
    }

    @Test func backAsksOnlyWhenWorkWasEnteredAndNeverDuringASave() {
        #expect(FormLeave.decide(saving: false, saved: false, entered: false) == .leave)
        #expect(FormLeave.decide(saving: false, saved: false, entered: true) == .ask)
        #expect(FormLeave.decide(saving: true, saved: false, entered: true) == .stay)
        #expect(FormLeave.decide(saving: false, saved: true, entered: true) == .leave)
    }

    @Test func aReportWithAPhotoATypedReadingALineOrANoteHoldsEnteredData() {
        #expect(!FormLeave.reportEntered(hasPhoto: false, typedReading: "", lines: [], startingLines: [], note: ""))
        #expect(FormLeave.reportEntered(hasPhoto: true, typedReading: "", lines: [], startingLines: [], note: ""))
        #expect(FormLeave.reportEntered(hasPhoto: false, typedReading: "1510.5", lines: [], startingLines: [], note: ""))
        #expect(FormLeave.reportEntered(hasPhoto: false, typedReading: "", lines: [Self.line()], startingLines: [], note: ""))
        #expect(FormLeave.reportEntered(hasPhoto: false, typedReading: "", lines: [], startingLines: [], note: "Late start"))
        // A correction opens with the rejected report's lines (new row ids): not new input until they change.
        #expect(!FormLeave.reportEntered(hasPhoto: false, typedReading: "", lines: [Self.line()], startingLines: [Self.line()], note: ""))
        #expect(FormLeave.reportEntered(hasPhoto: false, typedReading: "", lines: [Self.line("100")], startingLines: [Self.line()], note: ""))
    }

    @Test func aSaleHoldsEnteredDataOnceAnythingIsChosenOrTyped() {
        let opening = HoursSaleDraft.newSale()
        #expect(!FormLeave.saleEntered(opening, photoCount: 0, holderChosen: false))
        // The opening Cash line following the total does not count, even with the total's amount filled in.
        var followed = opening
        followed.payments[0].amountText = "950000"
        #expect(!FormLeave.saleEntered(followed, photoCount: 0, holderChosen: false))
        var d = opening; d.customerID = Self.pwani
        #expect(FormLeave.saleEntered(d, photoCount: 0, holderChosen: false))
        d = opening; d.walkIn = true; d.walkInName = "Juma"
        #expect(FormLeave.saleEntered(d, photoCount: 0, holderChosen: false))
        d = opening; d.machineID = UUID()
        #expect(FormLeave.saleEntered(d, photoCount: 0, holderChosen: false))
        d = opening; d.hoursText = "20"
        #expect(FormLeave.saleEntered(d, photoCount: 0, holderChosen: false))
        d = opening; d.payments[0].typedAmount = "5000"
        #expect(FormLeave.saleEntered(d, photoCount: 0, holderChosen: false))
        d = opening; d.payments[0].method = "BANK"
        #expect(FormLeave.saleEntered(d, photoCount: 0, holderChosen: false))
        d = opening; d.payments = []
        #expect(FormLeave.saleEntered(d, photoCount: 0, holderChosen: false))
        #expect(FormLeave.saleEntered(opening, photoCount: 1, holderChosen: false))
        #expect(FormLeave.saleEntered(opening, photoCount: 0, holderChosen: true))
    }

    @Test func theWordingMatchesAndroid() {
        #expect(FormLeave.reportTitle == "Discard this report?")
        #expect(FormLeave.reportBody == "The photo and readings you entered will be lost.")
        #expect(FormLeave.saleTitle == "Discard this sale?")
        #expect(FormLeave.saleBody == "The customer, hours and payments you entered will be lost.")
        #expect(FormLeave.keepEditing == "Keep editing")
        #expect(FormLeave.discard == "Discard")
    }
}
