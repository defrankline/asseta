package com.asseta.owner.ui.accountability

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.HoursStatementDto
import com.asseta.core.model.owner.HoursStatementUsageDto
import com.asseta.core.model.owner.OwnerHoursPurchaseDto
import com.asseta.core.ui.components.FilterChipRow
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.NavigationRow
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.math.BigDecimal
import java.time.LocalDate
import java.time.ZoneId

private val T = OwnerAccountabilityTexts

/** Statement period chips (owner.stmt.period.*): local days, always ending today except Last month. */
enum class StatementPeriod(val label: String) {
    THIS_MONTH("This month"),
    LAST_MONTH("Last month"),
    LAST_3_MONTHS("Last 3 months"),
    THIS_YEAR("This year"),
    ;

    fun range(today: LocalDate): Pair<LocalDate, LocalDate> = when (this) {
        THIS_MONTH -> today.withDayOfMonth(1) to today
        LAST_MONTH -> today.withDayOfMonth(1).minusMonths(1).let { it to it.withDayOfMonth(it.lengthOfMonth()) }
        LAST_3_MONTHS -> today.withDayOfMonth(1).minusMonths(2) to today
        THIS_YEAR -> today.withDayOfYear(1) to today
    }
}

/** One usage line of the statement: label, value, caption. */
data class UsageLine(val label: String, val value: String, val caption: String)

/** Pure presentation of customer hours, purchases and the statement (unit-tested; same rules as iOS). */
object HoursPresentation {
    private fun dec(raw: String?): BigDecimal = raw?.toBigDecimalOrNull() ?: BigDecimal.ZERO
    private fun positive(raw: String?): Boolean = dec(raw).signum() > 0
    /** Hours in the phone's number format, 0–2 decimals, no trailing zeros ("12", "1,234.5"), as on iOS. */
    private fun num(raw: String?) = OwnerFormat.hoursNumber(raw)
    private fun hours(raw: String?) = "${num(raw)} h"

    /** Open (not cancelled) purchases with hours left or in use by running jobs, newest first. */
    fun open(items: List<OwnerHoursPurchaseDto>): List<OwnerHoursPurchaseDto> =
        items.filter { it.cancelledAt == null && (positive(it.totals.remaining) || positive(it.totals.provisional)) }.sortedByDescending { it.createdAt }

    /** "{left} h left[ · {n} h in use by running jobs]" (provisional is already out of remaining: never subtracted again). */
    fun leftLine(remaining: String?, provisional: String?): String =
        T.hoursLeft(num(remaining)) + if (positive(provisional)) " · " + T.hoursInUse(num(provisional)) else ""

    fun machine(p: OwnerHoursPurchaseDto): String = RevenuePresentation.machine(p.machineCode, p.machineName, p.machineId)

    fun customer(p: OwnerHoursPurchaseDto): String = p.customerName ?: p.customerId.take(8)

    /** Hours card rows in the documented order (zero-only optional rows left out). */
    fun purchaseRows(p: OwnerHoursPurchaseDto): List<Pair<String, String>> = buildList {
        val t = p.totals
        add(T.HOURS_CUSTOMER to customer(p))
        add(T.HOURS_MACHINE to machine(p))
        add(T.HOURS_STATUS to T.purchaseStatus(p.status))
        add(T.HOURS_BOUGHT to hours(t.purchased))
        add(T.HOURS_ACTIVATED to hours(t.activated))
        add(T.HOURS_USED to hours(t.consumed))
        if (positive(t.provisional)) add(T.HOURS_PROVISIONAL to hours(t.provisional))
        if (positive(t.transferred)) add(T.HOURS_TRANSFERRED to hours(t.transferred))
        if (positive(t.expired)) add(T.HOURS_EXPIRED to hours(t.expired))
        add(T.HOURS_REMAINING to hours(t.remaining))
        if (positive(t.awaitingActivation)) add(T.HOURS_AWAITING to hours(t.awaitingActivation))
    }

    /** Per-machine rows, only when the hours are on more than one machine. */
    fun machineRows(p: OwnerHoursPurchaseDto): List<Pair<String, String>> =
        if (p.machines.size < 2) emptyList()
        else p.machines.map { m -> RevenuePresentation.machine(m.machineCode, m.machineName, m.machineId) to leftLine(m.remaining, m.provisional) }

    fun period(from: String, to: String): String =
        if (from == to) RevenuePresentation.day(from) else "${RevenuePresentation.day(from)} – ${RevenuePresentation.day(to)}"

    fun header(s: HoursStatementDto, fallbackName: String?): String =
        T.stmtHeader(s.customerName ?: fallbackName ?: s.customerId.take(8), period(s.dateFrom, s.dateTo))

    /** Totals rows in the documented order (optional rows only when > 0). */
    fun totals(s: HoursStatementDto): List<Pair<String, String>> = buildList {
        val t = s.totals
        add(T.STMT_OPENING to hours(t.openingBalance))
        add(T.STMT_BOUGHT to hours(t.bought))
        add(T.STMT_ACTIVATED to hours(t.activated))
        add(T.STMT_USED to hours(t.used))
        if (positive(t.provisionalAtClose)) add(T.STMT_PROVISIONAL_AT_CLOSE to hours(t.provisionalAtClose))
        if (positive(t.transferredIn)) add(T.STMT_TRANSFERRED_IN to hours(t.transferredIn))
        if (positive(t.transferredOut)) add(T.STMT_TRANSFERRED_OUT to hours(t.transferredOut))
        if (positive(t.expired)) add(T.STMT_EXPIRED to hours(t.expired))
        if (positive(t.cancelled)) add(T.STMT_CANCELLED to hours(t.cancelled))
        add(T.STMT_CLOSING to hours(t.closingBalance))
        if (positive(t.awaitingActivation)) add(T.STMT_AWAITING to hours(t.awaitingActivation))
    }

    /** Usage lines, newest day first. */
    fun usage(s: HoursStatementDto): List<UsageLine> = s.usage.sortedByDescending { it.day }.map { u: HoursStatementUsageDto ->
        val caption = listOf(RevenuePresentation.machine(u.machineCode, u.machineName, u.machineId), T.stmtBasis(u.basis)) +
            listOfNotNull(T.STMT_RUNNING.takeIf { u.jobRunning })
        UsageLine(T.stmtUsageRow(RevenuePresentation.day(u.day), u.jobNumber ?: "—"), hours(u.hours), caption.joinToString(" · "))
    }
}

// --- view models -------------------------------------------------------------------------------------------------------

class CustomerHoursViewModel(data: OwnerData, refreshOn: Flow<Unit>) :
    SnapshotViewModel<List<OwnerHoursPurchaseDto>>({ data.hoursPurchases() }, refreshOn)

class HoursPurchaseViewModel(data: OwnerData, purchaseId: String, refreshOn: Flow<Unit>) :
    SnapshotViewModel<OwnerHoursPurchaseDto>({ data.hoursPurchase(purchaseId) }, refreshOn)

/** PDF download state of the statement screen. */
data class PdfState(val busy: Boolean = false, val bytes: ByteArray? = null, val error: String? = null)

class HoursStatementViewModel private constructor(
    private val data: OwnerData,
    private val customerId: String,
    private val selected: MutableStateFlow<StatementPeriod>,
    private val today: () -> LocalDate,
    refreshOn: Flow<Unit>,
) : SnapshotViewModel<HoursStatementDto>({ selected.value.range(today()).let { (f, t) -> data.hoursStatement(customerId, f, t) } }, refreshOn) {
    constructor(data: OwnerData, customerId: String, refreshOn: Flow<Unit>, today: () -> LocalDate = { LocalDate.now() }) :
        this(data, customerId, MutableStateFlow(StatementPeriod.THIS_MONTH), today, refreshOn)

    val period: StateFlow<StatementPeriod> get() = selected
    private val _pdf = MutableStateFlow(PdfState())
    val pdf: StateFlow<PdfState> = _pdf.asStateFlow()

    fun select(p: StatementPeriod) {
        if (selected.value == p) return
        selected.value = p
        refresh()
    }

    fun downloadPdf() {
        if (_pdf.value.busy) return
        _pdf.value = PdfState(busy = true)
        val (from, to) = selected.value.range(today())
        viewModelScope.launch {
            _pdf.value = when (val r = data.hoursStatementPdf(customerId, from, to)) {
                is ActionResult.Done -> PdfState(bytes = r.value)
                is ActionResult.Refused -> PdfState(error = r.error.message.takeIf { r.code != null } ?: T.STMT_PDF_FAILED)
            }
        }
    }

    fun pdfHandled(error: String? = null) {
        _pdf.value = PdfState(error = error)
    }
}

// --- screens ---------------------------------------------------------------------------------------------------------

@Composable
fun CustomerHoursScreen(vm: CustomerHoursViewModel, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { rows ->
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
            if (rows.isEmpty()) {
                item { EmptyState(T.HOURS_EMPTY) }
                return@LazyColumn
            }
            groupedSection(
                keyPrefix = "hours", header = null, footer = T.HOURS_LIST_FOOTER,
                items = rows.map { p ->
                    GroupedItem(p.id, onClick = { onOpen(OwnerDestination.HoursPurchase(p.id)) }) {
                        Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(T.hoursRow(p.purchaseNumber, HoursPresentation.customer(p)), style = AssetaType.headline)
                            Text(HoursPresentation.machine(p), style = AssetaType.subheadline, color = palette.secondaryText)
                            Text(HoursPresentation.leftLine(p.totals.remaining, p.totals.provisional), style = AssetaType.caption, color = palette.secondaryText)
                        }
                    }
                },
            )
        }
    }
}

@Composable
fun HoursPurchaseScreen(vm: HoursPurchaseViewModel, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { p ->
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
            item {
                SectionCard(T.HOURS_HOURS, footer = T.HOURS_PROVISIONAL_FOOTER) {
                    Text(p.purchaseNumber, style = AssetaType.headline)
                    HoursPresentation.purchaseRows(p).forEach { (l, v) -> KeyValue(l, v) }
                }
            }
            val machines = HoursPresentation.machineRows(p)
            if (machines.isNotEmpty()) item { SectionCard(T.HOURS_MACHINES) { machines.forEach { (l, v) -> KeyValue(l, v) } } }
            item {
                SectionCard(null) {
                    NavigationRow(T.HOURS_OPEN_STATEMENT) { onOpen(OwnerDestination.HoursStatement(p.customerId, p.customerName)) }
                }
            }
        }
    }
}

@Composable
fun HoursStatementScreen(vm: HoursStatementViewModel, online: Boolean, customerName: String?) {
    val state by vm.state.collectAsStateWithLifecycle()
    val period by vm.period.collectAsStateWithLifecycle()
    val pdf by vm.pdf.collectAsStateWithLifecycle()
    val context = LocalContext.current
    LaunchedEffect(pdf.bytes) {
        val bytes = pdf.bytes ?: return@LaunchedEffect
        vm.pdfHandled(StatementPdf.open(context, bytes))
    }
    Column(Modifier.fillMaxSize()) {
        FilterChipRow(StatementPeriod.entries.map { it to it.label }, period, vm::select)
        SnapshotScaffold(state, vm::refresh) { s ->
            val zone = ZoneId.systemDefault()
            LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
                item {
                    SectionCard(T.STMT_TOTALS) {
                        Text(HoursPresentation.header(s, customerName), style = AssetaType.headline)
                        HoursPresentation.totals(s).forEach { (l, v) -> KeyValue(l, v) }
                    }
                }
                item {
                    SectionCard(T.STMT_USAGE) {
                        val lines = HoursPresentation.usage(s)
                        if (lines.isEmpty()) FootNote(T.STMT_USAGE_EMPTY)
                        lines.forEach { u ->
                            Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                KeyValue(u.label, u.value)
                                Text(u.caption, style = AssetaType.caption, color = palette.secondaryText)
                            }
                        }
                    }
                }
                item {
                    SectionCard(null, footer = T.stmtFooter(s.timezone, OwnerFormat.dateTime(s.generatedAt, zone))) {
                        Button(
                            vm::downloadPdf, enabled = online && !pdf.busy,
                            modifier = Modifier.fillMaxWidth().testTag("statement-pdf"), shape = RoundedCornerShape(8.dp),
                        ) { Text(T.STMT_OPEN_PDF) }
                        pdf.error?.let { Text(it, style = AssetaType.caption, color = OwnerColors.Critical) }
                    }
                }
            }
        }
    }
}

/** Saves the statement PDF in the app cache (one file, overwritten) and opens it in the phone's PDF viewer. */
object StatementPdf {
    private const val DIR = "statements"
    private const val NAME = "hours-statement.pdf"

    /** Null when opened, else the message to show. */
    suspend fun open(context: Context, bytes: ByteArray): String? {
        val file = withContext(Dispatchers.IO) {
            runCatching { File(context.cacheDir, DIR).apply { mkdirs() }.resolve(NAME).apply { writeBytes(bytes) } }.getOrNull()
        } ?: return T.STMT_PDF_FAILED
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        val intent = Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/pdf")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            context.startActivity(intent)
            null
        } catch (_: ActivityNotFoundException) {
            T.STMT_NO_PDF_APP
        }
    }
}
