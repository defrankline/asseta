#if os(iOS)
import AssetaModel
import AssetaSync
import Foundation

/// Finance queries for the views. The permission checks only choose what to show; the server
/// enforces `tenant.expense.write` / `tenant.collection.record` on every pushed operation.
extension FieldModel {
    var canRecordExpenses: Bool { tenant.permissions.contains("tenant.expense.write") }
    var canRecordCash: Bool { tenant.permissions.contains("tenant.collection.record") }

    var expenseCategories: [ExpenseCategoryDTO] { (try? services?.directory.expenseCategories()) ?? [] }
    var customers: [CustomerDTO] { (try? services?.directory.customers()) ?? [] }
    var machines: [MachineDTO] { (try? services?.directory.machines()) ?? [] }
    var baseCurrency: String? { services?.directory.baseCurrency() }
    /// Machine rates and customer discounts saved from sync: the hours sale total shows as the hours are typed, offline.
    var hoursPrices: HoursPriceBook { services?.directory.hoursPrices() ?? HoursPriceBook() }
    /// Company deposit accounts saved from sync (deactivated ones included; the picker shows active ones).
    var depositAccounts: [DepositAccountDTO] { (try? services?.directory.allDepositAccounts()) ?? [] }

    func expenseGate() -> ExpenseGate {
        (try? services?.directory.expenseGate()) ?? .blocked(.noSnapshot)
    }

    func cashSummary() -> CashSummary? { try? services?.directory.cashSummary() }

    /// Picker rows for synced data (searchable; never a plain dropdown).
    var machineOptions: [PickerOption] {
        machines.map { PickerOption(id: $0.id, title: $0.assetCode, subtitle: $0.name) }
    }

    var customerOptions: [PickerOption] {
        customers.map { PickerOption(id: $0.id, title: $0.name, subtitle: $0.code) }
    }

    /// Account picker rows: active accounts of `currency` matching `method`; subtitle "{institution} · {masked}".
    func depositAccountOptions(method: RemittanceMethod, currency: String) -> [PickerOption] {
        RemittanceRules.accounts(depositAccounts, currency: currency, method: method).map {
            let subtitle = RemittanceRules.subtitle($0)
            return PickerOption(id: $0.id, title: $0.name, subtitle: subtitle.isEmpty ? nil : subtitle)
        }
    }

    var categoryOptions: [PickerOption] {
        expenseCategories.map { PickerOption(id: $0.id, title: $0.name, subtitle: $0.code) }
    }
}
#endif
