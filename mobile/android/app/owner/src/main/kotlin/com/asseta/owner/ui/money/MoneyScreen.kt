package com.asseta.owner.ui.money

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.owner.CashSupervisorSummaryDto
import com.asseta.core.model.owner.OwnerHoursPurchaseDto
import com.asseta.core.model.owner.RemittanceOverdueDto
import com.asseta.core.model.sync.CreditInvoiceDto
import com.asseta.core.ui.shell.CardRow
import com.asseta.core.ui.shell.PeriodTabs
import com.asseta.core.ui.shell.PillTone
import com.asseta.core.ui.shell.SectionLabel
import com.asseta.core.ui.shell.ShellCard
import com.asseta.core.ui.shell.StatusPill
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.common.Figures
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.Period
import com.asseta.owner.ui.common.ScreenState
import com.asseta.owner.ui.common.Section
import com.asseta.owner.ui.common.ShellButton
import com.asseta.owner.ui.common.StaleBanner
import com.asseta.owner.ui.customers.MoneyWords
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.math.BigDecimal
import java.time.LocalDate
import java.time.temporal.ChronoUnit

/** Money wording (design OwnerMoney; same as iOS). */
object MoneyTexts {
    const val CASH_WITH_SUPERVISORS = "CASH WITH SUPERVISORS"
    const val CREDIT_INVOICES = "CREDIT INVOICES"
    const val AWAITING_CHECK = "awaiting your check"
    const val OVERDUE_HANDOVER = "Overdue to hand over"
    const val HOLDING = "Holding"
    const val NO_SALES = "No sales in this period."
    const val NO_CASH = "No supervisor holds cash."
    const val NO_INVOICES = "No open credit invoices."
    const val PART_PAID = "Part paid"
    const val UNPAID = "Unpaid"
    const val PAID = "Paid"
    const val OVERDUE = "Overdue"
    const val CANCELLED = "Cancelled"

    fun sold(p: Period) = when (p) {
        Period.TODAY -> "SOLD TODAY"
        Period.WEEK -> "SOLD THIS WEEK"
        Period.MONTH -> "SOLD THIS MONTH"
    }

    fun handedOver(amount: BigDecimal) = "Handed over ${Figures.compact(amount)} · $AWAITING_CHECK"
    fun overdue(days: Long?) = OVERDUE_HANDOVER + (days?.takeIf { it > 0 }?.let { " · ${Figures.days(it.toInt())}" } ?: "")
    fun expenses(n: Int?) = "Expenses" + (n?.let { " ($it)" } ?: "")
}

/** Sold in a period for one currency: the total and each payment method (credit = the orders' credit parts). */
data class SoldByMethod(val currency: String, val total: BigDecimal, val byMethod: List<Pair<String, BigDecimal>>) {
    /** "TZS 12,600,000". */
    val totalText: String get() = Figures.money(total, currency)

    /** "Cash 5.4M · Bank 2.0M · Mobile 1.4M · Credit 3.8M" (methods with nothing left out). */
    val methodsText: String get() = byMethod.filter { it.second.signum() > 0 }.joinToString(" · ") { (m, v) -> "${MoneyWords.method(m)} ${Figures.compact(v)}" }
}

/** Pure Money presentation (unit-tested). */
object MoneyPresentation {
    private val METHODS = listOf("CASH", "BANK", "MOBILE_MONEY", "CREDIT")

    /**
     * Orders of the period by currency: the total of the orders (cancelled ones left out) and the money per method
     * from their payment parts (rejected or reversed parts left out) plus the credit parts.
     */
    fun sold(orders: List<OwnerHoursPurchaseDto>): List<SoldByMethod> =
        orders.filter { it.cancelledAt == null }.groupBy { it.currency ?: "" }.toSortedMap().map { (currency, list) ->
            val sums = METHODS.associateWith { BigDecimal.ZERO }.toMutableMap()
            list.forEach { o ->
                o.payments.filter { it.status != "REJECTED" && it.reversedAt == null }.forEach { p ->
                    val m = if (p.method == "BANK_TRANSFER") "BANK" else p.method
                    sums[m] = (sums[m] ?: BigDecimal.ZERO) + Figures.dec(p.amount)
                }
                sums["CREDIT"] = sums.getValue("CREDIT") + Figures.dec(o.creditAmount)
            }
            val total = list.fold(BigDecimal.ZERO) { a, o -> a + (o.amount?.let(Figures::dec) ?: BigDecimal.ZERO) }
            SoldByMethod(currency, total, METHODS.map { it to sums.getValue(it) } + sums.filterKeys { it !in METHODS }.toList())
        }

    /** The pill of an invoice (design: Part paid / Unpaid / Paid / Overdue). */
    fun pill(i: CreditInvoiceDto): Pair<String, PillTone> = when {
        i.status == CreditInvoiceDto.CANCELLED -> MoneyTexts.CANCELLED to PillTone.NEUTRAL
        i.status == CreditInvoiceDto.PAID -> MoneyTexts.PAID to PillTone.GOOD
        i.overdue -> MoneyTexts.OVERDUE to PillTone.BAD
        i.status == CreditInvoiceDto.PART_PAID -> MoneyTexts.PART_PAID to PillTone.WAITING
        else -> MoneyTexts.UNPAID to PillTone.WAITING
    }

    /** "INV-0042 · Msasani Bay". */
    fun invoiceTitle(i: CreditInvoiceDto): String = listOfNotNull(i.invoiceNumber, i.customerName).joinToString(" · ")

    /** "3.8M · paid 1.8M by bank · due 30 Nov" (the method only when the payments are known). */
    fun invoiceDetail(i: CreditInvoiceDto): String {
        val paid = Figures.dec(i.paid)
        val method = i.payments.filter { it.counts }.map { it.method }.distinct().singleOrNull()?.let { " by ${MoneyWords.method(it).lowercase()}" } ?: ""
        return listOfNotNull(
            Figures.compact(Figures.dec(i.amount)),
            "paid ${Figures.compact(paid)}$method".takeIf { paid.signum() > 0 },
            "due ${Figures.day(i.dueDate)}",
        ).joinToString(" · ")
    }

    /** Invoices to show: open ones first (overdue, then by due date), then the period's paid ones; at most [max]. */
    fun invoices(all: List<CreditInvoiceDto>, max: Int = 20): List<CreditInvoiceDto> =
        all.filter { it.status != CreditInvoiceDto.CANCELLED }
            .sortedWith(compareBy<CreditInvoiceDto> { it.status == CreditInvoiceDto.PAID }.thenByDescending { it.overdue }.thenBy { it.dueDate })
            .take(max)

    /** A supervisor's cash line: handed over and waiting for the office, or overdue to hand over. */
    fun cashDetail(s: CashSupervisorSummaryDto, overdue: RemittanceOverdueDto?, today: LocalDate): String? {
        val claimed = s.claimedUnverifiedHandovers.value
        return when {
            overdue != null -> MoneyTexts.overdue(overdue.heldSince?.let { runCatching { LocalDate.parse(it.take(10)) }.getOrNull() }?.let { ChronoUnit.DAYS.between(it, today) })
            claimed.signum() > 0 -> MoneyTexts.handedOver(claimed)
            else -> null
        }
    }
}

class MoneyViewModel(
    private val data: OwnerData,
    private val features: OwnerFeatures,
    refreshOn: Flow<Unit>,
    private val today: () -> LocalDate = { LocalDate.now() },
) : ViewModel() {
    private val selected = MutableStateFlow(Period.WEEK)
    val period: StateFlow<Period> = selected.asStateFlow()
    private fun range() = selected.value.range(today())

    val orders: Section<List<OwnerHoursPurchaseDto>>? = if (features.customerHours) Section(viewModelScope) { range().let { data.ordersBetween(it.from, it.to) } } else null
    val cash: Section<List<CashSupervisorSummaryDto>>? = if (features.finance) Section(viewModelScope) { range().let { data.cash("money_${selected.value.name}", it.from, it.to) } } else null
    val overdue: Section<List<RemittanceOverdueDto>>? = if (features.finance && features.cashCustody) Section(viewModelScope) { data.remittanceOverdue(today()) } else null
    val invoices: Section<List<CreditInvoiceDto>>? = if (features.customerHours) Section(viewModelScope) { data.creditInvoices() } else null
    val pendingExpenses: Section<com.asseta.core.model.owner.PageDto<com.asseta.core.model.owner.ExpenseDto>>? =
        if (features.expenses) Section(viewModelScope) { data.expenses("PENDING_APPROVAL") } else null
    private val all = listOfNotNull(orders, cash, overdue, invoices, pendingExpenses)

    init {
        refresh()
        viewModelScope.launch { refreshOn.collect { refresh() } }
    }

    fun refresh() = all.forEach { it.refresh() }

    fun select(p: Period) {
        if (selected.value == p) return
        selected.value = p
        orders?.refresh()
        cash?.refresh()
    }
}

@Composable
fun MoneyScreen(vm: MoneyViewModel, features: OwnerFeatures, onOpen: (OwnerDestination) -> Unit) {
    val period by vm.period.collectAsStateWithLifecycle()
    val orders = vm.orders?.state?.collectAsStateWithLifecycle()?.value
    val cash = vm.cash?.state?.collectAsStateWithLifecycle()?.value
    val overdue = vm.overdue?.state?.collectAsStateWithLifecycle()?.value?.data.orEmpty()
    val invoices = vm.invoices?.state?.collectAsStateWithLifecycle()?.value
    val expenses = vm.pendingExpenses?.state?.collectAsStateWithLifecycle()?.value?.data
    val today = LocalDate.now()
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 24.dp)) {
        item { PeriodTabs(Period.entries.map { it to it.label }, period, vm::select) }
        orders?.let { st ->
            item { SectionLabel(MoneyTexts.sold(period)) }
            item {
                Column(Modifier.padding(horizontal = 20.dp)) {
                    StaleBanner(st.snapshot)
                    val sold = st.data?.let(MoneyPresentation::sold)
                    when {
                        sold == null && st.loading -> Unit
                        sold == null -> FootNote(st.error?.message.orEmpty())
                        sold.isEmpty() -> FootNote(MoneyTexts.NO_SALES)
                        else -> sold.forEach { s ->
                            Text(s.totalText, fontSize = 26.sp, fontWeight = FontWeight.Bold)
                            Text(s.methodsText, fontSize = 14.sp, color = palette.accent, modifier = Modifier.padding(bottom = 6.dp))
                        }
                    }
                }
            }
        }
        cash?.let { st ->
            item { SectionLabel(MoneyTexts.CASH_WITH_SUPERVISORS) }
            item { CashCard(st, overdue, today, onOpen) }
        }
        invoices?.let { st ->
            item { SectionLabel(MoneyTexts.CREDIT_INVOICES) }
            item {
                val list = st.data?.let { MoneyPresentation.invoices(it) }
                when {
                    list == null && st.loading -> Unit
                    list == null -> Column(Modifier.padding(horizontal = 20.dp)) { FootNote(st.error?.message.orEmpty()) }
                    list.isEmpty() -> Column(Modifier.padding(horizontal = 20.dp)) { FootNote(MoneyTexts.NO_INVOICES) }
                    else -> ShellCard(padding = false) {
                        list.forEachIndexed { i, inv ->
                            val (pill, tone) = MoneyPresentation.pill(inv)
                            val pay = OwnerDestination.RecordPayment(inv.id).takeIf { features.recordInvoicePayments && Figures.dec(inv.balance).signum() > 0 && inv.status != CreditInvoiceDto.CANCELLED }
                            CardRow(
                                MoneyPresentation.invoiceTitle(inv), MoneyPresentation.invoiceDetail(inv), last = i == list.lastIndex,
                                onClick = pay?.let { d -> { onOpen(d) } },
                                trailing = { StatusPill(pill, tone) },
                            )
                        }
                    }
                }
            }
        }
        item {
            Row(Modifier.padding(start = 20.dp, end = 20.dp, top = 20.dp).fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                if (features.expenses) {
                    ShellButton(MoneyTexts.expenses(expenses?.total), primary = false, enabled = true, modifier = Modifier.weight(1f)) { onOpen(OwnerDestination.FieldSpend) }
                }
                if (features.recordInvoicePayments) {
                    ShellButton(PaymentTexts.TITLE, primary = true, enabled = true, modifier = Modifier.weight(1f)) { onOpen(OwnerDestination.RecordPayment()) }
                }
            }
        }
    }
}

@Composable
private fun CashCard(st: ScreenState<List<CashSupervisorSummaryDto>>, overdue: List<RemittanceOverdueDto>, today: LocalDate, onOpen: (OwnerDestination) -> Unit) {
    val list = st.data?.filter { it.closingOutstanding.value.signum() != 0 || it.claimedUnverifiedHandovers.value.signum() > 0 }
        ?.sortedByDescending { it.closingOutstanding.value }
    when {
        list == null && st.loading -> Unit
        list == null -> Column(Modifier.padding(horizontal = 20.dp)) { FootNote(st.error?.message.orEmpty()) }
        list.isEmpty() -> Column(Modifier.padding(horizontal = 20.dp)) { FootNote(MoneyTexts.NO_CASH) }
        else -> ShellCard(padding = false) {
            list.forEachIndexed { i, s ->
                val flag = overdue.firstOrNull { it.staffMemberId == s.staffMemberId.toString() }
                CardRow(
                    s.staffName, MoneyPresentation.cashDetail(s, flag, today), last = i == list.lastIndex,
                    onClick = { onOpen(OwnerDestination.Cash) },
                    trailing = { Text(Figures.compact(s.closingOutstanding.value), fontWeight = FontWeight.Bold, fontSize = 16.sp) },
                )
            }
        }
    }
}
