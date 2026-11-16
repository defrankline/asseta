#if os(iOS)
import AssetaAppShell
import AssetaCapture
import AssetaModel
import AssetaSync
import SwiftUI
import UIKit

private typealias T = MachineReportTexts
private typealias A = FieldAccountabilityTexts

/// Sell hours (design SellHours): registered customer or walk-in, machine, hours, the live total, and payment lines Cash
/// (default) / Bank / M-money / Credit. No job is created; a credit part creates an invoice on the server. Saved on the
/// phone and sent by sync (`HOURS_PURCHASE`).
struct SellHoursView: View {
    let model: FieldModel
    let close: () -> Void
    @State private var clientID = UUID()
    @State private var draft = HoursSaleDraft.newSale()
    @State private var holderID: UUID?
    @State private var photos: [UUID: [(evidence: StoredEvidence, data: Data)]] = [:]
    @State private var cameraFor: UUID?
    @State private var cameraDenied = false
    @State private var error: String?
    @State private var saving = false
    @Environment(\.openURL) private var openURL

    var body: some View {
        let a = model.access
        let price = HoursPricing.price(model.hoursPrices, machineID: draft.machineID, customerID: draft.customerID,
                                       walkIn: draft.walkIn, hoursText: draft.hoursText)
        let credit = a.creditSales && !draft.walkIn
        let valid = { if case .success = AccountabilityRules.hoursSale(draft, walkInAllowed: a.walkIn, noncashAllowed: a.noncashPayments,
                                                                         price: price, creditAllowed: credit) { true } else { false } }()
        VStack(spacing: 0) {
            ShellHeader(T.saleTitle, action: { discardPhotos(); close() })
            if !a.sellHours {
                ShellCard { Text(a.hours == nil ? A.needsRules : A.hoursOff).foregroundStyle(Shell.muted) }.padding(16)
                Spacer()
            } else {
                ScrollView {
                    VStack(spacing: 12) {
                        if a.walkIn {
                            ShellSegments([(false, T.saleRegistered), (true, T.saleWalkIn)], selection: Binding(
                                get: { draft.walkIn },
                                set: { walkIn in
                                    draft.walkIn = walkIn
                                    // A walk-in never buys on credit.
                                    if walkIn { draft.payments = draft.payments.map { var l = $0; if l.method == "CREDIT" { l.method = "CASH" }; return l } }
                                }))
                        }
                        if draft.walkIn {
                            FieldBox(A.hoursWalkInName) {
                                TextField("", text: $draft.walkInName).textContentType(.name).font(.system(size: 16, weight: .semibold))
                            }
                            FieldBox(A.hoursWalkInPhone) {
                                TextField("", text: $draft.walkInPhone).keyboardType(.phonePad).font(.system(size: 16, weight: .semibold))
                            }
                        } else {
                            ShellPicker(label: T.saleCustomer, options: model.customerOptions, selection: $draft.customerID,
                                        emptyMessage: A.hoursCustomerEmpty, identifier: "hours.customer")
                        }
                        HStack(spacing: 12) {
                            ShellPicker(label: T.saleMachine, options: model.machineOptions, selection: $draft.machineID,
                                        identifier: "hours.machine")
                            FieldBox(T.saleHours) {
                                TextField("0", text: $draft.hoursText).keyboardType(.decimalPad)
                                    .font(.system(size: 15, weight: .semibold)).accessibilityIdentifier("hours.hours")
                            }
                            .frame(maxWidth: 130)
                        }
                        totalCard(price)
                        SectionLabel(T.salePayment).padding(.top, 6)
                        ForEach(Array(draft.payments.enumerated()), id: \.element.id) { index, _ in
                            paymentCard(index, methods: a.saleMethods(walkIn: draft.walkIn))
                        }
                        HStack {
                            if draft.payments.count < HoursPayments.max {
                                Button(T.saleAddPayment) { draft.payments.append(HoursPayments.newLine(draft.payments, price: price)) }
                                    .accessibilityIdentifier("hours.addPayment")
                            }
                            Spacer()
                            Text(paidStatus(price)).fontWeight(.semibold).accessibilityIdentifier("hours.paid")
                        }
                        .font(.system(size: 14)).foregroundStyle(Shell.goodText).padding(.horizontal, 4)
                        if let blockers = AccountabilityRules.hoursSaleBlockers(draft, walkInAllowed: a.walkIn,
                                                                                noncashAllowed: a.noncashPayments, price: price,
                                                                                creditAllowed: credit) {
                            Text(blockers).font(.system(size: 13)).foregroundStyle(Shell.badText)
                                .frame(maxWidth: .infinity, alignment: .leading).accessibilityIdentifier("hours.toSave")
                        }
                        if draft.payments.contains(where: { $0.method == "CASH" }) && a.recordForOthers {
                            ShellPicker(label: A.cashHolder, options: model.custodianOptions(),
                                        selection: Binding(get: { holderID ?? model.myStaffID }, set: { holderID = $0 }),
                                        emptyMessage: A.cashTransferCustodiansEmpty, identifier: "hours.holder")
                        }
                    }
                    .padding(.horizontal, 16).padding(.top, 4)
                }
                VStack(spacing: 8) {
                    PrimaryButton(saving ? T.saleSaving : T.saleSave, enabled: valid && !saving, identifier: "hours.save") {
                        save(price: price, credit: credit)
                    }
                    Text(T.saleFooter).font(.system(size: 12)).foregroundStyle(Shell.faint).multilineTextAlignment(.center)
                }
                .padding(.horizontal, 16).padding(.vertical, 12)
            }
        }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .onChange(of: price, initial: true) { _, p in draft.payments = HoursPayments.follow(draft.payments, price: p) }
        .fullScreenCover(item: Binding(get: { cameraFor.map(LineID.init) }, set: { cameraFor = $0?.id })) { line in
            CameraCaptureView { data in
                cameraFor = nil
                if let data { addPhoto(data, line: line.id) }
            }
            .ignoresSafeArea()
        }
        .alert("Camera access needed", isPresented: $cameraDenied) {
            Button("Open Settings") { if let url = URL(string: UIApplication.openSettingsURLString) { openURL(url) } }
            Button("Cancel", role: .cancel) {}
        } message: { Text(A.hoursEvidenceFooter) }
        .alert("Not saved", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
            Button("OK") { error = nil }
        } message: { Text(error ?? "") }
    }

    private struct LineID: Identifiable { let id: UUID }

    /// The total card: "Total", the amount and "20 h × 95,000 · rate card"; nothing until the hours and machine are known.
    @ViewBuilder private func totalCard(_ price: HoursSalePrice) -> some View {
        if price != .hidden { ShellCard(fill: Shell.raised) {
            HStack(alignment: .bottom) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(T.saleTotal).font(.system(size: 13)).foregroundStyle(Shell.muted)
                    switch price {
                    case let .priced(q):
                        Text(HoursPricing.money(q.amount, currency: q.currency, minorUnits: q.minorUnits))
                            .font(.system(size: 26, weight: .bold)).foregroundStyle(Shell.text).accessibilityIdentifier("hours.total")
                    case .unpriced:
                        Text(A.hoursPriceLater).font(.system(size: 15, weight: .semibold)).foregroundStyle(Shell.text)
                    case .hidden:
                        EmptyView()
                    }
                }
                Spacer()
                if case let .priced(q) = price {
                    Text(T.saleRate(HoursPricing.figure(q.hours), HoursPricing.rate(q.hourlyRate),
                                    discount: q.discountPercent > 0 ? HoursPricing.figure(q.discountPercent) : nil))
                        .font(.system(size: 13)).foregroundStyle(Shell.muted).multilineTextAlignment(.trailing)
                }
            }
        } }
    }

    @ViewBuilder private func paymentCard(_ index: Int, methods: [String]) -> some View {
        let line = draft.payments[index]
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 6) {
                ForEach(methods, id: \.self) { method in
                    let on = line.method == method
                    Button { draft.payments[index].method = method } label: {
                        Text(T.saleMethodLabel(method)).font(.system(size: 13, weight: on ? .semibold : .medium))
                            .frame(maxWidth: .infinity, minHeight: 40)
                            .foregroundStyle(on ? Shell.onAccent : Shell.text)
                            .background(on ? Shell.accent : Color.clear, in: RoundedRectangle(cornerRadius: 10))
                            .overlay(RoundedRectangle(cornerRadius: 10).stroke(on ? Color.clear : Shell.outline))
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("hours.method.\(index).\(method)")
                }
            }
            HStack {
                Text(T.saleLineTitle(line.method)).font(.system(size: 15)).foregroundStyle(Shell.text)
                Spacer()
                TextField("0", text: $draft.payments[index].typedAmount).keyboardType(.decimalPad)
                    .multilineTextAlignment(.trailing).font(.system(size: 16, weight: .bold)).monospacedDigit()
                    .foregroundStyle(Shell.text).frame(maxWidth: 160).accessibilityIdentifier("hours.amount.\(index)")
            }
            if line.method == "BANK" || line.method == "MOBILE_MONEY" {
                TextField(T.saleReference, text: $draft.payments[index].reference)
                    .font(.system(size: 15)).foregroundStyle(Shell.text)
                    .padding(10).background(Shell.raised, in: RoundedRectangle(cornerRadius: 10))
                if AccountabilityRules.referenceMissing(line) {
                    Text(A.hoursReferenceLine).font(.system(size: 12)).foregroundStyle(Shell.badText)
                }
                photoRow(line.id)
            } else if line.method == "CREDIT" {
                Text(T.saleCreditNote).font(.system(size: 13)).foregroundStyle(Shell.muted)
            }
            if draft.payments.count > 1 || line.method != "CASH" {
                Button(A.hoursRemovePayment, role: .destructive) {
                    let removed = draft.payments.remove(at: index)
                    photos.removeValue(forKey: removed.id)?.forEach { model.discardEvidence($0.evidence) }
                }
                .font(.system(size: 13))
            }
        }
        .padding(14)
        .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
    }

    @ViewBuilder private func photoRow(_ lineID: UUID) -> some View {
        let count = photos[lineID]?.count ?? 0
        HStack {
            if count > 0 {
                Text(T.salePhotoAttached + (count > 1 ? " (\(count))" : "")).font(.system(size: 13)).foregroundStyle(Shell.muted)
                Spacer()
                Button("Remove", role: .destructive) {
                    photos.removeValue(forKey: lineID)?.forEach { model.discardEvidence($0.evidence) }
                }
                .font(.system(size: 13))
            } else {
                Button { Task { if await CameraAccess.request() { cameraFor = lineID } else { cameraDenied = true } } } label: {
                    Label(T.salePhoto, systemImage: "camera").font(.system(size: 13))
                }
                Spacer()
            }
        }
    }

    private func paidStatus(_ price: HoursSalePrice) -> String {
        let summary = HoursPayments.summary(draft.payments, price: price)
        switch summary.status {
        case .notPaid: return T.saleNotPaid
        case .fullyPaid: return T.saleFullyPaid()
        case let .partPaid(balance): return T.saleBalance(HoursPricing.rate(balance))
        case .overTotal:
            guard let q = summary.quote else { return "" }
            return A.hoursErrPaymentsExceed(HoursPricing.money(q.amount, currency: q.currency, minorUnits: q.minorUnits))
        case .noTotal: return T.salePaid(HoursPricing.rate(summary.paid))
        }
    }

    private func addPhoto(_ data: Data, line: UUID) {
        do {
            photos[line, default: []].append((try model.storeEvidence(data, fileExtension: "jpg", contentType: "image/jpeg"), data))
        } catch {
            self.error = "The photo could not be saved: \(error)"
        }
    }

    private func discardPhotos() {
        photos.values.joined().forEach { model.discardEvidence($0.evidence) }
        photos = [:]
    }

    private func save(price: HoursSalePrice, credit: Bool) {
        guard !saving else { return }
        saving = true
        // "Saving…" shows while the sale is written (next run loop turn).
        Task { @MainActor in
            await Task.yield()
            store(credit: credit)
            saving = false
        }
    }

    private func store(credit: Bool) {
        let a = model.access
        let holder = holderID.flatMap { a.recordForOthers && $0 != model.myStaffID ? $0 : nil }
        do {
            try model.perform {
                try $0.recordHoursSale(draft, walkInAllowed: a.walkIn, cashHolderID: holder,
                                       evidence: draft.payments.map { line in
                                           line.method == "CREDIT" ? [] : (photos[line.id] ?? []).map(\.evidence)
                                       },
                                       receivedAt: Date(), clientID: clientID, noncashAllowed: a.noncashPayments,
                                       creditAllowed: credit)
            }
            photos = [:]
            close()
        } catch {
            self.error = FieldErrors.describe(error)
        }
    }
}
#endif
