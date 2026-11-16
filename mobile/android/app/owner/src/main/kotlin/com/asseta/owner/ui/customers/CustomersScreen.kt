package com.asseta.owner.ui.customers

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.reports.MachineReportRules
import com.asseta.core.model.sync.CreditInvoiceDto
import com.asseta.core.model.sync.CustomerHoursSummaryDto
import com.asseta.core.ui.shell.CardRow
import com.asseta.core.ui.shell.PillTone
import com.asseta.core.ui.shell.ShellCard
import com.asseta.core.ui.shell.StatusPill
import com.asseta.core.ui.shell.SummaryFigure
import com.asseta.core.ui.shell.SummaryStrip
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.common.CardDetail
import com.asseta.owner.ui.common.CardGap
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.Figures
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.ItemCard
import com.asseta.owner.ui.common.LoadFailure
import com.asseta.owner.ui.common.Section
import com.asseta.owner.ui.common.StaleBanner
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.launch
import java.math.BigDecimal

/** Customers & hours wording (design OwnerCustomers; same as iOS). */
object CustomerTexts {
    const val SEARCH = "Search customers"
    const val BOUGHT = "Bought"
    const val USED = "Used"
    const val OWED = "Credit owed"
    const val ALL_PAID = "all paid"
    const val EMPTY = "No customers with hours yet."
    const val NO_MATCH = "No customer matches this search."

    fun left(hours: BigDecimal) = "${MachineReportRules.formatHours(hours)} h left"
    fun bought(hours: BigDecimal) = "Bought ${MachineReportRules.formatHours(hours)} h"
    fun used(hours: BigDecimal) = "used ${MachineReportRules.formatHours(hours)} h"
    fun awaiting(owed: BigDecimal) = "${Figures.compact(owed)} on credit, awaiting approval"
    fun invoiceTitle(number: String) = "Invoice $number · credit"
    fun owed(balance: BigDecimal) = "${Figures.compact(balance)} owed"
}

/** Pure Customers & hours presentation (unit-tested). */
object CustomersPresentation {
    data class Totals(val bought: BigDecimal, val used: BigDecimal, val owed: BigDecimal)

    fun totals(list: List<CustomerHoursSummaryDto>): Totals =
        Totals(Figures.sum(list.map { it.bought }), Figures.sum(list.map { it.used }), Figures.sum(list.map { it.creditOwed }))

    fun figures(t: Totals): List<SummaryFigure> = listOf(
        SummaryFigure(CustomerTexts.BOUGHT, Figures.hours(t.bought)),
        SummaryFigure(CustomerTexts.USED, Figures.hours(t.used)),
        SummaryFigure(CustomerTexts.OWED, Figures.compact(t.owed), accent = t.owed.signum() > 0),
    )

    /** Customers matching [query] (name, case-insensitive), by name. */
    fun filter(list: List<CustomerHoursSummaryDto>, query: String): List<CustomerHoursSummaryDto> {
        val q = query.trim().lowercase()
        return list.filter { q.isEmpty() || (it.customerName ?: "").lowercase().contains(q) }.sortedBy { (it.customerName ?: "").lowercase() }
    }

    /** "Bought 160 h · used 140 h · all paid" (or "· 3.6M on credit, awaiting approval"). */
    fun detail(c: CustomerHoursSummaryDto): String {
        val owed = Figures.dec(c.creditOwed)
        val awaiting = Figures.dec(c.awaitingActivation)
        val tail = when {
            owed.signum() == 0 && awaiting.signum() == 0 -> CustomerTexts.ALL_PAID
            owed.signum() > 0 && awaiting.signum() > 0 -> CustomerTexts.awaiting(owed)
            else -> null
        }
        return listOfNotNull(CustomerTexts.bought(Figures.dec(c.bought)), CustomerTexts.used(Figures.dec(c.used)), tail).joinToString(" · ")
    }

    /** The customer's open credit invoices (balance left, not cancelled), oldest due first. */
    fun openInvoices(c: CustomerHoursSummaryDto, invoices: List<CreditInvoiceDto>): List<CreditInvoiceDto> =
        invoices.filter { it.customerId == c.customerId && it.status != CreditInvoiceDto.CANCELLED && Figures.dec(it.balance).signum() > 0 }
            .sortedBy { it.dueDate }

    /** "3,800,000 · paid 1,800,000 (bank) · due 30 Nov" (the method only when the payments are known). */
    fun invoiceLine(i: CreditInvoiceDto): String {
        val paid = Figures.dec(i.paid)
        val methods = i.payments.filter { it.counts }.map { it.method }.distinct()
        val how = methods.singleOrNull()?.let { " (${MoneyWords.method(it).lowercase()})" } ?: ""
        return listOfNotNull(
            Figures.money(Figures.dec(i.amount), "").trim(),
            ("paid ${Figures.money(paid, "").trim()}$how").takeIf { paid.signum() > 0 },
            "due ${Figures.day(i.dueDate)}",
        ).joinToString(" · ")
    }
}

/** Payment method words shared by Customers and Money (design: Cash · Bank · Mobile · Credit). */
object MoneyWords {
    fun method(m: String): String = when (m) {
        "CASH" -> "Cash"
        "BANK", "BANK_TRANSFER" -> "Bank"
        "MOBILE_MONEY" -> "Mobile"
        "CREDIT" -> "Credit"
        else -> m.lowercase().replaceFirstChar { it.uppercase() }
    }
}

class CustomersViewModel(data: OwnerData, refreshOn: Flow<Unit>) : ViewModel() {
    val customers = Section(viewModelScope) { data.customerHoursSummary() }
    val invoices = Section(viewModelScope) { data.creditInvoices() }

    init {
        refresh()
        viewModelScope.launch { refreshOn.collect { refresh() } }
    }

    fun refresh() {
        customers.refresh()
        invoices.refresh()
    }
}

@Composable
fun CustomersScreen(vm: CustomersViewModel, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.customers.state.collectAsStateWithLifecycle()
    val invoices = vm.invoices.state.collectAsStateWithLifecycle().value.data.orEmpty()
    var query by rememberSaveable { mutableStateOf("") }
    val all = state.data
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 24.dp)) {
        item {
            OutlinedTextField(
                query, { query = it.take(100) }, Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
                placeholder = { Text(CustomerTexts.SEARCH) }, label = { Text(CustomerTexts.SEARCH) }, singleLine = true,
            )
        }
        item { Column(Modifier.padding(horizontal = 20.dp, vertical = 4.dp)) { StaleBanner(state.snapshot) } }
        if (all == null) {
            item { if (!state.loading) LoadFailure(state.error, vm::refresh) }
            return@LazyColumn
        }
        item { SummaryStrip(CustomersPresentation.figures(CustomersPresentation.totals(all)), Modifier.padding(top = 8.dp, bottom = 16.dp)) }
        val shown = CustomersPresentation.filter(all, query)
        if (shown.isEmpty()) item { EmptyState(if (all.isEmpty()) CustomerTexts.EMPTY else CustomerTexts.NO_MATCH) }
        shown.forEach { c ->
            item(key = c.customerId) {
                ItemCard(onClick = { onOpen(OwnerDestination.HoursStatement(c.customerId, c.customerName)) }) {
                    androidx.compose.foundation.layout.Row(Modifier.fillMaxWidth()) {
                        Text(c.customerName ?: c.customerId, fontSize = 16.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                        Text(CustomerTexts.left(Figures.dec(c.left)), fontSize = 15.sp, fontWeight = FontWeight.Bold)
                    }
                    CardDetail(CustomersPresentation.detail(c), accent = true)
                    CustomersPresentation.openInvoices(c, invoices).forEach { i ->
                        ShellCardRow(i)
                    }
                }
                CardGap()
            }
        }
        if (vm.invoices.state.value.error != null && vm.invoices.state.value.data == null) {
            item { Column(Modifier.padding(horizontal = 20.dp)) { FootNote(vm.invoices.state.value.error!!.message) } }
        }
    }
}

/** One open invoice inside a customer card. */
@Composable
private fun ShellCardRow(i: CreditInvoiceDto) {
    androidx.compose.foundation.layout.Row(
        Modifier.padding(top = 10.dp).fillMaxWidth()
            .clip(androidx.compose.foundation.shape.RoundedCornerShape(12.dp)).background(palette.raised).padding(12.dp),
        verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(CustomerTexts.invoiceTitle(i.invoiceNumber), fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
            Text(CustomersPresentation.invoiceLine(i), fontSize = 13.sp, color = palette.secondaryText)
        }
        StatusPill(CustomerTexts.owed(Figures.dec(i.balance)), if (i.overdue) PillTone.BAD else PillTone.WAITING)
    }
}
