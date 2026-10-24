#if os(iOS)
import AssetaModel
import AssetaSync
import Foundation

/// Finance queries for the views. The permission checks only choose what to show; the server
/// enforces `tenant.expense.write` / `tenant.collection.record` on every pushed operation.
extension FieldModel {
    var canRecordExpenses: Bool { tenant.permissions.contains("tenant.expense.write") }
    var canRecordCash: Bool { tenant.permissions.contains("tenant.collection.record") }
    /// Request a job from the field for owner approval (`tenant.job.request`; the server enforces it).
    var canRequestJobs: Bool { tenant.permissions.contains("tenant.job.request") }

    var expenseCategories: [ExpenseCategoryDTO] { (try? services?.directory.expenseCategories()) ?? [] }
    var customers: [CustomerDTO] { (try? services?.directory.customers()) ?? [] }
    var machines: [MachineDTO] { (try? services?.directory.machines()) ?? [] }
    var baseCurrency: String? { services?.directory.baseCurrency() }

    func expenseGate() -> ExpenseGate {
        (try? services?.directory.expenseGate()) ?? .blocked(.noSnapshot)
    }

    func cashSummary() -> CashSummary? { try? services?.directory.cashSummary() }

    /// Picker rows for synced data (searchable; never a plain dropdown).
    var jobOptions: [PickerOption] {
        jobs.filter { !progress($0).isClosed }.map { job in
            PickerOption(id: job.id, title: job.job.jobNumber,
                         subtitle: [job.machine?.assetCode, job.customer?.name, job.site?.name].compactMap { $0 }
                             .joined(separator: " · "))
        }
    }

    var machineOptions: [PickerOption] {
        machines.map { PickerOption(id: $0.id, title: $0.assetCode, subtitle: $0.name) }
    }

    var customerOptions: [PickerOption] {
        customers.map { PickerOption(id: $0.id, title: $0.name, subtitle: $0.code) }
    }

    var categoryOptions: [PickerOption] {
        expenseCategories.map { PickerOption(id: $0.id, title: $0.name, subtitle: $0.code) }
    }
}
#endif
