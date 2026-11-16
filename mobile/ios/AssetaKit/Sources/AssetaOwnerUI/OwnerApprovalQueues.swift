#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import Observation
import SwiftUI

/// Everything waiting for a decision (Android `ApprovalsViewModel`): machine reports, credit sales and expense requests
/// (the three chips), then every other kind the role may decide under All. One instance per company, shared by the side
/// menu badge, the Home tile and the Approvals screen; each list loads on its own.
@MainActor
@Observable
final class ApprovalQueues {
    let features: OwnerFeatures
    let reports = Loader<Page<MachineReportDTO>>()
    let credit = Loader<Page<HoursPurchaseDTO>>()
    /// What is left of each customer's credit limit (best effort, online only).
    private(set) var limitLeft: [UUID: DecimalString] = [:]
    let expenses = Loader<Page<ApprovalRequestDTO>>()
    let expenseDetails = Loader<Page<ExpenseDTO>>()
    let handovers = Loader<Page<CashHandoverDTO>>()
    private(set) var supervisorNames: [UUID: String] = [:]
    let payments = Loader<Page<CustomerPaymentRecordDTO>>()
    let pettyMovements = Loader<Page<PettyCashMovementDTO>>()
    let pettyAdjustments = Loader<Page<PettyCashAdjustmentDTO>>()
    let exceptions = Loader<Page<MeterExceptionDTO>>()
    let resets = Loader<[MeterResetDTO]>()
    let dailyReports = Loader<Page<DailyReportDTO>>()
    let decisions: [DecisionKind: Loader<Page<JSONValue>>]
    /// Every list has been asked for at least once (the empty state waits for it).
    private(set) var loaded = false

    init(features: OwnerFeatures) {
        self.features = features
        decisions = Dictionary(uniqueKeysWithValues: features.decisionKinds.map { ($0, Loader<Page<JSONValue>>()) })
    }

    // MARK: Lists

    /// Credit sales still waiting (a credit part with hours not yet usable), with the customer's limit left.
    var creditSales: [CreditSale] {
        (credit.value?.items ?? []).filter(CreditSales.waiting).map { CreditSale(purchase: $0, limitLeft: limitLeft[$0.customerID]) }
    }

    func expense(for request: ApprovalRequestDTO) -> ExpenseDTO? {
        ExpenseApprovals.expense(request, in: expenseDetails.value?.items ?? [])
    }

    var pettyRows: [PettyCashRequest] {
        PettyCashReviewText.rows(movements: pettyMovements.value?.items ?? [], adjustments: pettyAdjustments.value?.items ?? [])
    }

    func pending(_ kind: DecisionKind) -> [PendingDecision] {
        guard let page = decisions[kind]?.value else { return [] }
        return PendingDecision.list(page, kind: kind).filter(\.isPending)
    }

    /// Decision kinds under All (credit arrangements go under Credit), in the order Approvals always listed them.
    var otherDecisionKinds: [DecisionKind] {
        let late: [DecisionKind] = [.allocationCorrection, .adjustmentRequest, .partialRemittance, .varianceClosure]
        return features.decisionKinds.filter { $0 != .credit && !late.contains($0) } + late.filter(features.decisionKinds.contains)
    }

    /// Waiting items per chip (an unloaded list counts 0).
    var counts: ApprovalCounts {
        ApprovalCounts(
            reports: reports.value?.items.count ?? 0,
            credit: creditSales.count + pending(.credit).count,
            expenses: expenses.value?.items.count ?? 0,
            other: otherDecisionKinds.reduce(0) { $0 + pending($1).count }
                + (resets.value?.count ?? 0)
                + (handovers.value?.items.count ?? 0)
                + (payments.value?.items.count ?? 0)
                + pettyRows.count
                + (exceptions.value?.items.count ?? 0)
                + (dailyReports.value?.items.count ?? 0)
        )
    }

    // MARK: Loading

    func reload(_ model: OwnerModel) async {
        let f = features
        await withTaskGroup(of: Void.self) { group in
            if f.machineReports { group.addTask { await self.reports.load(model, .machineReportQueue, OwnerAPI.machineReports(pending: true)) } }
            if f.creditSales { group.addTask { await self.loadCredit(model) } }
            if f.approvals { group.addTask { await self.loadExpenses(model) } }
            if f.finance { group.addTask { await self.loadHandovers(model) } }
            if f.confirmPayments { group.addTask { await self.payments.load(model, .paymentsToConfirm, OwnerAPI.paymentsToConfirm()) } }
            if f.pettyCashApprove {
                group.addTask {
                    await self.pettyMovements.load(model, .pettyCashMovementsToApprove, OwnerAPI.pettyCashMovementsToApprove())
                    await self.pettyAdjustments.load(model, .pettyCashAdjustmentsToApprove, OwnerAPI.pettyCashAdjustmentsToApprove())
                }
            }
            if f.meterEvidence {
                group.addTask {
                    await self.exceptions.load(model, .exceptions(openOnly: true),
                                               OwnerAPI.exceptions(status: ExceptionReviewText.openStatus, pageSize: 100))
                }
                group.addTask {
                    await self.resets.load(model, .meterResets(pendingOnly: true), OwnerAPI.meterResets(status: MeterResetText.pendingStatus))
                }
            }
            if f.allocationsRead {
                group.addTask {
                    await self.dailyReports.load(model, .dailyReports(status: DailyReportStatuses.submitted),
                                                 OwnerAPI.dailyReports(status: DailyReportStatuses.submitted))
                }
            }
            for (kind, loader) in decisions {
                group.addTask { await loader.load(model, .decisions(kind, pendingOnly: true), OwnerAPI.decisions(kind, pendingOnly: true)) }
            }
        }
        loaded = true
    }

    private func loadCredit(_ model: OwnerModel) async {
        await credit.load(model, .creditToApprove, OwnerAPI.creditToApprove())
        guard model.isOnline, features.hoursRead, let repository = model.repository else { return }
        let customers = Array(Set(creditSales.map(\.purchase.customerID))).prefix(CreditSales.maxExposureLookups)
        var left: [UUID: DecimalString] = [:]
        for customer in customers {
            if let exposure = try? await repository.send(OwnerAPI.customerCreditExposure(customer)), let available = exposure.available {
                left[customer] = available
            }
        }
        limitLeft = left
    }

    private func loadExpenses(_ model: OwnerModel) async {
        await expenses.load(model, .approvals(.pending), OwnerAPI.approvals(status: .pending, pageSize: 100))
        if features.expenses, expenses.value?.items.isEmpty == false {
            await expenseDetails.load(model, .expensesAwaitingApproval, OwnerAPI.expenses(status: "PENDING_APPROVAL", pageSize: 100))
        }
    }

    private func loadHandovers(_ model: OwnerModel) async {
        await handovers.loadClaimed(model)
        supervisorNames = await OwnerLookups.supervisorNames(model)
    }
}
#endif
