import Foundation

/// On-screen wording of the ADR-008 Supervisor app (approved designs: Main, SideNav, SellHours, Money, MachineReading,
/// Reconcile, ReviewSubmit, Dashboard). Same text as Android.
public enum MachineReportTexts {
    // Home
    public static func greeting(_ name: String, hour: Int) -> String {
        let part = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening"
        let first = name.split(separator: " ").first.map(String.init) ?? name
        return first.isEmpty ? part : "\(part), \(first)"
    }
    public static let cashInHand = "Cash in hand"
    public static let hoursToReport = "Hours to report"
    public static func machinesCount(_ n: Int) -> String { n == 1 ? "1 machine" : "\(n) machines" }
    public static let awaitingApproval = "Awaiting approval"
    public static let whatToDo = "WHAT DO YOU WANT TO DO?"
    public static let tileSellHours = "Sell hours"
    public static let tileSellHoursSub = "Customer buys machine hours"
    public static let tileReport = "Machine report"
    public static let tileReportSub = "Reading → account for hours"
    public static func dueBadge(_ n: Int) -> String { "\(n) due" }
    public static let tileMoney = "Money"
    public static let tileMoneySub = "Collections, hand over, expenses"
    public static let tileDashboard = "Dashboard"
    public static let tileDashboardSub = "Reports, my machines"
    public static let recent = "RECENT"
    public static let recentEmpty = "Your sales and machine reports appear here."
    public static let allSynced = "All synced"
    public static func notSynced(_ n: Int) -> String { "\(n) not synced" }
    public static let syncing = "Syncing…"
    public static func recentReport(_ code: String, _ hours: String) -> String { "\(code) report · \(hours) h" }
    public static func recentOpening(_ code: String) -> String { "\(code) opening reading" }
    public static func recentSale(_ hours: String, _ customer: String) -> String { "Sold \(hours) h · \(customer)" }
    public static let pillPaid = "Paid"
    public static let pillPartPaid = "Part paid"
    public static let pillCredit = "On credit"
    public static let pillSent = "Sent"
    public static let pillApproved = "Approved"

    // Side menu
    public static let menuHome = "Home"
    public static let menuInbox = "Inbox"
    public static let menuCustomers = "Customers"
    public static func menuSync(_ time: String) -> String { "Sync · all sent \(time)" }
    public static func menuSyncWaiting(_ n: Int) -> String { "Sync · \(n) waiting" }
    public static let menuSwitchCompany = "Switch company"
    public static let menuSignOut = "Sign out"
    public static let menuSettings = "Settings"
    public static let menuFuel = "Fuel"
    public static let menuReadings = "Readings"
    public static func menuFooter(_ app: String) -> String { "\(app) · Delete my account in Settings" }
    public static let roleSupervisor = "Supervisor"

    // Status pills
    public static let pillOpening = "First reading needed"
    public static let pillDue = "Report due"
    public static let pillAwaiting = "Awaiting approval"
    public static let pillNotSent = "Not sent yet"
    public static let pillRejected = "Rejected · redo"
    /// A machine whose last report was rejected (field.report.state.rejected).
    public static let stateRejected = "Rejected · redo the split"
    public static let pillUpToDate = "Up to date"

    // Step 1: reading
    public static let title = "Machine report"
    public static func step(_ n: Int, _ name: String) -> String { "Step \(n) of 3 · \(name)" }
    public static let stepReading = "New reading"
    public static let stepSplit = "Account for hours"
    public static let stepReview = "Review & submit"
    public static let machine = "Machine"
    public static let chooseMachine = "Choose a machine"
    public static let noMachines = "No machines are assigned to you. The office assigns machines to supervisors."
    public static let lastReading = "Last reading"
    public static let sourceApproved = "approved"
    public static let readingPhoto = "Reading the meter on this phone…"
    public static let readingsAndReset = "Readings and meter reset"
    public static let takePhoto = "Take a photo of the meter"
    public static let retakePhoto = "Retake photo"
    public static let newReading = "New reading (check the number)"
    public static let hoursToAccount = "Hours to account for"
    public static func next(_ hours: String) -> String { "Next: account for \(hours) h" }
    public static let nextPlain = "Next"
    public static let nothingFooter = "No difference since the last reading? Nothing to report."
    public static let openingTitle = "First reading for this machine"
    public static let openingBody = "This machine has no starting reading yet. Record the meter now; the next report counts the hours from it."
    public static let submitOpening = "Submit the reading"
    /// "Rejected: {reason}. Split the same reading again." (no reason: "Rejected. Split the same reading again.").
    public static func rejected(_ reason: String?) -> String {
        let r = reason?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return "Rejected" + (r.isEmpty ? "" : ": \(reason ?? "")") + ". Split the same reading again."
    }
    public static func rejectedReason(_ reason: String) -> String { "Reason: \(reason)" }

    // Step 2: account for hours
    public static func reconcileTitle(_ code: String, _ from: String, _ to: String) -> String { "\(code) · \(from) → \(to)" }
    public static let accountedFor = "Accounted for"
    public static func ofHours(_ total: String) -> String { "/ \(total) h" }
    public static func stillToAccount(_ hours: String) -> String { "\(hours) h still to account for" }
    public static func overAccounted(_ hours: String) -> String { "\(hours) h more than the meter shows" }
    public static let allAccounted = "All hours accounted for"
    public static let customersHeader = "CUSTOMERS (FROM HOURS THEY BOUGHT)"
    public static let nonProductiveHeader = "NON-PRODUCTIVE (REASON NEEDED)"
    public static func availableAfter(_ available: String, _ after: String) -> String { "Available \(available) h · after this \(after) h" }
    public static let addCustomer = "+ Customer"
    public static let addNonProductive = "+ Non-productive"
    public static func reviewLeft(_ hours: String) -> String { "Review — \(hours) h left to account for" }
    public static let review = "Review"
    public static let reconcileFooter = "A customer can only get hours they have bought and that are usable."
    public static let noCustomersWithHours = "No customer has usable hours on this phone. Sync, or account for the hours as non-productive."
    public static let customer = "Customer"
    public static let reason = "Reason"
    public static let hours = "Hours"
    public static let whatHappened = "What happened (required)"
    public static let removeLine = "Remove"
    public static let lineDone = "Done"

    // Step 3: review & submit
    public static let reviewTitle = "Review & submit"
    public static func readingRange(_ from: String, _ to: String) -> String { "\(from) h → \(to) h" }
    /// "12 Nov, 17:30 → 13 Nov, 08:10 · photo + GPS" (no start: only the end).
    public static func periodLine(_ from: String?, _ to: String) -> String { (from.map { "\($0) → \(to)" } ?? to) + " · photo + GPS" }
    public static func productiveHeader(_ hours: String) -> String { "PRODUCTIVE · \(hours) h" }
    public static func nonProductiveHeaderTotal(_ hours: String) -> String { "NON-PRODUCTIVE · \(hours) h" }
    public static let total = "Total"
    public static func matchesMeter(_ hours: String) -> String { "\(hours) h ✓ matches meter" }
    public static func reviewInfo(_ customerHours: String) -> String {
        "The owner or manager approves this report. Until then the \(customerHours) customer hours are reserved; on approval they come off each customer’s purchased hours."
    }
    public static let approverNote = "Note for the approver (optional)"
    public static let submit = "Submit for approval"
    public static let submitting = "Submitting…"
    public static let queued = "Saved on this phone. It is sent when you are online."

    // Errors
    public static let errReading = "Take the meter reading first."
    public static let errReadingInvalid = "Enter the new reading."
    public static let errReadingLower = "The new reading is below the last reading. Check the number, or ask the office about a meter reset."
    public static let errNothingToReport = "No difference since the last reading? Nothing to report."
    public static let errNoLines = "Add a customer or a non-productive line."
    public static let errTooManyLines = "At most 50 lines per report."
    public static func errLineHours(_ decimals: Int) -> String {
        decimals <= 0 ? "Enter whole hours (more than 0)."
            : "Enter the hours (more than 0, at most \(decimals) decimal\(decimals == 1 ? "" : "s"))."
    }
    public static let errDuplicateCustomer = "Each customer can appear only once."
    public static func errNote(_ reason: String) -> String { "Say what happened for “\(reason)”." }
    public static func errOverCap(_ name: String, _ available: String) -> String { "\(name) has only \(available) h available." }
    public static func leftToAccount(_ diff: Decimal) -> String {
        diff > 0 ? stillToAccount(MachineReportRules.hoursText(diff)) : overAccounted(MachineReportRules.hoursText(-diff))
    }

    // Sell hours (design SellHours)
    public static let saleTitle = "Sell hours"
    public static let saleRegistered = "Registered customer"
    public static let saleWalkIn = "Walk-in"
    public static let saleCustomer = "Customer"
    public static let saleMachine = "Machine"
    public static let saleHours = "Hours"
    public static let saleTotal = "Total"
    public static func saleRate(_ hours: String, _ rate: String) -> String { "\(hours) h × \(rate)\nrate card" }
    public static let salePayment = "PAYMENT"
    public static let saleAddPayment = "+ Add payment"
    public static let saleSave = "Save sale"
    public static let saleFooter = "No job is created. Hours become usable when the money is verified. A credit part creates an invoice automatically; its hours wait for office approval."
    public static let saleMethodCash = "Cash"
    public static let saleMethodBank = "Bank"
    public static let saleMethodMobile = "M-money"
    public static let saleMethodCredit = "Credit"
    public static func saleMethodLabel(_ wire: String) -> String {
        switch wire {
        case "BANK": saleMethodBank
        case "MOBILE_MONEY": saleMethodMobile
        case "CREDIT": saleMethodCredit
        default: saleMethodCash
        }
    }
    public static func saleLineTitle(_ wire: String) -> String {
        switch wire {
        case "BANK": "Bank transfer"
        case "MOBILE_MONEY": "Mobile money"
        case "CREDIT": "On credit"
        default: "Cash received"
        }
    }
    public static let saleReference = "Reference"
    public static let salePhotoAttached = "Photo of the message attached"
    public static let saleCreditNote = "The customer pays later on the credit invoice."
    public static func saleFullyPaid() -> String { "Fully paid · balance 0" }
    public static func saleBalance(_ money: String) -> String { "Balance \(money)" }
    public static let saleNotPaid = "Not paid yet"
    public static let saleErrCreditOff = "Credit sales are not allowed for you."
    public static let saleErrCreditWalkIn = "Walk-in customers cannot buy on credit."
    public static let saleErrCreditTwice = "Only one credit part per sale."
    public static let saleTodoNoCredit = "remove the credit part"
    public static let saleTodoOneCredit = "keep one credit part"

    // Money (design Money)
    public static let moneyToday = "Today"
    public static let moneyWeek = "Week"
    public static let moneyMonth = "Month"
    public static let moneyCashInHand = "CASH IN HAND"
    public static func moneyCashLine(collected: String, handed: String, expenses: String) -> String {
        "Collected \(collected) − handed over \(handed) − expenses \(expenses)"
    }
    public static let moneyByMethod = "COLLECTIONS BY METHOD"
    public static let moneyCash = "Cash"
    public static let moneyBank = "Bank"
    public static let moneyMobile = "Mobile money"
    public static let moneyCredit = "Credit"
    public static let moneyCreditAwaiting = "· awaiting approval"
    public static let moneyTotalSold = "Total sold"
    public static let moneyHandedOver = "Handed over to HQ"
    public static let moneyAwaitingCheck = "Awaiting office check"
    public static let moneyAllChecked = "Checked by the office"
    public static let moneyExpenses = "Expenses"
    public static func moneyReceipts(_ n: Int, pending: Int) -> String {
        "\(n) \(n == 1 ? "receipt" : "receipts")" + (pending > 0 ? " · \(pending) pending" : "")
    }
    public static let moneyHandOver = "Hand over"
    public static let moneyExpense = "Expense"
    public static let moneyPettyCash = "Petty cash"
    public static let moneyRecords = "RECORDS"
    public static let moneyCollect = "Record cash collection"

    // Dashboard (design Dashboard)
    public static let dashHoursSold = "Hours sold"
    public static let dashHoursUsed = "Hours used by customers"
    public static let dashFromBought = "from bought hours"
    public static func dashMachineHours(_ period: String) -> String { "Machine hours \(period)" }
    public static func dashProductive(_ hours: String, _ percent: Int) -> String { "Productive \(hours) h (\(percent)%)" }
    public static func dashNonProductive(_ hours: String) -> String { "Non-productive \(hours) h" }
    public static let dashMyMachines = "MY MACHINES"
    public static let dashList = "List"
    public static let dashMap = "Map"
    public static func dashLastReading(_ reading: String, _ when: String) -> String { "Last reading \(reading) h · \(when)" }
    public static let dashNoReading = "No reading yet"
    public static let dashReports = "REPORTS"
    public static let dashCustomerBalances = "Customer balances"
    public static let dashMyReports = "My machine reports"
    public static let dashMySales = "My sales"
    public static let dashMyCash = "My cash"
    public static let dashPeriodToday = "today"
    public static let dashPeriodWeek = "this week"
    public static let dashPeriodMonth = "this month"
    public static let dashNoReports = "No machine reports in this period."
    public static let dashNoSales = "No sales recorded on this phone in this period."

    // Credit invoice payment
    public static let payTitle = "Record payment"
    public static let payInvoice = "Invoice"
    public static let payAmount = "Amount received"
    public static let paySave = "Save payment"
    public static func payBalance(_ money: String) -> String { "Balance \(money)" }
    public static let payErrAmount = "Enter the amount received."
    public static let payErrOverBalance = "The amount is more than the invoice balance."
    public static let payErrPaid = "Nothing is left to pay on this invoice."
    public static let payFooter = "Cash goes into your cash in hand. Bank and mobile money wait for the office to verify them."
    public static let creditInvoices = "CREDIT INVOICES"
    public static func invoiceLine(_ amount: String, _ paid: String, _ due: String?) -> String {
        [amount, "paid \(paid)", due.map { "due \($0)" }].compactMap { $0 }.joined(separator: " · ")
    }
    public static let statusUnpaid = "Unpaid"
    public static let statusPartPaid = "Part paid"
    public static let statusPaid = "Paid"
    public static let statusOverdue = "Overdue"
    public static func invoiceStatus(_ status: String, overdue: Bool) -> String {
        if overdue { return statusOverdue }
        switch status {
        case "PART_PAID": return statusPartPaid
        case "PAID": return statusPaid
        case "CANCELLED": return "Cancelled"
        default: return statusUnpaid
        }
    }
}
