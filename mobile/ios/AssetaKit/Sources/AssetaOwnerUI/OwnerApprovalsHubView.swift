#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

/// Approvals (design OwnerApprovals, Android `ApprovalsScreen`): machine reports, credit sales (approve inline) and
/// expenses under their chips, then every other kind the role may decide inline under All, each in its own titled group.
struct OwnerApprovalsHubView: View {
    let model: OwnerModel
    let queues: ApprovalQueues
    let back: () -> Void
    let push: (AnyHashable) -> Void
    @State private var filter: ApprovalFilter = .all
    @State private var busy: UUID?
    @State private var creditError: (id: UUID, message: String)?
    @State private var message: String?

    var body: some View {
        let counts = queues.counts
        VStack(spacing: 0) {
            ShellHeader(OwnerMenuTexts.approvals, action: back)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) { ForEach(chips, id: \.self) { chip($0, counts.chip($0)) } }
                    .padding(.horizontal, 16)
            }
            .padding(.bottom, 10)
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    if let message {
                        Text(message).font(.system(size: 14)).foregroundStyle(Shell.accent)
                            .accessibilityIdentifier("approvals.message")
                    }
                    if filter.shows(.machineReport) { reportCards }
                    if filter.shows(.credit) {
                        creditCards
                        decisionGroup(.credit)
                    }
                    if filter.shows(.expense) { expenseCards }
                    if filter == .all { otherGroups }
                    if counts.of(filter) == 0 && queues.loaded {
                        EmptyState(title: ApprovalsTexts.emptyTitle, message: ApprovalsTexts.emptyMessage, systemImage: "checkmark.seal")
                    }
                }
                .padding(.horizontal, 16).padding(.bottom, 16)
            }
            .refreshable { await queues.reload(model) }
        }
        .background(Shell.background.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .task(id: model.changeTick) { await queues.reload(model) }
    }

    /// Chips the role sees: All, and each kind it can have waiting.
    private var chips: [ApprovalFilter] {
        let f = model.features
        return [.all] + (f.machineReports ? [.machineReports] : [])
            + (f.creditSales || f.decisionKinds.contains(.credit) ? [.credit] : []) + (f.approvals ? [.expenses] : [])
    }

    private func chip(_ value: ApprovalFilter, _ title: String) -> some View {
        let on = filter == value
        return Button { filter = value } label: {
            Text(title).font(.system(size: 13, weight: on ? .semibold : .regular))
                .foregroundStyle(on ? Shell.onAccent : Shell.text)
                .padding(.horizontal, 12).padding(.vertical, 8)
                .background(on ? Shell.accent : Shell.card, in: Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(on ? .isSelected : [])
    }

    private func kindLine(_ kind: String, _ when: Date) -> some View {
        HStack {
            Text(kind).font(.system(size: 12, weight: .semibold)).tracking(0.6).foregroundStyle(Shell.muted)
            Spacer()
            Text(OwnerFigures.relative(when)).font(.system(size: 12)).foregroundStyle(Shell.muted)
        }
    }

    private func card<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 8, content: content)
            .padding(14).frame(maxWidth: .infinity, alignment: .leading)
            .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
    }

    /// A list's load error (nothing while it first loads).
    @ViewBuilder private func failure<V>(_ loader: Loader<V>) -> some View {
        if loader.value == nil, let error = loader.error {
            Text(error).font(.system(size: 13)).foregroundStyle(Shell.muted)
        }
    }

    // MARK: Machine reports, credit sales, expenses

    @ViewBuilder private var reportCards: some View {
        failure(queues.reports)
        ForEach(queues.reports.value?.items ?? []) { report in
            Button { push(OwnerRoute.machineReport(report.id)) } label: {
                card {
                    kindLine(ReportTexts.kind, report.submittedAt)
                    Text(ReportPresentation.rowTitle(report)).font(.system(size: 16, weight: .semibold)).foregroundStyle(Shell.text)
                    Text(ReportPresentation.split(report)).font(.system(size: 13)).foregroundStyle(Shell.accent)
                }
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("approvals.report.\(report.reportNumber)")
        }
    }

    @ViewBuilder private var creditCards: some View {
        failure(queues.credit)
        ForEach(queues.creditSales) { sale in creditCard(sale) }
    }

    private func creditCard(_ sale: CreditSale) -> some View {
        let order = sale.purchase
        let blocked = model.mutationBlock(permitted: model.features.creditActivate, showingCachedData: queues.credit.isFromCache)
        return card {
            kindLine(ApprovalsTexts.creditKind, order.createdAt)
            Text(CreditSales.title(order)).font(.system(size: 16, weight: .semibold)).foregroundStyle(Shell.text)
            Text(CreditSales.detail(sale)).font(.system(size: 13)).foregroundStyle(Shell.muted)
            if CreditSales.recordedBy(order, me: model.me.userID) {
                Text(ApprovalsTexts.ownSale).font(.system(size: 13)).foregroundStyle(Shell.muted)
            } else if let blocked {
                Text(blocked.message).font(.system(size: 13)).foregroundStyle(Shell.muted)
            } else {
                HStack(spacing: 10) {
                    // Reject opens the order, where it can be cancelled (no cancellation from this list).
                    OutlineButton(ApprovalsTexts.reject, height: 40) { push(OwnerRoute.hoursPurchase(order.id)) }
                    Button { Task { await approveCredit(order) } } label: {
                        Text(busy == order.id ? "…" : ApprovalsTexts.approveCredit).font(.system(size: 14, weight: .bold))
                            .frame(maxWidth: .infinity, minHeight: 40)
                            .foregroundStyle(Shell.onAccent).background(Shell.accent, in: RoundedRectangle(cornerRadius: 14))
                    }
                    .buttonStyle(.plain)
                    .disabled(busy != nil)
                    .accessibilityIdentifier("approvals.credit.approve")
                }
            }
            if let creditError, creditError.id == order.id {
                Text(creditError.message).font(.system(size: 12)).foregroundStyle(Shell.badText)
            }
        }
    }

    @ViewBuilder private var expenseCards: some View {
        failure(queues.expenses)
        ForEach(queues.expenses.value?.items ?? []) { request in
            let expense = queues.expense(for: request)
            let detail = ExpenseApprovals.detail(request, expense)
            Button { push(OwnerRoute.approval(request.id)) } label: {
                card {
                    kindLine(ApprovalsTexts.expenseKind, request.requestedAt)
                    Text(ExpenseApprovals.title(request, expense)).font(.system(size: 16, weight: .semibold)).foregroundStyle(Shell.text)
                    if !detail.isEmpty { Text(detail).font(.system(size: 13)).foregroundStyle(Shell.muted) }
                }
            }
            .buttonStyle(.plain)
        }
    }

    // MARK: Every other kind (under All)

    @ViewBuilder private var otherGroups: some View {
        let handovers = queues.handovers.value?.items ?? []
        group(HandoverText.sectionTitle, handovers) { h in
            Button { push(OwnerRoute.handover(h.id)) } label: { PendingHandoverRow(handover: h, supervisor: queues.supervisorNames[h.staffMemberID]) }
        }
        group(PaymentReviewText.section, queues.payments.value?.items ?? []) { p in
            Button { push(OwnerRoute.customerPayment(p.id)) } label: { PendingPaymentRow(payment: p) }
        }
        group(PettyCashReviewText.section, queues.pettyRows) { row in
            Button { push(row.route) } label: {
                VStack(alignment: .leading, spacing: 4) {
                    Text(PettyCashReviewText.headline(row)).font(.headline)
                    Text(PettyCashReviewText.summary(row)).font(.subheadline).foregroundStyle(.secondary)
                    if let reason = PettyCashReviewText.reasonLine(row) {
                        Text(reason).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                    }
                    if let at = PettyCashReviewText.createdAt(row) { Text(OwnerFormat.stamp(at)).font(.caption).foregroundStyle(.secondary) }
                }
                .accessibilityElement(children: .combine)
            }
        }
        group(ExceptionReviewText.sectionTitle, queues.exceptions.value?.items ?? []) { e in
            Button { push(OwnerRoute.exception(e.id)) } label: { PendingExceptionRow(exception: e) }
        }
        group(MeterResetText.sectionTitle, queues.resets.value ?? []) { r in
            Button { push(OwnerRoute.meterReset(r.id)) } label: { MeterResetRow(reset: r) }
        }
        group(DailyReportOwnerTexts.section, queues.dailyReports.value?.items ?? []) { report in
            Button { push(OwnerRoute.dailyReport(report.id)) } label: {
                VStack(alignment: .leading, spacing: 4) {
                    Text(AllocationPresentation.rowHeadline(report)).font(.headline)
                    Text(AllocationPresentation.rowLine(report)).font(.subheadline).foregroundStyle(.secondary)
                    ForEach(AllocationPresentation.flags(report), id: \.self) { Text($0).font(.caption).foregroundStyle(Palette.warning) }
                }
                .accessibilityElement(children: .combine)
            }
        }
        ForEach(queues.otherDecisionKinds, id: \.self) { decisionGroup($0) }
    }

    @ViewBuilder private func decisionGroup(_ kind: DecisionKind) -> some View {
        group(kind.sectionTitle, queues.pending(kind)) { item in
            Button { push(OwnerRoute.decision(kind, item.recordID)) } label: { DecisionRow(item: item) }
        }
    }

    /// One titled group of rows; hidden while empty (as Android's grouped sections).
    @ViewBuilder private func group<Item: Identifiable, Row: View>(_ header: String, _ items: [Item],
                                                                    @ViewBuilder row: @escaping (Item) -> Row) -> some View {
        if !items.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                SectionLabel(header.uppercased()).padding(.top, 10)
                VStack(spacing: 0) {
                    ForEach(Array(items.enumerated()), id: \.element.id) { index, item in
                        row(item).buttonStyle(.plain).foregroundStyle(Shell.text)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, 16).padding(.vertical, 12)
                        if index < items.count - 1 { Divider().overlay(Shell.border).padding(.leading, 16) }
                    }
                }
                .background(Shell.card, in: RoundedRectangle(cornerRadius: 18))
            }
        }
    }

    // MARK: Credit approval

    /// Approves the credit part at once (credit amount ÷ effective rate), one Idempotency-Key per attempt.
    private func approveCredit(_ order: HoursPurchaseDTO) async {
        guard let repository = model.repository, busy == nil else { return }
        busy = order.id
        creditError = nil
        defer { busy = nil }
        do {
            _ = try await repository.send(OwnerAPI.activateCredit(order.id, hours: CreditSales.creditHours(order),
                                                                  reason: MachineReportOwnerTexts.creditApprovedReason,
                                                                  idempotencyKey: UUID()))
            message = ApprovalsTexts.creditApproved
            UIAccessibility.post(notification: .announcement, argument: message)
            await queues.reload(model)
        } catch {
            let code = (error as? APIError)?.code
            creditError = (order.id, ApprovalsTexts.creditRefusal(code, fallback: DecisionErrorText.message(for: error)))
            model.handle(error)
            if ApprovalsTexts.creditReloads(code) || DecisionErrorText.needsReload(error) {
                await queues.reload(model)
            }
        }
    }
}
#endif
