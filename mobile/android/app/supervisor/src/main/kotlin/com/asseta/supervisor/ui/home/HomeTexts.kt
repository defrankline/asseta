package com.asseta.supervisor.ui.home

import java.math.BigDecimal

/** Wording of the Supervisor shell, Home, Money and Dashboard (approved designs; shared with iOS word for word). */
object HomeTexts {
    // Home (design Main)
    const val CASH_IN_HAND = "Cash in hand"
    const val HOURS_TO_REPORT = "Hours to report"
    const val AWAITING_APPROVAL = "Awaiting approval"
    const val WHAT_TO_DO = "What do you want to do?"
    const val RECENT = "Recent"
    const val NO_RECENT = "Your sales and machine reports appear here."
    const val SELL_HOURS_SUB = "Customer buys machine hours"
    const val MACHINE_REPORT_SUB = "Reading → account for hours"
    const val MONEY_SUB = "Collections, hand over, expenses"
    const val DASHBOARD_SUB = "Reports, my machines"
    const val ALL_SYNCED = "All synced"
    fun notSynced(n: Int) = "$n not synced"

    // Side menu (design SideNav)
    fun role(company: String) = "Supervisor · $company"
    fun caption(version: String) = "Asseta Supervisor $version · Delete my account in Settings"

    /** Settings' caption at the bottom, under the rows. */
    fun settingsVersion(version: String) = "Asseta Supervisor $version"
    fun syncRow(waiting: Int, lastSentAt: String?) = when {
        waiting > 0 -> "Sync · $waiting waiting"
        lastSentAt != null -> "Sync · all sent $lastSentAt"
        else -> "Sync · all sent"
    }

    // Money (design Money)
    const val CASH_IN_HAND_CAPS = "Cash in hand"
    fun cashFormula(collected: String, handedOver: String, expenses: String) = "Collected $collected − handed over $handedOver − expenses $expenses"
    const val COLLECTIONS_BY_METHOD = "Collections by method"
    const val CASH = "Cash"
    const val BANK = "Bank"
    const val MOBILE_MONEY = "Mobile money"
    const val CREDIT = "Credit"
    const val CREDIT_AWAITING = " · awaiting approval"
    const val TOTAL_SOLD = "Total sold"
    const val HANDED_OVER = "Handed over to HQ"
    const val AWAITING_CHECK = "Awaiting office check"
    const val EXPENSES = "Expenses"
    fun receipts(count: Int, pending: Int) = "$count receipt${if (count == 1) "" else "s"}" + (if (pending > 0) " · $pending pending" else "")
    const val HAND_OVER = "Hand over"
    const val EXPENSE = "Expense"
    const val PETTY_CASH = "Petty cash"
    const val RECORD_INVOICE_PAYMENT = "Record a credit invoice payment"
    const val MONEY_RECORDS = "Cash records, transfers and more"
    const val MONEY_FOOTER = "Sales and payments recorded on this phone, and your cash records."
    const val NO_CASH = "No cash balance yet. It appears after a sync."

    // Dashboard (design Dashboard)
    const val HOURS_SOLD = "Hours sold"
    const val HOURS_USED = "Hours used by customers"
    const val FROM_BOUGHT = "from bought hours"
    fun machineHours(period: Period) = when (period) {
        Period.TODAY -> "Machine hours today"
        Period.WEEK -> "Machine hours this week"
        Period.MONTH -> "Machine hours this month"
    }
    fun productive(hours: String, percent: Int?) = "Productive $hours h" + (percent?.let { " ($it%)" } ?: "")
    fun nonProductive(hours: String) = "Non-productive $hours h"
    const val MY_MACHINES = "My machines"
    const val LIST = "List"
    const val MAP = "Map"
    fun lastReading(reading: String?, ago: String?) = listOfNotNull(reading?.let { "Last reading $it h" } ?: "No reading yet", ago).joinToString(" · ")
    const val REPORTS = "Reports"
    const val CUSTOMER_BALANCES = "Customer balances"
    const val MY_REPORTS = "My machine reports"
    const val MY_SALES = "My sales"
    const val MY_CASH = "My cash"
    const val NO_REPORTS = "Your machine reports of the last 30 days appear here."
    const val NO_SALES = "Hours you sell on this phone appear here."
    const val NO_BALANCES = "Customers with usable hours appear here after a sync."
    fun hoursLeft(h: String) = "$h h usable"
    const val BALANCES_FOOTER = "Hours each customer can still use in a machine report (bought, activated, not yet used or reserved)."

    // Report rows
    fun reportStatus(status: String): String = when (status) {
        "SUBMITTED" -> "Awaiting approval"
        "APPROVED" -> "Approved"
        "REJECTED" -> "Rejected"
        else -> status.lowercase().replaceFirstChar { it.uppercase() }
    }
    const val WAITING_TO_SYNC = "Waiting to sync"
    const val NOT_SYNCED = "Not synced"

    // Settings
    const val SETTINGS = "Settings"
    const val ACCOUNT = "Account"

    // Credit invoice payment
    const val INVOICE_PAYMENT_TITLE = "Credit invoice payment"
    const val INVOICE = "Invoice"
    const val NO_INVOICES = "No open credit invoices on this phone. They appear after a sync."
    fun invoiceOption(number: String, customer: String?) = listOfNotNull(number, customer).joinToString(" · ")
    fun invoiceOwes(balance: String, due: String?) = "owes $balance" + (due?.let { " · due $it" } ?: "")
    const val AMOUNT_RECEIVED = "Amount received"
    const val SAVE_PAYMENT = "Save payment"
    const val INVOICE_PAYMENT_FOOTER = "Cash goes into your cash in hand. Bank and mobile money wait for the office to verify them."

    fun signed(amount: BigDecimal) = ShellModel.grouped(amount)
}
