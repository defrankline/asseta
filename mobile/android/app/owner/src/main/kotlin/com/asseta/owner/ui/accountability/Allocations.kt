package com.asseta.owner.ui.accountability

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.groupedSection
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import kotlinx.coroutines.flow.Flow
import java.time.LocalDate
import com.asseta.core.domain.accountability.DisplayNames
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.AllocationDayDto
import com.asseta.core.model.owner.ReportAllocationDto
import com.asseta.core.model.owner.WorkAllocationDto
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.MachineDayAllocations
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.ScreenState
import com.asseta.owner.ui.common.SectionCard
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull

/** Wording of daily reports, work allocations and value at risk (keys `owner.report.*`, `owner.allocation.*`, same on iOS). */
object AllocationTexts {
    const val REPORT_SECTION = "Daily reports to review"
    const val REPORT_EMPTY = "No daily reports waiting."
    const val REPORT_TITLE = "Daily report"
    const val FIGURES = "Figures"
    const val MACHINE = "Machine"
    const val DAY = "Day"
    const val OPENING = "Opening reading"
    const val CLOSING = "Closing reading"
    const val TOTAL = "Total hours"
    const val BILLABLE = "Billable hours"
    const val UNBILLABLE = "Unbillable hours"
    const val NOT_ACCOUNTED = "Not accounted for"
    const val REASONS = "Unbillable hours by reason"
    const val ALLOCATIONS = "Hours by customer"
    const val NOTE = "Supervisor's note"
    const val SUBMITTED_BY = "Sent by"
    const val SUBMITTED = "Sent"
    const val FLAG_LATE = "Sent after the daily cut-off"
    const val FLAG_REPEAT = "Repeat report for this day"
    const val REPLACES = "Replaces an earlier report"
    const val EVIDENCE = "Evidence"
    const val REVIEW = "Review"
    const val REVIEW_FOOTER = "Someone other than the sender reviews a report. Sending it back asks the sender to correct it."
    const val NOTE_LABEL = "Note (at least 5 characters)"
    const val MARK_REVIEWED = "Mark as reviewed"
    const val SEND_BACK = "Send back"
    const val REVIEWED = "Marked as reviewed."
    const val SENT_BACK = "Sent back to the supervisor."
    const val OWN = "You sent this report, so someone else must review it."
    const val REVIEWED_BY = "Reviewed by"
    const val REVIEW_NOTE = "Review note"
    const val STATUS = "Status"

    const val SECTION = "Work allocation corrections"
    const val EMPTY = "No corrections waiting."
    const val TITLE = "Work allocation correction"
    const val ORIGINAL = "Now recorded as"
    const val DAY_CARD = "Hours allocated"
    const val DAY_TOTAL = "Engine hours"
    const val DAY_CUSTOMER = "Customer work"
    const val DAY_AUTHORIZED = "Authorized activity"
    const val DAY_UNEXPLAINED = "Unexplained"
    const val DAY_ALLOCATED = "Allocated"
    const val DAY_DIFFERENCE = "Difference"
    const val DAY_RECONCILED = "Every engine hour is allocated."
    const val DAY_NOT_RECONCILED = "Some engine hours are not allocated yet."
    const val ENTRIES = "Work allocations"
    const val ENTRIES_EMPTY = "No allocations for this day."
    const val DAYS_EMPTY = "No engine hours in the last 14 days."
    const val VALUE_AT_RISK = "Value at risk"
    const val VALUE_AT_RISK_FOOTER = "Unexplained hours at the job's rate. Not part of expected revenue or the shortfall."

    fun status(wire: String): String = when (wire) {
        "SUBMITTED" -> "To review"
        "REVIEWED" -> "Reviewed"
        "RETURNED" -> "Sent back"
        "SUPERSEDED" -> "Replaced"
        else -> OwnerFormat.humanize(wire)
    }

    fun kind(wire: String): String = when (wire) {
        WorkAllocationDto.CUSTOMER_WORK -> DAY_CUSTOMER
        WorkAllocationDto.AUTHORIZED_ACTIVITY -> DAY_AUTHORIZED
        WorkAllocationDto.UNEXPLAINED -> DAY_UNEXPLAINED
        else -> OwnerFormat.humanize(wire)
    }

    fun part(kind: String) = "Proposed: ${kind(kind)}"

    fun partValue(hours: String, who: String?) = listOfNotNull(hours, who?.takeIf { it.isNotBlank() }).joinToString(" · ")

    fun reportRow(machine: String, date: String) = "$machine · $date"

    fun reportLine(total: String, billable: String, unbillable: String) = "$total h in total · $billable h billable · $unbillable h unbillable"

    fun correctionRow(machine: String, date: String, hours: String) = "$machine · $date · $hours h"

    fun entryLine(start: String, end: String, hours: String) = "$start → $end · $hours h"

    fun dayLine(engine: String, allocated: String) = "$engine h engine · $allocated h allocated"

    fun dayUnexplained(hours: String) = "$hours h unexplained"

    fun lotLine(purchase: String, hours: String) = "From $purchase: $hours h"

    /** The refusal in plain words ([fallback]: the server's message). */
    fun error(code: String?, fallback: String): String = when (code) {
        "REPORT_ALREADY_REVIEWED" -> "This report was already reviewed or replaced. Reload to see it."
        "SEGREGATION_OF_DUTIES" -> OWN
        "ALLOCATION_NOT_ACTIVE" -> "The original entry has changed. Reload to see it."
        "ALLOCATION_CORRECTION_PENDING" -> "Another correction of this entry is already waiting."
        else -> fallback
    }
}

/** Pure presentation of the ledger (unit-tested). */
object AllocationPresentation {
    private val A = AllocationTexts
    private val R = RevenuePresentation

    /** Customer + job, the reason or activity of authorized time, nothing for unexplained time. */
    fun who(kind: String, customer: String?, job: String?, reason: String?, activity: String?): String? = when (kind) {
        WorkAllocationDto.CUSTOMER_WORK -> listOfNotNull(customer, job).joinToString(" · ").ifEmpty { null }
        WorkAllocationDto.AUTHORIZED_ACTIVITY -> reason ?: activity?.let(OwnerFormat::humanize)
        else -> null
    }

    fun who(a: WorkAllocationDto) = who(a.kind, DisplayNames.of(a.customerName, a.customerId), a.jobNumber, a.reasonName, a.activityType)

    fun who(a: ReportAllocationDto) = who(a.kind, DisplayNames.of(a.customerName, a.customerId), a.jobNumber, null, a.activityType)

    fun dayRows(d: AllocationDayDto): List<Pair<String, String>> = listOf(
        A.DAY_TOTAL to R.hours(d.totalEngineHours),
        A.DAY_CUSTOMER to R.hours(d.customerHours),
        A.DAY_AUTHORIZED to R.hours(d.authorizedHours),
        A.DAY_UNEXPLAINED to R.hours(d.unexplainedHours),
        A.DAY_ALLOCATED to R.hours(d.allocatedHours),
        A.DAY_DIFFERENCE to R.hours(d.differenceHours),
    )

    fun lots(a: WorkAllocationDto): List<String> = a.lots.map { A.lotLine(DisplayNames.or(it.purchaseNumber, it.purchaseId), R.num(it.hours)) }

    /** `value_at_risk` of a dashboard tile: one row per currency, none when empty. */
    fun valueAtRiskRows(tile: JsonObject): List<Pair<String, String>> =
        (tile["value_at_risk"] as? JsonArray).orEmpty().mapNotNull { it as? JsonObject }.mapNotNull { v ->
            val currency = (v["currency"] as? JsonPrimitive)?.contentOrNull ?: return@mapNotNull null
            A.VALUE_AT_RISK to R.money((v["amount"] as? JsonPrimitive)?.contentOrNull, currency)
        }
}

/** The ledger's two cards on the machine day ([state] null: the role cannot read the ledger or ENGINE_HOURS is off). */
@Composable
fun AllocationCards(state: ScreenState<MachineDayAllocations>) {
    val data = state.data
    if (data == null) {
        state.error?.let { SectionCard(AllocationTexts.DAY_CARD) { FootNote(it.message) } }
        return
    }
    AllocationCards(data)
}

@Composable
fun AllocationCards(data: MachineDayAllocations) {
    val T = AllocationTexts
    data.day?.let { d ->
        SectionCard(T.DAY_CARD, footer = if (d.reconciled) T.DAY_RECONCILED else T.DAY_NOT_RECONCILED) {
            AllocationPresentation.dayRows(d).forEach { (l, v) -> KeyValue(l, v) }
        }
    }
    SectionCard(T.ENTRIES) {
        if (data.entries.isEmpty()) FootNote(T.ENTRIES_EMPTY)
        data.entries.forEach { a ->
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(T.kind(a.kind), style = AssetaType.headline, color = if (a.kind == WorkAllocationDto.UNEXPLAINED) OwnerColors.Warning else androidx.compose.ui.graphics.Color.Unspecified)
                AllocationPresentation.who(a)?.let { Text(it, style = AssetaType.subheadline) }
                Text(T.entryLine(RevenuePresentation.num(a.startReading), RevenuePresentation.num(a.endReading), RevenuePresentation.num(a.hours)), style = AssetaType.subheadline, color = palette.secondaryText)
                AllocationPresentation.lots(a).forEach { Text(it, style = AssetaType.caption, color = palette.secondaryText) }
            }
        }
    }
}

// --- machine days while revenue checks are off: the ledger alone, no money ------------------------------------------

/** The last 14 local days of the ledger of one machine (the daily sheet needs revenue checks on). */
class LedgerDaysViewModel(data: OwnerData, val machineId: String, refreshOn: Flow<Unit>, today: () -> LocalDate = { LocalDate.now() }) :
    SnapshotViewModel<List<AllocationDayDto>>({
        val (from, to) = RevenuePresentation.window(today())
        data.allocationDays(machineId, from, to)
    }, refreshOn)

class LedgerDayViewModel(data: OwnerData, machineId: String, day: String, refreshOn: Flow<Unit>) :
    SnapshotViewModel<MachineDayAllocations>({ data.machineDayAllocations(machineId, day) }, refreshOn)

@Composable
fun LedgerDaysScreen(vm: LedgerDaysViewModel, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val T = AllocationTexts
    val R = RevenuePresentation
    SnapshotScaffold(state, vm::refresh) { days ->
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
            if (days.isEmpty()) {
                item { EmptyState(T.DAYS_EMPTY) }
                return@LazyColumn
            }
            groupedSection(
                keyPrefix = "ledger-days", header = null,
                items = days.map { d ->
                    GroupedItem(d.day, onClick = { onOpen(OwnerDestination.SheetDay(d.machineId, d.day)) }) {
                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(R.day(d.day), style = AssetaType.headline)
                            Text(T.dayLine(R.num(d.totalEngineHours), R.num(d.allocatedHours)), style = AssetaType.subheadline, color = palette.secondaryText)
                            if (R.nonZero(d.unexplainedHours)) Text(T.dayUnexplained(R.num(d.unexplainedHours)), style = AssetaType.caption, color = OwnerColors.Warning)
                        }
                    }
                },
            )
        }
    }
}

@Composable
fun LedgerDayScreen(vm: LedgerDayViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { data ->
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
            item { AllocationCards(data) }
        }
    }
}
