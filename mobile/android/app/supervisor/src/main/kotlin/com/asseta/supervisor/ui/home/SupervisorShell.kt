package com.asseta.supervisor.ui.home

import com.asseta.core.domain.accountability.FieldAccess
import com.asseta.core.domain.accountability.PaymentMethod
import com.asseta.core.domain.reports.MachineReportRules
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.HoursPurchasePayload
import com.asseta.core.model.sync.MachineReportDto
import com.asseta.core.sync.data.LocalInvoicePayment
import com.asseta.core.sync.data.LocalReport
import com.asseta.supervisor.ui.Route
import java.math.BigDecimal
import java.math.RoundingMode
import java.time.DayOfWeek
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Side-menu entries of the Supervisor app (approved design SideNav), in order. */
enum class MenuItem(val label: String) {
    HOME("Home"),
    SELL_HOURS("Sell hours"),
    MACHINE_REPORT("Machine report"),
    MONEY("Money"),
    FUEL("Fuel"),
    DASHBOARD("Dashboard"),
    INBOX("Inbox"),
    CUSTOMERS("Customers"),
    ;

    val root: Route
        get() = when (this) {
            HOME -> Route.Home
            SELL_HOURS -> Route.HoursSale
            MACHINE_REPORT -> Route.MachineReport()
            MONEY -> Route.Money
            FUEL -> Route.Fuel
            DASHBOARD -> Route.Dashboard
            INBOX -> Route.Inbox
            CUSTOMERS -> Route.Customers
        }
}

/** Footer entries of the side menu. */
enum class MenuFooter(val label: String) { SYNC("Sync"), SWITCH_COMPANY("Switch company"), SETTINGS("Settings"), SIGN_OUT("Sign out") }

/** Reporting periods of Money and Dashboard. */
enum class Period(val label: String) {
    TODAY("Today"), WEEK("Week"), MONTH("Month");

    /** [from, to) in epoch ms for the local day, the week (from Monday) or the month containing [nowMs]. */
    fun range(nowMs: Long, zone: ZoneId = ZoneId.systemDefault()): Pair<Long, Long> {
        val today = Instant.ofEpochMilli(nowMs).atZone(zone).toLocalDate()
        val (from, to) = when (this) {
            TODAY -> today to today.plusDays(1)
            WEEK -> today.with(DayOfWeek.MONDAY).let { it to it.plusDays(7) }
            MONTH -> today.withDayOfMonth(1).let { it to it.plusMonths(1) }
        }
        fun ms(d: LocalDate) = d.atStartOfDay(zone).toInstant().toEpochMilli()
        return ms(from) to ms(to)
    }
}

/** An hours sale recorded on this phone (from its HOURS_PURCHASE operation). */
data class SaleRecord(
    val id: String,
    val atMs: Long,
    val customer: String,
    val hours: BigDecimal,
    val parts: List<Pair<PaymentMethod, BigDecimal>>,
    val status: ClientOperationStatus,
) {
    val total: BigDecimal get() = parts.fold(BigDecimal.ZERO) { s, p -> s + p.second }
    val credit: BigDecimal get() = parts.filter { it.first == PaymentMethod.CREDIT }.fold(BigDecimal.ZERO) { s, p -> s + p.second }
}

/** Money figures of a period (approved design Money). */
data class MoneyFigures(
    val byMethod: Map<PaymentMethod, BigDecimal>,
    val totalSold: BigDecimal,
    val collected: BigDecimal,
    val handedOver: BigDecimal,
    val handedOverAwaiting: Int,
    val expenses: BigDecimal,
    val expenseCount: Int,
    val expensePending: Int,
)

/** Dashboard figures of a period (approved design Dashboard). */
data class DashboardFigures(
    val hoursSold: BigDecimal,
    val soldAmount: BigDecimal,
    val hoursUsed: BigDecimal,
    val machineHours: BigDecimal,
    val productive: BigDecimal,
    val nonProductive: BigDecimal,
) {
    /** Productive share in whole percent; null when there are no hours. */
    val productivePercent: Int?
        get() = if (machineHours.signum() <= 0) null else productive.multiply(BigDecimal(100)).divide(machineHours, 0, RoundingMode.HALF_UP).toInt()
}

/** A money movement of the period for [ShellModel.money]. */
data class Movement(val atMs: Long, val amount: BigDecimal, val pending: Boolean)

/** One row of Home's Recent list. */
data class RecentRow(val key: String, val atMs: Long, val title: String, val subtitle: String, val pill: String, val tone: RecentTone)

enum class RecentTone { WAITING, GOOD, BAD, NEUTRAL }

/** Pure rules of the Supervisor shell (menu, tiles, figures, wording), unit-tested; same rules as the iOS app. */
object ShellModel {
    /** Menu entries the user may open: Sell hours / Machine report per access, Fuel only while FUEL is on. */
    fun menu(access: FieldAccess?, permissions: Set<String>, fuelOn: Boolean): List<MenuItem> = MenuItem.entries.filter {
        when (it) {
            MenuItem.SELL_HOURS -> access?.sellHours == true
            MenuItem.MACHINE_REPORT -> access?.machineReport == true
            MenuItem.FUEL -> fuelOn && EXPENSE_WRITE in permissions
            else -> true
        }
    }

    /** Home's four tiles (design Main), the ones the user may open. */
    fun tiles(access: FieldAccess?): List<MenuItem> =
        listOf(MenuItem.SELL_HOURS, MenuItem.MACHINE_REPORT, MenuItem.MONEY, MenuItem.DASHBOARD).filter {
            when (it) {
                MenuItem.SELL_HOURS -> access?.sellHours == true
                MenuItem.MACHINE_REPORT -> access?.machineReport == true
                else -> true
            }
        }

    /** "3.85M", "950K", "1,200" (summary strip and dashboard tiles). */
    fun compact(amount: BigDecimal): String {
        val abs = amount.abs()
        fun fmt(v: BigDecimal, suffix: String) = v.setScale(2, RoundingMode.HALF_UP).stripTrailingZeros().toPlainString() + suffix
        return when {
            abs >= BigDecimal(1_000_000) -> fmt(amount.divide(BigDecimal(1_000_000)), "M")
            abs >= BigDecimal(10_000) -> fmt(amount.divide(BigDecimal(1_000)).setScale(0, RoundingMode.HALF_UP), "K")
            else -> grouped(amount)
        }
    }

    /** "3,845,000" (no decimals for whole amounts). */
    fun grouped(amount: BigDecimal): String = java.text.DecimalFormat("#,##0.##", java.text.DecimalFormatSymbols.getInstance(Locale.US)).format(amount)

    /** "TZS 3,845,000". */
    fun money(amount: BigDecimal, currency: String?) = listOfNotNull(currency, grouped(amount)).joinToString(" ")

    /** This phone's hours sales from their HOURS_PURCHASE payloads. */
    fun sale(id: String, atMs: Long, status: ClientOperationStatus, p: HoursPurchasePayload, customerName: (String) -> String?): SaleRecord {
        val parts = (p.payments ?: listOfNotNull(p.payment)).map { line ->
            val method = PaymentMethod.entries.firstOrNull { it.wire == line.method } ?: PaymentMethod.CASH
            method to (line.amount?.value ?: BigDecimal.ZERO)
        }
        val customer = p.customerId?.let(customerName) ?: p.walkIn?.name ?: "Walk-in"
        return SaleRecord(id, atMs, customer, p.hours.toBigDecimalOrNull() ?: BigDecimal.ZERO, parts, status)
    }

    fun inPeriod(atMs: Long, range: Pair<Long, Long>) = atMs >= range.first && atMs < range.second

    /** Collections by method (my sales and credit-invoice payments of the period), handed over and expenses. */
    fun money(
        range: Pair<Long, Long>,
        sales: List<SaleRecord>,
        invoicePayments: List<LocalInvoicePayment>,
        handovers: List<Movement>,
        expenses: List<Movement>,
    ): MoneyFigures {
        val byMethod = linkedMapOf<PaymentMethod, BigDecimal>().apply { PaymentMethod.entries.forEach { put(it, BigDecimal.ZERO) } }
        sales.filter { inPeriod(it.atMs, range) && it.status != ClientOperationStatus.FAILED }.forEach { s ->
            s.parts.forEach { (m, a) -> byMethod[m] = byMethod.getValue(m) + a }
        }
        invoicePayments.filter { inPeriod(it.createdAtMs, range) && it.status != ClientOperationStatus.FAILED }.forEach { p ->
            val m = PaymentMethod.entries.firstOrNull { it.wire == p.payload.method } ?: PaymentMethod.CASH
            byMethod[m] = byMethod.getValue(m) + (p.payload.amount.toBigDecimalOrNull() ?: BigDecimal.ZERO)
        }
        val h = handovers.filter { inPeriod(it.atMs, range) }
        val e = expenses.filter { inPeriod(it.atMs, range) }
        return MoneyFigures(
            byMethod = byMethod,
            totalSold = byMethod.values.fold(BigDecimal.ZERO, BigDecimal::add),
            collected = byMethod.filterKeys { it != PaymentMethod.CREDIT }.values.fold(BigDecimal.ZERO, BigDecimal::add),
            handedOver = h.fold(BigDecimal.ZERO) { s, m -> s + m.amount },
            handedOverAwaiting = h.count { it.pending },
            expenses = e.fold(BigDecimal.ZERO) { s, m -> s + m.amount },
            expenseCount = e.size,
            expensePending = e.count { it.pending },
        )
    }

    /** Hours sold (my sales), hours used by customers and productive vs non-productive (my reports) in the period. */
    fun dashboard(range: Pair<Long, Long>, sales: List<SaleRecord>, reports: List<MachineReportDto>, local: List<LocalReport>, at: (String) -> Long?): DashboardFigures {
        val sold = sales.filter { inPeriod(it.atMs, range) && it.status != ClientOperationStatus.FAILED }
        val server = reports.filter { it.status != MachineReportDto.REJECTED && (at(it.submittedAt) ?: 0L).let { t -> inPeriod(t, range) } }
        val phone = local.filter { it.waiting && server.none { s -> s.id == it.operationId } && inPeriod(it.createdAtMs, range) }
        fun BigDecimal?.orZero() = this ?: BigDecimal.ZERO
        val customer = server.fold(BigDecimal.ZERO) { s, r -> s + r.customerHours.toBigDecimalOrNull().orZero() } + phone.fold(BigDecimal.ZERO) { s, r -> s + r.customerHours }
        val all = server.fold(BigDecimal.ZERO) { s, r -> s + r.hours.toBigDecimalOrNull().orZero() } + phone.fold(BigDecimal.ZERO) { s, r -> s + r.hours }
        val non = server.fold(BigDecimal.ZERO) { s, r -> s + r.nonProductiveHours.toBigDecimalOrNull().orZero() } + phone.fold(BigDecimal.ZERO) { s, r -> s + (r.hours - r.customerHours) }
        return DashboardFigures(
            hoursSold = sold.fold(BigDecimal.ZERO) { s, x -> s + x.hours },
            soldAmount = sold.fold(BigDecimal.ZERO) { s, x -> s + x.total },
            hoursUsed = customer,
            machineHours = all,
            productive = customer,
            nonProductive = non,
        )
    }

    /** "Today 07:40", "Yesterday 16:05", "12 Nov 17:30". */
    fun when_(atMs: Long, nowMs: Long, zone: ZoneId = ZoneId.systemDefault()): String {
        val t = Instant.ofEpochMilli(atMs).atZone(zone)
        val today = Instant.ofEpochMilli(nowMs).atZone(zone).toLocalDate()
        val time = t.format(DateTimeFormatter.ofPattern("HH:mm", Locale.ENGLISH))
        return when (t.toLocalDate()) {
            today -> "Today $time"
            today.minusDays(1) -> "Yesterday $time"
            else -> t.format(DateTimeFormatter.ofPattern("d MMM HH:mm", Locale.ENGLISH))
        }
    }

    /** "today 07:40", "yesterday", "3 days ago" (my machines). */
    fun ago(atMs: Long?, nowMs: Long, zone: ZoneId = ZoneId.systemDefault()): String? {
        atMs ?: return null
        val t = Instant.ofEpochMilli(atMs).atZone(zone)
        val days = java.time.temporal.ChronoUnit.DAYS.between(t.toLocalDate(), Instant.ofEpochMilli(nowMs).atZone(zone).toLocalDate())
        return when {
            days <= 0 -> "today " + t.format(DateTimeFormatter.ofPattern("HH:mm", Locale.ENGLISH))
            days == 1L -> "yesterday"
            else -> "$days days ago"
        }
    }

    /** "Sold 20 h · Pwani Road"; subtitle "Yesterday 16:05 · TZS 1,900,000"; pill Paid / Part on credit / Not synced. */
    fun recentSale(s: SaleRecord, currency: String?, nowMs: Long): RecentRow {
        val (pill, tone) = when {
            s.status == ClientOperationStatus.FAILED || s.status == ClientOperationStatus.CONFLICT -> "Not synced" to RecentTone.BAD
            s.status != ClientOperationStatus.ACKED -> "Waiting to sync" to RecentTone.NEUTRAL
            s.parts.isEmpty() -> "Not paid" to RecentTone.WAITING
            s.credit.signum() > 0 -> "Credit" to RecentTone.WAITING
            else -> "Paid" to RecentTone.GOOD
        }
        val amount = s.total.takeIf { it.signum() > 0 }?.let { " · " + money(it, currency) }.orEmpty()
        return RecentRow("sale-${s.id}", s.atMs, "Sold ${MachineReportRules.formatHours(s.hours)} h · ${s.customer}", ShellModel.when_(s.atMs, nowMs) + amount, pill, tone)
    }

    const val EXPENSE_WRITE = "tenant.expense.write"
}
