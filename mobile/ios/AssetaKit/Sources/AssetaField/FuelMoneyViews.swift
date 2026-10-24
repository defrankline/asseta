#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaStore
import AssetaSync
import SwiftUI

/// Fuel tab: my fuel events by type (purchase, issue, usage), newest first; "+" opens the fuel form.
struct FuelTabView: View {
    let model: FieldModel
    @State private var segment: FuelSegment = .issue

    var body: some View {
        let events = model.inbox.fuel.filter { $0.eventType == segment.rawValue }
        List {
            FilterChips(options: FuelSegment.allCases.map { ($0, $0.label) }, selection: $segment)
            if events.isEmpty {
                ContentUnavailableView("No fuel \(segment.label.lowercased()) events", systemImage: "fuelpump",
                                       description: Text("Fuel events you record appear here. Tap + to record one."))
            }
            Section {
                ForEach(events) { f in
                    NavigationLink(value: FieldRoute.fuel(f.id)) {
                        let machine = f.machineID.flatMap { model.inbox.machines[$0]?.assetCode }
                        let job = f.jobID.flatMap { model.inbox.jobs[$0]?.jobNumber }
                        let detail = [job, f.supplier].compactMap { $0 }.joined(separator: " · ")
                        InboxRow([InboxTexts.litres(f.litres), machine].compactMap { $0 }.joined(separator: " · "), f.status,
                                 detail.isEmpty ? nil : detail, f.at.listText)
                    }
                }
            }
        }
        .refreshable { await model.sync(force: true) }
    }
}

/// One fuel event with its linked expense and sync state.
struct FuelDetailView: View {
    let model: FieldModel
    let id: UUID

    var body: some View {
        if let f = model.inbox.fuel.first(where: { $0.id == id }) {
            let machine = f.machineID.flatMap { model.inbox.machines[$0] }
            List {
                Section {
                    LabeledContent("Status") { StatusPill(status: f.status) }
                    LabeledContent("Type", value: InboxTexts.fuelType(f.eventType))
                    LabeledContent("Litres", value: InboxTexts.litres(f.litres))
                    if let price = f.unitPrice { LabeledContent("Price per litre", value: InboxTexts.money(price, f.currency)) }
                    if let cost = f.attributedCost { LabeledContent("Cost", value: InboxTexts.money(cost, f.currency)) }
                    LabeledContent("When", value: f.at.listText)
                }
                Section("Charge to") {
                    LabeledContent("Machine", value: machine.map { InboxTexts.machine($0.assetCode, $0.name) } ?? "None")
                    LabeledContent("Job", value: f.jobID.flatMap { model.inbox.jobs[$0]?.jobNumber } ?? "None")
                    if let meter = f.meterReading { LabeledContent("Meter reading", value: meter) }
                    if let supplier = f.supplier { LabeledContent("Supplier", value: supplier) }
                }
                if let note = f.note { Section("Note") { Text(note).font(.subheadline) } }
                if let expenseID = f.expenseID {
                    Section("Linked expense") {
                        if let expense = model.inbox.expenses.first(where: { $0.serverID == expenseID }) {
                            NavigationLink(value: FieldRoute.expense(expense.id)) {
                                InboxRow(expense.description.isEmpty ? "Expense" : expense.description, expense.status,
                                         InboxTexts.money(expense.amount, expense.currency))
                            }
                        } else {
                            Text("Recorded by the office.").font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                }
                SyncSection(operation: f.op)
                if let machine {
                    Section {
                        NavigationLink(value: FieldRoute.machine(machine.id)) {
                            Label("Machine \(machine.assetCode)", systemImage: "gauge.with.dots.needle.33percent")
                        }
                    }
                }
            }
            .navigationTitle("Fuel event")
        } else {
            ContentUnavailableView("Fuel event not available", systemImage: "questionmark.folder",
                                   description: Text("It is no longer on this phone."))
        }
    }
}

/// Money tab: my cash custody (synced balance apart from unsynced records), today's reconciliation
/// (from the office when online, else the figures saved the last time this phone was online, else a
/// clearly labelled estimate), then my expenses, cash collections and handovers with the office's
/// decisions. "+" opens the existing forms.
struct MoneyTabView: View {
    let model: FieldModel
    /// Opens the answer to a transfer (`false`) or a float (`true`) waiting for me.
    var acknowledge: (UUID, Bool) -> Void = { _, _ in }
    @State private var segment: MoneySegment = .expenses
    /// The last fetch per currency; nil when it failed (the saved figures are used then).
    @State private var reconciliation: [String: CashReconciliationDayDTO]?
    @State private var saved: CashTodaySnapshot?

    var body: some View {
        let summary = model.cashSummary()
        List {
            if let summary, !summary.lines.isEmpty {
                ForEach(summary.lines) { line in
                    CustodyLineSection(line: line, base: summary.baseCurrency)
                    TodaySection(line: line, today: CashToday.select(live: reconciliation, snapshot: saved, currency: line.currency,
                                                                     today: CashToday.localDay(Date())))
                }
            } else {
                ContentUnavailableView("No cash balance yet", systemImage: "banknote",
                                       description: Text("Your cash custody appears here after a sync."))
            }
            CashToAcknowledgeSection(model: model, open: acknowledge)
            FilterChips(options: MoneySegment.allCases.filter { $0 != .transfers || model.access.transferCash }.map { ($0, $0.label) },
                        selection: $segment)
            switch segment {
            case .expenses:
                if model.inbox.expenses.isEmpty {
                    ContentUnavailableView("No expenses", systemImage: "doc.text",
                                           description: Text("Expenses you record appear here with the office's decision."))
                }
                ForEach(InboxTexts.moneyGroups(model.inbox.expenses) { $0.status }, id: \.title) { group in
                    Section(group.title) {
                        ForEach(group.items) { e in
                            NavigationLink(value: FieldRoute.expense(e.id)) {
                                InboxRow(e.description.isEmpty ? "Expense" : e.description, e.status,
                                         InboxTexts.money(e.amount, e.currency) + " · " + InboxTexts.paidFrom(e.paidFrom),
                                         e.at.listText, e.decisionNote.map { "Office note: \($0)" })
                            }
                        }
                    }
                }
            case .collections:
                cashList(model.inbox.collections, empty: ("No cash collections",
                                                          "Cash you collect from customers appears here with the office's verification."))
            case .handovers:
                cashList(model.inbox.handovers, empty: ("No cash handovers",
                                                        "Cash you hand over to the office appears here with its verification."))
            case .transfers:
                TransfersSegment(model: model)
            }
        }
        .refreshable { await model.sync(force: true); await model.refreshAccountability(); await loadReconciliation(summary) }
        .task(id: model.isSyncing) {
            if !model.isSyncing {
                await model.refreshAccountability()
                await loadReconciliation(summary)
            }
        }
    }

    @ViewBuilder private func cashList(_ items: [CashItem], empty: (String, String)) -> some View {
        if items.isEmpty {
            ContentUnavailableView(empty.0, systemImage: "banknote", description: Text(empty.1))
        }
        ForEach(InboxTexts.moneyGroups(items) { $0.status }, id: \.title) { group in
            Section(group.title) {
                ForEach(group.items) { c in
                    NavigationLink(value: FieldRoute.cash(c.id, collection: c.isCollection)) {
                        let detail = [c.reference, c.note].compactMap { $0 }.joined(separator: " · ")
                        InboxRow(InboxTexts.money(c.amount, c.currency), c.status, detail.isEmpty ? nil : detail, c.at.listText,
                                 c.decisionNote.map { "Office note: \($0)" })
                    }
                }
            }
        }
    }

    private func loadReconciliation(_ summary: CashSummary?) async {
        let currencies = summary?.lines.map(\.currency).filter { !$0.isEmpty } ?? []
        defer { saved = model.online?.cachedCashToday() }
        guard let rows = await model.online?.todayReconciliation(currencies: currencies) else {
            reconciliation = nil
            return
        }
        reconciliation = Dictionary(rows.compactMap { r in r.days.last.map { (r.currency, $0) } }, uniquingKeysWith: { a, _ in a })
    }
}

/// Today's figures: the office's reconciliation when online, else the figures saved when this phone was
/// last online (with what it recorded since), else the offline estimate (clearly labelled).
struct TodaySection: View {
    let line: CashLine
    let today: CashToday

    var body: some View {
        let c = line.currency
        switch today {
        case let .live(day), let .savedToday(day, _):
            Section {
                LabeledContent("Opening balance", value: InboxTexts.money(day.opening, c))
                LabeledContent("Floats issued", value: InboxTexts.money(day.floatsIssued, c))
                LabeledContent("Collections", value: InboxTexts.money(day.collections, c))
                LabeledContent("Approved spending", value: InboxTexts.money(day.approvedSpending, c))
                LabeledContent("Verified handovers", value: InboxTexts.money(day.verifiedHandovers, c))
                LabeledContent("Outstanding") { Text(InboxTexts.money(day.outstanding, c)).font(.title3.monospacedDigit().bold()) }
                if nonZero(day.claimedUnverifiedHandovers) {
                    LabeledContent("Handed over, awaiting verification", value: InboxTexts.money(day.claimedUnverifiedHandovers, c))
                }
                if nonZero(day.unverifiedCollections) {
                    LabeledContent("Collections awaiting verification", value: InboxTexts.money(day.unverifiedCollections, c))
                }
                if nonZero(day.pendingSpending) {
                    LabeledContent("Expenses awaiting approval", value: InboxTexts.money(day.pendingSpending, c))
                }
            } header: { Text(today.header()) } footer: { Text(today.footer) }
            if case .savedToday = today, line.hasUnsyncedCash {
                Section {
                    unsyncedRow("Collections", "+", line.pendingCollections)
                    unsyncedRow("Handovers", "−", line.pendingHandovers)
                    unsyncedRow("Cash expenses", "−", line.pendingCashExpenses)
                    estimated
                } header: { Text(CashToday.unsyncedHeader) }
            }
        case let .savedEarlier(day, _):
            Section {
                LabeledContent("Outstanding") { Text(InboxTexts.money(day.outstanding, c)).font(.title3.monospacedDigit().bold()) }
                estimated
            } header: { Text(today.header()) } footer: { Text(today.footer) }
        case .estimate:
            Section { estimated } header: { Text(today.header()) } footer: { Text(today.footer) }
        }
    }

    private var estimated: some View {
        LabeledContent("Estimated cash in hand") {
            Text(MyCashView.money(line.estimatedInHand, line.currency)).foregroundStyle(Palette.warning).monospacedDigit()
        }
    }

    @ViewBuilder private func unsyncedRow(_ title: String, _ sign: String, _ amount: Decimal) -> some View {
        if amount != 0 {
            LabeledContent(title) { Text(sign + MyCashView.money(amount, line.currency)).monospacedDigit() }
        }
    }

    private func nonZero(_ text: String) -> Bool { (Decimal(string: text, locale: Locale(identifier: "en_US_POSIX")) ?? 0) != 0 }
}

/// One expense: amount, paid from, category, job/machine, receipts, the office's decision and sync state.
struct ExpenseDetailView: View {
    let model: FieldModel
    let id: UUID
    let recordExpense: () -> Void

    var body: some View {
        if let e = model.inbox.expenses.first(where: { $0.id == id || $0.serverID == id }) {
            let category = e.categoryID.flatMap { cid in model.expenseCategories.first { $0.id == cid }?.name }
            let files = e.op.map { model.evidenceFiles(of: $0) } ?? []
            let online = model.online
            List {
                Section {
                    LabeledContent("Status") { StatusPill(status: e.status) }
                    LabeledContent("Amount", value: InboxTexts.money(e.amount, e.currency))
                    LabeledContent("Paid from", value: InboxTexts.paidFrom(e.paidFrom))
                    if let category { LabeledContent("Category", value: category) }
                    LabeledContent("Description", value: e.description)
                    if let supplier = e.supplier { LabeledContent("Supplier", value: supplier) }
                    LabeledContent("When", value: e.at.listText)
                    if let job = e.jobID.flatMap({ model.inbox.jobs[$0] }) { LabeledContent("Job", value: job.jobNumber) }
                    if let machine = e.machineID.flatMap({ model.inbox.machines[$0] }) {
                        LabeledContent("Machine", value: InboxTexts.machine(machine.assetCode, machine.name))
                    }
                }
                if e.status == .approved || e.status == .rejected {
                    Section("Office decision") {
                        LabeledContent("Decision") { Text(e.status.label).foregroundStyle(e.status.tone.color) }
                        if let decided = e.decidedAt { LabeledContent("Decided", value: decided.listText) }
                        Text(e.decisionNote ?? "No note.").font(.subheadline)
                    }
                }
                if !e.receiptAttachmentIDs.isEmpty || e.op != nil {
                    Section("Receipts") {
                        if let serverID = e.serverID, !e.receiptAttachmentIDs.isEmpty {
                            ForEach(Array(e.receiptAttachmentIDs.enumerated()), id: \.offset) { index, attachment in
                                EvidenceImage(description: "Receipt \(index + 1)", local: nil,
                                              remote: { await online?.receiptURL(expenseID: serverID, attachmentID: attachment) })
                            }
                        } else if files.isEmpty {
                            Text("No receipt photo.").font(.footnote).foregroundStyle(.secondary)
                        } else {
                            ForEach(Array(files.enumerated()), id: \.offset) { index, file in
                                EvidenceImage(description: "Receipt \(index + 1)", local: { model.localEvidence(file) }, remote: nil)
                            }
                        }
                    }
                }
                SyncSection(operation: e.op)
                if e.status == .rejected && model.canRecordExpenses {
                    Section {
                        Button("Record a new expense", systemImage: "doc.text.viewfinder", action: recordExpense)
                    } footer: { Text("A rejected expense stays rejected. Record a new one if the office asked you to correct it.") }
                }
                let fuel = e.serverID.map { sid in model.inbox.fuel.filter { $0.expenseID == sid } } ?? []
                if !fuel.isEmpty {
                    Section("Fuel") {
                        ForEach(fuel) { f in
                            NavigationLink(value: FieldRoute.fuel(f.id)) {
                                Text("Fuel \(InboxTexts.fuelType(f.eventType).lowercased()) · \(InboxTexts.litres(f.litres))")
                            }
                        }
                    }
                }
            }
            .navigationTitle("Expense")
        } else {
            ContentUnavailableView("Expense not available", systemImage: "questionmark.folder",
                                   description: Text("It is no longer on this phone."))
        }
    }
}

/// One cash collection or handover: amount, reference, the office's verification and sync state.
struct CashDetailView: View {
    let model: FieldModel
    let id: UUID
    let collection: Bool
    let record: (FieldSheet) -> Void

    var body: some View {
        let items = collection ? model.inbox.collections : model.inbox.handovers
        if let c = items.first(where: { $0.id == id }) {
            List {
                Section {
                    LabeledContent("Status") { StatusPill(status: c.status) }
                    LabeledContent("Amount", value: InboxTexts.money(c.amount, c.currency))
                    if collection {
                        LabeledContent("Customer", value: c.customerID.flatMap { cid in model.customers.first { $0.id == cid }?.name }
                                       ?? "Customer")
                    }
                    if let reference = c.reference { LabeledContent("Reference", value: reference) }
                    LabeledContent(collection ? "Received" : "Handed over", value: c.at.listText)
                    if c.allocations > 0 { LabeledContent("Allocated to invoices", value: "\(c.allocations)") }
                }
                if let note = c.note { Section("Note") { Text(note).font(.subheadline) } }
                if c.status == .verified || c.status == .rejected {
                    Section("Office decision") {
                        LabeledContent("Decision") { Text(c.status.label).foregroundStyle(c.status.tone.color) }
                        if let verified = c.verifiedAt { LabeledContent("Decided", value: verified.listText) }
                        Text(c.decisionNote ?? "No note.").font(.subheadline)
                    }
                }
                SyncSection(operation: c.op)
                if c.status == .rejected && model.canRecordCash {
                    Section {
                        if collection {
                            Button("Record cash collection", systemImage: "banknote") { record(.collection) }
                        } else {
                            Button("Hand over cash again", systemImage: "arrow.up.forward.circle") { record(.handover) }
                        }
                    }
                }
            }
            .navigationTitle(collection ? "Cash collection" : "Cash handover")
        } else {
            ContentUnavailableView(collection ? "Collection not available" : "Handover not available",
                                   systemImage: "questionmark.folder", description: Text("It is no longer on this phone."))
        }
    }
}

/// Inbox tab: what needs my attention (rejected expenses, flagged readings, rejected cash, refused sync
/// items) and the office's notifications (fetched online, kept on the phone for offline reading).
struct InboxTabView: View {
    let model: FieldModel
    let open: (NotificationDTO) -> Void
    let attention: (AttentionItem) -> Void

    var body: some View {
        let items = model.inbox.attention
        let notifications = model.notifications
        List {
            if items.isEmpty && notifications.isEmpty {
                ContentUnavailableView("All caught up", systemImage: "tray",
                                       description: Text("Decisions from the office and items that need your attention appear here."))
            }
            if !items.isEmpty {
                Section("Needs attention") {
                    ForEach(items) { item in
                        Button { attention(item) } label: {
                            InboxRow(InboxTexts.attentionTitle(item.kind), item.status, InboxTexts.attentionDetail(item.status),
                                     item.at.listText)
                        }
                        .foregroundStyle(.primary)
                    }
                }
            }
            if !notifications.isEmpty {
                Section {
                    ForEach(notifications) { n in
                        Button { open(n) } label: { NotificationRow(notification: n) }.foregroundStyle(.primary)
                    }
                    if model.unreadNotifications > 0 {
                        Button("Mark all as read") { Task { await model.markAllRead() } }
                    }
                } header: { Text("Notifications") } footer: {
                    if model.notificationsOffline { Text(InboxTexts.notificationsOffline) }
                }
            } else if model.notificationsOffline {
                Text(InboxTexts.notificationsOffline).font(.footnote).foregroundStyle(.secondary)
            }
        }
        .refreshable {
            await model.sync(force: true)
            await model.refreshNotifications()
        }
    }
}

struct NotificationRow: View {
    let notification: NotificationDTO

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Circle().fill(notification.isUnread ? Color.accentColor : .clear).frame(width: 8, height: 8).padding(.top, 7)
            VStack(alignment: .leading, spacing: 2) {
                Text(notification.title).font(.headline).lineLimit(2)
                if let detail = InboxTexts.notificationDetail(title: notification.title, body: notification.body) {
                    Text(detail).font(.subheadline).foregroundStyle(.secondary).lineLimit(3)
                }
                Text(notification.createdAt.listText).font(.caption).foregroundStyle(.secondary)
            }
        }
    }
}

/// A notification that points to nothing on the phone: its full text.
struct NotificationDetailView: View {
    let notification: NotificationDTO?

    var body: some View {
        if let n = notification {
            List {
                Section {
                    Text(n.title).font(.headline)
                    Text(n.body).font(.subheadline)
                    LabeledContent("Received", value: n.createdAt.listText)
                }
            }
            .navigationTitle("Notification")
        } else {
            ContentUnavailableView("Notification not available", systemImage: "questionmark.folder",
                                   description: Text("It is no longer on this phone."))
        }
    }
}
#endif
