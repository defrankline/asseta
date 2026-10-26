#if os(iOS)
import AssetaAppShell
import AssetaCapture
import AssetaModel
import AssetaNetwork
import AssetaSync
import SwiftUI

private typealias T = FieldAccountabilityTexts

/// A form-blocking notice (feature off for the company, rules never loaded, server too old).
private struct NoticeSection: View {
    let title: String
    let message: String

    var body: some View {
        ContentUnavailableView(title, systemImage: "exclamationmark.triangle", description: Text(message))
    }
}

/// Why a capability-gated entry is unavailable (never synced, or a server without it).
private func unavailableMessage(_ access: FieldAccess) -> String { access.capabilities == nil ? T.needsRules : T.serverTooOld }

/// Purchases with hours left, as picker options ("HP-2026-00012 · 12.5 h left", customer below).
private func purchaseOptions(_ purchases: [HoursPurchaseDTO]) -> [PickerOption] {
    purchases.map {
        PickerOption(id: $0.id, title: T.transferPurchaseOption(number: $0.purchaseNumber,
                                                                hours: AccountabilityRules.plain($0.totals.remaining.value),
                                                                provisional: AccountabilityRules.inUse($0.totals.provisional.value)),
                     subtitle: $0.customerName)
    }
}

// MARK: - Sell customer hours (`HOURS_PURCHASE`, offline)

struct HoursSaleFormView: View {
    let model: FieldModel
    @Environment(\.dismiss) private var dismiss
    @State private var clientID = UUID()
    @State private var draft = HoursSaleDraft()
    @State private var receivedAt = Date()
    @State private var holderID: UUID?
    @State private var photos: [(evidence: StoredEvidence, data: Data)] = []
    @State private var error: String?

    var body: some View {
        let a = model.access
        let check = AccountabilityRules.hoursSale(draft, walkInAllowed: a.walkIn)
        NavigationStack {
            Form {
                if !a.sellHours {
                    NoticeSection(title: T.titleHoursSale, message: a.hours == nil ? T.needsRules : T.hoursOff)
                } else {
                    Section {
                        if a.walkIn {
                            Picker(T.hoursSectionCustomer, selection: $draft.walkIn) {
                                Text(T.hoursRegistered).tag(false)
                                Text(T.hoursWalkIn).tag(true)
                            }.pickerStyle(.segmented)
                        }
                        if draft.walkIn {
                            TextField(T.hoursWalkInName, text: $draft.walkInName).textContentType(.name)
                            TextField(T.hoursWalkInPhone, text: $draft.walkInPhone).keyboardType(.phonePad)
                        } else {
                            SearchablePickerField(label: T.hoursCustomer, options: model.customerOptions, selection: $draft.customerID,
                                                  emptyMessage: T.hoursCustomerEmpty, identifier: "hours.customer")
                        }
                    } header: { Text(T.hoursSectionCustomer) } footer: { if draft.walkIn { Text(T.hoursWalkInFooter) } }
                    Section {
                        SearchablePickerField(label: T.hoursMachine, options: model.machineOptions, selection: $draft.machineID,
                                              identifier: "hours.machine")
                        TextField(T.hoursHours, text: $draft.hoursText).keyboardType(.decimalPad)
                            .font(.title3.monospacedDigit()).accessibilityIdentifier("hours.hours")
                        TextField(T.noteOptional, text: $draft.note, axis: .vertical)
                    } header: { Text(T.hoursSectionHours) } footer: { Text(T.hoursHoursFooter) }
                    Section {
                        Picker(T.hoursSectionPayment, selection: $draft.paidNow) {
                            Text(T.hoursPaidNow).tag(true)
                            Text(T.hoursNotPaid).tag(false)
                        }.pickerStyle(.segmented)
                        if draft.paidNow {
                            Picker(T.hoursSectionPayment, selection: $draft.method) {
                                ForEach(T.paymentMethods, id: \.wire) { Text($0.label).tag($0.wire) }
                            }.pickerStyle(.segmented)
                            TextField(T.hoursAmountReceived, text: $draft.amountText).keyboardType(.decimalPad)
                                .font(.title3.monospacedDigit()).accessibilityIdentifier("hours.amount")
                            if draft.method != "CASH" { TextField(T.hoursReference, text: $draft.reference) }
                            DatePicker(T.hoursReceived, selection: $receivedAt, in: ...Date())
                            if draft.method == "CASH" && a.recordForOthers {
                                SearchablePickerField(label: T.cashHolder, options: model.custodianOptions(),
                                                      selection: Binding(get: { holderID ?? model.myStaffID }, set: { holderID = $0 }),
                                                      emptyMessage: T.cashTransferCustodiansEmpty, identifier: "hours.holder")
                            }
                        }
                    } header: { Text(T.hoursSectionPayment) } footer: {
                        Text(draft.paidNow ? T.hoursPaymentFooter : T.hoursNotPaidFooter)
                    }
                    if draft.paidNow {
                        EvidencePhotosSection(model: model, photos: $photos, error: $error)
                    }
                }
            }
            .navigationTitle(T.titleHoursSale)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { discardPhotos(); dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save", action: save).disabled(!a.sellHours || !check.isValid).accessibilityIdentifier("hours.save")
                }
            }
            .alert("Not saved", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
                Button("OK") { error = nil }
            } message: { Text(error ?? "") }
        }
        .interactiveDismissDisabled()
    }

    private func discardPhotos() {
        photos.forEach { model.discardEvidence($0.evidence) }
        photos = []
    }

    private func save() {
        let a = model.access
        let holder = holderID.flatMap { a.recordForOthers && $0 != model.myStaffID ? $0 : nil }
        do {
            try model.perform {
                try $0.recordHoursSale(draft, walkInAllowed: a.walkIn, cashHolderID: holder,
                                       evidence: draft.paidNow ? photos.map(\.evidence) : [], receivedAt: min(receivedAt, Date()),
                                       clientID: clientID)
            }
            if !draft.paidNow { discardPhotos() }
            photos = [] // now owned by the queued sale
            dismiss()
        } catch {
            self.error = JobDetailView.describe(error)
        }
    }
}

/// Payment evidence photos through the in-app camera (originals stored encrypted at once; at most ten).
struct EvidencePhotosSection: View {
    let model: FieldModel
    @Binding var photos: [(evidence: StoredEvidence, data: Data)]
    @Binding var error: String?
    /// Wording (the hours sale's by default; the hand-over form passes the deposit slip lines).
    var title = T.hoursEvidence
    var footer = T.hoursEvidenceFooter
    var photograph = T.hoursPhotograph
    var addPhoto = T.hoursAddPhoto
    var removeLabel = "Remove"
    @State private var showCamera = false
    @State private var cameraDenied = false
    @Environment(\.openURL) private var openURL

    var body: some View {
        Section {
            ForEach(Array(photos.enumerated()), id: \.offset) { index, photo in
                HStack {
                    if let image = UIImage(data: photo.data) {
                        Image(uiImage: image).resizable().scaledToFit().frame(height: 120)
                            .accessibilityLabel("\(title) \(index + 1)")
                    }
                    Spacer()
                    Button(removeLabel, role: .destructive) { remove(index) }.buttonStyle(.borderless)
                }
            }
            if photos.count < AccountabilityRules.maxEvidence {
                Button(photos.isEmpty ? photograph : addPhoto, systemImage: "camera") {
                    Task { if await CameraAccess.request() { showCamera = true } else { cameraDenied = true } }
                }
            }
        } header: { Text(title) } footer: { Text(footer) }
            .fullScreenCover(isPresented: $showCamera) {
                CameraCaptureView { data in
                    showCamera = false
                    if let data { add(data) }
                }
                .ignoresSafeArea()
            }
            .alert("Camera access needed", isPresented: $cameraDenied) {
                Button("Open Settings") { if let url = URL(string: UIApplication.openSettingsURLString) { openURL(url) } }
                Button("Cancel", role: .cancel) {}
            } message: { Text(footer) }
    }

    private func add(_ data: Data) {
        do {
            photos.append((try model.storeEvidence(data, fileExtension: "jpg", contentType: "image/jpeg"), data))
        } catch {
            self.error = "The photo could not be saved: \(error)"
        }
    }

    private func remove(_ index: Int) {
        model.discardEvidence(photos[index].evidence)
        photos.remove(at: index)
    }
}

// MARK: - Request hours transfer (`HOURS_TRANSFER_REQUEST`, offline)

struct HoursTransferFormView: View {
    let model: FieldModel
    @Environment(\.dismiss) private var dismiss
    @State private var clientID = UUID()
    @State private var purchaseID: UUID?
    @State private var fromMachineID: UUID?
    @State private var toMachineID: UUID?
    @State private var hours = ""
    @State private var reasonCodeID: UUID?
    @State private var reason = ""
    @State private var error: String?

    private var purchases: [HoursPurchaseDTO] {
        (model.accountabilityData?.purchases() ?? []).filter { $0.totals.remaining.value > 0 }
    }

    private var purchase: HoursPurchaseDTO? { purchases.first { $0.id == purchaseID } }
    private var remaining: Decimal? { purchase?.remaining(on: fromMachineID) }

    var body: some View {
        let a = model.access
        let required = a.hours?.reasonCodeRequired == true
        let check = AccountabilityRules.hoursTransfer(purchaseID: purchaseID, fromMachineID: fromMachineID, toMachineID: toMachineID,
                                                      hoursText: hours, remaining: remaining, reason: reason,
                                                      reasonCodeID: reasonCodeID, reasonCodeRequired: required)
        NavigationStack {
            Form {
                if !a.requestHoursTransfer {
                    NoticeSection(title: T.titleHoursTransfer, message: a.hours == nil ? T.needsRules : T.hoursOff)
                } else {
                    Section {
                        if purchases.isEmpty { Text(T.transferPurchasesEmpty).foregroundStyle(.secondary) }
                        SearchablePickerField(label: T.transferPurchase, options: purchaseOptions(purchases),
                                              selection: Binding(get: { purchaseID }, set: { selectPurchase($0) }),
                                              emptyMessage: T.transferPurchasesEmpty, identifier: "transfer.purchase")
                        if let purchase {
                            let holding = Self.holding(purchase)
                            SearchablePickerField(label: T.transferFromMachine,
                                                  options: model.machineOptions.filter { holding.contains($0.id) },
                                                  selection: $fromMachineID, identifier: "transfer.from")
                                .disabled(holding.count <= 1)
                            if let inUse = AccountabilityRules.inUse(purchase.provisional(on: fromMachineID)) {
                                Text(T.hoursInUse(inUse)).font(.footnote).foregroundStyle(.secondary)
                            }
                        }
                        SearchablePickerField(label: T.transferToMachine,
                                              options: model.machineOptions.filter { $0.id != fromMachineID },
                                              selection: $toMachineID, identifier: "transfer.to")
                        TextField(T.transferHours, text: $hours).keyboardType(.decimalPad).font(.title3.monospacedDigit())
                    } footer: {
                        Text(a.hours?.transferRequiresApproval != false ? T.transferFooterApproval : T.transferFooterDirect)
                    }
                    Section(T.reason) {
                        let reasons = (model.accountabilityData?.transferReasons ?? [])
                            .map { PickerOption(id: $0.id, title: $0.label, subtitle: $0.code) }
                        if !reasons.isEmpty || required {
                            SearchablePickerField(label: required ? T.reasonCategory : T.reasonCategoryOptional, options: reasons,
                                                  selection: $reasonCodeID, noneTitle: required ? nil : T.noCategory,
                                                  identifier: "transfer.category")
                        }
                        TextField(T.reason, text: $reason, axis: .vertical)
                    }
                    if case let .failure(problems) = check {
                        let shown = problems.messages.filter { $0.hasPrefix("Only") || $0.hasPrefix("Choose a different") }
                        if !shown.isEmpty {
                            Section { ForEach(shown, id: \.self) { Text($0).foregroundStyle(Palette.warning) } }
                        }
                    }
                }
            }
            .navigationTitle(T.titleHoursTransfer)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save", action: save).disabled(!a.requestHoursTransfer || !check.isValid)
                }
            }
            .alert("Not saved", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
                Button("OK") { error = nil }
            } message: { Text(error ?? "") }
        }
    }

    /// Machines holding hours of the purchase (its own machine when none is listed).
    static func holding(_ p: HoursPurchaseDTO) -> [UUID] {
        let withHours = (p.machines ?? []).filter { $0.remaining.value > 0 }.map(\.machineID)
        return withHours.isEmpty ? [p.machineID] : withHours
    }

    /// The purchase's own machine when hours are left on it, else the first machine holding hours.
    static func defaultFrom(_ p: HoursPurchaseDTO) -> UUID {
        let withHours = holding(p)
        return withHours.contains(p.machineID) ? p.machineID : withHours.first ?? p.machineID
    }

    private func selectPurchase(_ id: UUID?) {
        purchaseID = id
        fromMachineID = purchases.first { $0.id == id }.map(Self.defaultFrom)
    }

    private func save() {
        let required = model.access.hours?.reasonCodeRequired == true
        do {
            try model.perform {
                try $0.requestHoursTransfer(purchaseID: purchaseID, fromMachineID: fromMachineID, toMachineID: toMachineID,
                                            hoursText: hours, remaining: remaining, reason: reason, reasonCodeID: reasonCodeID,
                                            reasonCodeRequired: required, clientID: clientID)
            }
            dismiss()
        } catch {
            self.error = JobDetailView.describe(error)
        }
    }
}

// MARK: - Transfer cash (`CASH_TRANSFER`, offline)

struct CashTransferFormView: View {
    let model: FieldModel
    @Environment(\.dismiss) private var dismiss
    @State private var clientID = UUID()
    @State private var fromID: UUID?
    @State private var toID: UUID?
    @State private var amount = ""
    @State private var currency = ""
    @State private var received = ""
    @State private var note = ""
    @State private var transferredAt = Date()
    @State private var error: String?

    var body: some View {
        let a = model.access
        let me = model.myStaffID
        let from = fromID ?? me
        let receiverIsMe = toID != nil && toID == me
        let selfAckPolicy = a.cash?.recorderReceiverCountsAsAck == true
        let selfAck = receiverIsMe && selfAckPolicy
        let check = AccountabilityRules.cashTransfer(fromID: from, toID: toID, amountText: amount, currency: currency,
                                                     receiverIsMe: receiverIsMe, selfAck: selfAckPolicy, receivedText: received,
                                                     note: note)
        let options = model.custodianOptions()
        NavigationStack {
            Form {
                if !a.transferCash {
                    NoticeSection(title: T.titleCashTransfer, message: unavailableMessage(a))
                } else {
                    Section {
                        SearchablePickerField(label: T.cashTransferFrom, options: options,
                                              selection: Binding(get: { from }, set: { fromID = $0 }),
                                              emptyMessage: T.cashTransferCustodiansEmpty, identifier: "cashTransfer.from")
                            .disabled(!a.recordForOthers)
                        SearchablePickerField(label: T.cashTransferTo, options: options.filter { $0.id != from }, selection: $toID,
                                              emptyMessage: T.cashTransferCustodiansEmpty, identifier: "cashTransfer.to")
                        TextField(T.cashTransferAmount, text: $amount).keyboardType(.decimalPad).font(.title3.monospacedDigit())
                        TextField(T.currency, text: Binding(get: { currency }, set: { currency = String($0.uppercased().prefix(3)) }))
                            .textInputAutocapitalization(.characters).autocorrectionDisabled()
                        if selfAck {
                            TextField(T.cashTransferAmountReceived, text: $received).keyboardType(.decimalPad)
                        }
                        DatePicker(T.cashTransferWhen, selection: $transferredAt, in: ...Date())
                        TextField(T.noteOptional, text: $note, axis: .vertical)
                    } footer: {
                        Text(selfAck ? T.cashTransferFooterSelf
                             : a.cash?.transferAckRequired == false ? T.cashTransferFooterNoAck : T.cashTransferFooterAck)
                    }
                }
            }
            .navigationTitle(T.titleCashTransfer)
            .navigationBarTitleDisplayMode(.inline)
            .onAppear { if currency.isEmpty { currency = model.baseCurrency ?? "" } }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save", action: save).disabled(!a.transferCash || !check.isValid)
                }
            }
            .alert("Not saved", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
                Button("OK") { error = nil }
            } message: { Text(error ?? "") }
        }
    }

    private func save() {
        let me = model.myStaffID
        let selfAck = model.access.cash?.recorderReceiverCountsAsAck == true
        do {
            try model.perform {
                try $0.recordCashTransfer(fromStaffID: fromID, toStaffID: toID, myStaffID: me, amountText: amount, currency: currency,
                                          selfAck: selfAck, receivedText: received, note: note,
                                          transferredAt: min(transferredAt, Date()), clientID: clientID)
            }
            dismiss()
        } catch {
            self.error = JobDetailView.describe(error)
        }
    }
}

// MARK: - Acknowledge a transfer or a float (offline)

struct CashAckFormView: View {
    let model: FieldModel
    let targetID: UUID
    let isFloat: Bool
    @Environment(\.dismiss) private var dismiss
    @State private var received: String?
    @State private var note = ""
    @State private var error: String?

    var body: some View {
        let a = model.access
        let pending = model.accountabilityData?.toAcknowledge(myStaffID: model.myStaffID)
        let transfer = isFloat ? nil : (pending?.transfers.first { $0.id == targetID })
        let float = isFloat ? pending?.floats.first { $0.id == targetID } : nil
        let declared = transfer?.amountDeclared ?? float?.amount
        let currency = transfer?.currency ?? float?.currency ?? ""
        let waiting = (try? model.recorder?.alreadySaved(isFloat ? .cashFloatAcknowledgement : .cashTransferAcknowledgement,
                                                         clientID: targetID)) ?? false
        let title = isFloat ? T.titleAcknowledgeFloat : T.titleAcknowledgeTransfer
        NavigationStack {
            Form {
                if waiting {
                    Section { Text(T.ackWaiting).foregroundStyle(Palette.warning) }
                } else if let declared {
                    if !a.acknowledgeCash {
                        NoticeSection(title: title, message: unavailableMessage(a))
                    } else {
                        Section {
                            Text(float != nil ? T.ackFloatFromOffice : T.ackTransferFrom(model.custodianName(transfer?.fromStaffID, server: transfer?.fromStaffName)))
                                .font(.headline)
                            LabeledContent(T.ackDeclared, value: InboxTexts.money(declared.description, currency))
                            LabeledContent(float != nil ? T.ackIssued : T.ackSent,
                                           value: (transfer?.transferredAt ?? float?.occurredAt ?? Date()).listText)
                            if let text = transfer?.note ?? float?.note, !text.isEmpty { Text(text).foregroundStyle(.secondary) }
                        }
                        Section {
                            TextField(T.ackAmountReceived, text: Binding(get: { received ?? declared.description }, set: { received = $0 }))
                                .keyboardType(.decimalPad).font(.title3.monospacedDigit())
                            TextField(T.noteOptional, text: $note, axis: .vertical)
                        } footer: { Text(T.ackFooter) }
                        Section {
                            Button(T.ackAcknowledge) { answer(true, declared: declared.description) }
                                .buttonStyle(.borderedProminent).tint(Palette.live)
                            Button(T.ackDispute, role: .destructive) { answer(false, declared: declared.description) }
                                .disabled(note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                            if note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                                Text(T.ackDisputeReason).font(.footnote).foregroundStyle(.secondary)
                            }
                        }
                    }
                } else {
                    ContentUnavailableView(title, systemImage: "banknote", description: Text(T.ackNotFound))
                }
            }
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
            .alert("Not saved", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
                Button("OK") { error = nil }
            } message: { Text(error ?? "") }
        }
    }

    private func answer(_ acknowledge: Bool, declared: String) {
        do {
            try model.perform {
                try $0.acknowledgeCash(targetID: targetID, isFloat: isFloat, acknowledge: acknowledge,
                                       receivedText: received ?? declared, note: note)
            }
            dismiss()
        } catch {
            self.error = JobDetailView.describe(error)
        }
    }
}

// MARK: - Ask to keep cash (`CASH_RETENTION_REQUEST` offline when the server takes it, else online)

struct RetentionFormView: View {
    let model: FieldModel
    /// Opens the status screen of the request just saved (client id).
    var viewStatus: (UUID) -> Void = { _ in }
    @Environment(\.dismiss) private var dismiss
    /// One per form visit: the request's idempotency key (a replay returns the same request).
    @State private var clientID = UUID()
    @State private var holderID: UUID?
    @State private var amount = ""
    @State private var currency = ""
    @State private var reasonID: UUID?
    @State private var reason = ""
    @State private var sending = false
    @State private var sent: String?
    @State private var savedID: UUID?
    @State private var messages: [String] = []

    var body: some View {
        let a = model.access
        let check = AccountabilityRules.retention(amountText: amount, currency: currency, reason: reason)
        NavigationStack {
            Form {
                if !a.askToKeepCash {
                    NoticeSection(title: T.titleRetention, message: a.cash == nil ? T.needsRules : T.retentionOff)
                } else {
                    Section {
                        if a.recordForOthers {
                            SearchablePickerField(label: T.cashHolder, options: model.custodianOptions(),
                                                  selection: Binding(get: { holderID ?? model.myStaffID }, set: { holderID = $0 }),
                                                  emptyMessage: T.cashTransferCustodiansEmpty, identifier: "retention.holder")
                        }
                        TextField(T.retentionAmount, text: $amount).keyboardType(.decimalPad).font(.title3.monospacedDigit())
                        TextField(T.currency, text: Binding(get: { currency }, set: { currency = String($0.uppercased().prefix(3)) }))
                            .textInputAutocapitalization(.characters).autocorrectionDisabled()
                    } footer: { Text(T.retentionFooter) }
                    Section(T.reason) {
                        let reasons = (model.accountabilityData?.retentionReasons ?? [])
                            .map { PickerOption(id: $0.id, title: $0.label, subtitle: $0.description) }
                        if !reasons.isEmpty {
                            SearchablePickerField(label: T.reasonCategoryOptional, options: reasons, selection: $reasonID,
                                                  noneTitle: T.noCategory, identifier: "retention.category")
                        }
                        TextField(T.reason, text: $reason, axis: .vertical)
                    }
                    if let sent {
                        Section {
                            Text(sent).foregroundStyle(Brand.amber)
                            if let savedID {
                                Button(T.retentionViewStatus) {
                                    dismiss()
                                    viewStatus(savedID)
                                }
                                .accessibilityIdentifier("retention.viewStatus")
                            }
                        }
                    } else {
                        Section {
                            ForEach(messages, id: \.self) { Text($0).foregroundStyle(Palette.offline) }
                            if !a.retentionOffline { Text(T.onlineOnly).font(.footnote).foregroundStyle(.secondary) }
                        }
                    }
                }
            }
            .disabled(sending)
            .navigationTitle(T.titleRetention)
            .navigationBarTitleDisplayMode(.inline)
            .onAppear { if currency.isEmpty { currency = model.baseCurrency ?? "" } }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button(sent == nil ? "Cancel" : "Done") { dismiss() } }
                if sent == nil {
                    ToolbarItem(placement: .confirmationAction) {
                        Button(T.send) { Task { await send() } }
                            .disabled(!a.askToKeepCash || !check.isValid || sending || (!a.retentionOffline && !model.isOnline))
                    }
                }
            }
        }
    }

    private func send() async {
        let holder = holderID.flatMap { model.access.recordForOthers && $0 != model.myStaffID ? $0 : nil }
        if model.access.retentionOffline {
            // Queued in the outbox: works offline, sent with the next sync.
            do {
                try model.perform {
                    try $0.requestRetention(amountText: amount, currency: currency, reason: reason, reasonID: reasonID,
                                            staffMemberID: holder, validUntil: nil, clientID: clientID)
                }
                sent = T.retentionSaved
                savedID = clientID
                messages = []
            } catch {
                messages = [JobDetailView.describe(error)]
            }
            return
        }
        guard let online = model.online else { return }
        sending = true
        defer { sending = false }
        do {
            let created = try await online.requestRetention(amountText: amount, currency: currency, reason: reason,
                                                            reasonID: reasonID, staffMemberID: holder, validUntil: nil)
            sent = T.retentionSent
            savedID = created.id
            messages = []
            model.refresh()
        } catch {
            messages = [AccountabilityErrors.message(error)]
        }
    }
}

/// "Requests to keep cash" (Money → Transfers): this phone's retention requests, newest first.
struct RetentionsSection: View {
    let model: FieldModel

    var body: some View {
        let _ = model.accountabilityTick
        let items = model.accountabilityData?.myRetentions() ?? []
        if !items.isEmpty {
            Section(T.moneyRetentions) {
                ForEach(items) { item in
                    NavigationLink(value: FieldRoute.retention(item.id)) {
                        VStack(alignment: .leading, spacing: 3) {
                            HStack {
                                Text(InboxTexts.money(AccountabilityRules.plain(item.amount), item.currency ?? "")).font(.subheadline)
                                Spacer()
                                RetentionStatusView.pill(item)
                            }
                            Text(item.reason).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                            Text(item.at.listText).font(.caption).foregroundStyle(.secondary)
                        }
                        .accessibilityElement(children: .combine)
                    }
                }
            }
        }
    }
}

/// "Request to keep cash": one request's status (the server's, read online by id; the sync state until it has it).
struct RetentionStatusView: View {
    let model: FieldModel
    /// Client id (queued here) or server id (from a notification).
    let id: UUID
    @State private var loading = false
    @State private var fetchFailed = false

    private var item: RetentionItem? { model.accountabilityData?.myRetentions().first { $0.matches(id) } }

    var body: some View {
        let _ = model.accountabilityTick
        List {
            if let item {
                Section {
                    LabeledContent(T.amount, value: InboxTexts.money(AccountabilityRules.plain(item.amount), item.currency ?? ""))
                    LabeledContent(T.retentionStatus) { Self.pill(item) }
                    LabeledContent(T.retentionRequested, value: item.at.listText)
                    if let until = item.validUntil { LabeledContent(T.retentionValidUntil, value: until.listText) }
                    LabeledContent(T.reason, value: item.reason)
                    if let name = item.decidedByName { LabeledContent(T.retentionDecidedBy, value: name) }
                    if let note = item.decisionNote, !note.isEmpty { LabeledContent(T.retentionDecisionNote, value: note) }
                }
                Section {
                    if item.serverID == nil {
                        Text(item.syncStatus == .conflict || item.syncStatus == .failed
                             ? (FieldAccountabilityTexts.conflictText(item.errorCode) ?? T.retentionNotSynced) : T.retentionNotSynced)
                    } else if !model.isOnline || fetchFailed {
                        Text(T.retentionOffline)
                    }
                }
                .font(.footnote).foregroundStyle(.secondary)
            } else if loading {
                ProgressView().frame(maxWidth: .infinity)
            } else {
                ContentUnavailableView(T.titleRetentionStatus, systemImage: "hand.raised",
                                       description: Text(model.isOnline ? T.retentionNotFound : T.retentionOffline))
            }
        }
        .navigationTitle(T.titleRetentionStatus)
        .refreshable { await load() }
        .task { await load() }
    }

    /// Reads the request online by its server id (or by `id` when it is not on the phone: a notification's record).
    private func load() async {
        guard model.isOnline, let online = model.online else { return }
        let known = item
        guard let serverID = known?.serverID ?? (known == nil ? id : nil) else { return }
        loading = true
        defer { loading = false }
        do {
            try await online.refreshRetention(serverID)
            fetchFailed = false
            model.refresh()
        } catch {
            fetchFailed = true
        }
    }

    static func status(_ item: RetentionItem) -> InboxStatus {
        if let sync = item.syncStatus { return InboxStatusRules.local(sync) }
        return switch item.status {
        case "APPROVED": .approved
        case "REJECTED": .rejected
        default: .pendingApproval
        }
    }

    static func statusText(_ item: RetentionItem) -> String? {
        if item.syncStatus != nil { return nil }
        return item.status.map(FieldAccountabilityTexts.retentionStatusText)
    }

    /// The sync state until the server has it, then the server's status in the strings-doc wording.
    static func pill(_ item: RetentionItem) -> some View {
        let status = status(item)
        return Pill(text: statusText(item) ?? status.label, color: status.tone.color)
    }
}

/// Server refusals of the accountability forms, in plain words (neutral wording).
enum AccountabilityErrors {
    static func message(_ error: any Error) -> String {
        if let api = error as? APIError {
            if case .transport = api { return T.onlineOnly }
            return api.localizedDescription
        }
        return JobDetailView.describe(error)
    }
}

// MARK: - Money tab parts

/// "Cash to acknowledge": transfers to me and floats waiting for my answer (newest first).
struct CashToAcknowledgeSection: View {
    let model: FieldModel
    let open: (UUID, Bool) -> Void

    var body: some View {
        let _ = model.accountabilityTick
        if model.access.acknowledgeCash, let pending = model.accountabilityData?.toAcknowledge(myStaffID: model.myStaffID) {
            let rows = pending.transfers.map { (id: $0.id, isFloat: false, title: T.ackTransferFrom(model.custodianName($0.fromStaffID, server: $0.fromStaffName)),
                                                amount: $0.amountDeclared.description, currency: $0.currency, at: $0.transferredAt) }
                + pending.floats.map { (id: $0.id, isFloat: true, title: T.ackFloatFromOffice, amount: $0.amount.description,
                                        currency: $0.currency, at: $0.occurredAt) }
            if !rows.isEmpty {
                Section(T.ackSection) {
                    ForEach(rows.sorted { $0.at > $1.at }, id: \.id) { row in
                        Button { open(row.id, row.isFloat) } label: {
                            InboxRow(row.title, nil, InboxTexts.money(row.amount, row.currency), row.at.listText)
                        }
                        .foregroundStyle(.primary)
                        .accessibilityIdentifier("ack.\(row.id)")
                    }
                }
            }
        }
    }
}

/// The Transfers segment: my transfers as the server has them, and this phone's transfers not yet synced.
struct TransfersSegment: View {
    let model: FieldModel

    var body: some View {
        let _ = model.accountabilityTick
        let rows = Self.rows(model)
        if rows.isEmpty {
            ContentUnavailableView(T.moneyTransfersEmptyTitle, systemImage: "arrow.left.arrow.right",
                                   description: Text(T.moneyTransfersEmptyMessage))
        } else {
            Section {
                ForEach(rows, id: \.key) { r in
                    InboxRow(r.title, r.status, InboxTexts.money(r.amount, r.currency),
                             [r.statusText, r.at.listText].compactMap { $0 }.joined(separator: " · "))
                }
            }
        }
    }

    struct Row { let key: String, title: String, amount: String, currency: String, status: InboxStatus, statusText: String?, at: Date }

    static func rows(_ model: FieldModel) -> [Row] {
        let me = model.myStaffID
        let saved = model.accountabilityData?.transfers.items ?? []
        let server = saved.map { t -> Row in
            let outgoing = t.fromStaffID == me
            let title = outgoing ? T.moneyTransferTo(model.custodianName(t.toStaffID, server: t.toStaffName))
                : T.moneyTransferFrom(model.custodianName(t.fromStaffID, server: t.fromStaffName))
            let (status, text): (InboxStatus, String?) = switch t.status {
            case "ACKNOWLEDGED": (.accepted, T.moneyStatusAcknowledged)
            case "DISPUTED": (.rejected, T.moneyStatusDisputed)
            default: (.pending, T.moneyStatusPendingAck)
            }
            return Row(key: t.id.uuidString, title: title, amount: (t.amountReceived ?? t.amountDeclared).description, currency: t.currency,
                       status: status, statusText: text, at: t.transferredAt)
        }
        let known = Set(saved.compactMap(\.clientID))
        let local = (model.overview?.items.map(\.operation) ?? [])
            .filter { $0.opType == OperationType.cashTransfer.rawValue && !known.contains($0.entityID) }
            .map { op -> Row in
                let p = try? JSONValue.parse(op.payloadJSON)
                let to = p?["to_staff_id"]?.stringValue.flatMap(UUID.init(uuidString:))
                return Row(key: op.id.uuidString, title: T.moneyTransferTo(model.custodianName(to)), amount: p?["amount"]?.stringValue ?? "",
                           currency: p?["currency"]?.stringValue ?? "", status: InboxStatusRules.local(op.status), statusText: nil,
                           at: op.createdAtDevice)
            }
        return (local + server).sorted { $0.at > $1.at }
    }
}

extension Result where Failure == AccountabilityRules.Problems {
    var isValid: Bool { if case .success = self { true } else { false } }
}

/// "Overdue remittance" (follow-up F2): one overdue-remittance flag of mine, read online by id
/// (`GET /cash/remittance-overdue/{id}`). The tap reads it first (``FieldModel/remittanceOverdue(_:)``) and opens the
/// Money tab when it cannot (offline, not mine: 404), as Android.
struct RemittanceOverdueView: View {
    let model: FieldModel
    let id: UUID
    @State private var record: RemittanceOverdueDTO?

    var body: some View {
        List {
            if let o = record ?? model.savedOverdue[id] {
                Section {
                    Text(RemittanceOverduePresentation.name(o)).font(.headline)
                    ForEach(RemittanceOverduePresentation.rows(o, flagged: { $0.listText }), id: \.label) { row in
                        LabeledContent(row.label, value: row.value)
                    }
                } footer: {
                    Text(RemittanceOverduePresentation.footer(o))
                }
            }
        }
        .navigationTitle(T.titleRemittanceOverdue)
        .refreshable { await load() }
        .task { await load() }
    }

    private func load() async {
        if let fresh = await model.remittanceOverdue(id) { record = fresh }
    }
}
#endif
