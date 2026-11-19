package com.asseta.owner.ui.machines

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.Connectivity
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.domain.accountability.CustomerHoursPolicy
import com.asseta.core.domain.reports.MachineReportRules
import com.asseta.core.domain.reports.ReportState
import com.asseta.core.map.MachineMap
import com.asseta.core.map.MapMarker
import com.asseta.core.model.owner.MachineMapDto
import com.asseta.core.model.sync.MachineReportDto
import com.asseta.core.model.sync.MachineReportStatusDto
import com.asseta.core.ui.shell.PeriodTabs
import com.asseta.core.ui.shell.PillTone
import com.asseta.core.ui.shell.SectionLabel
import com.asseta.core.ui.shell.StatusPill
import com.asseta.owner.data.OwnerData
import com.asseta.owner.data.ReportReminder
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.common.CardDetail
import com.asseta.owner.ui.common.CardGap
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.Figures
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.ItemCard
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.Period
import com.asseta.owner.ui.common.Section
import com.asseta.owner.ui.common.StaleBanner
import com.asseta.owner.ui.fleet.FleetRows
import com.asseta.owner.ui.reports.ReportPresentation
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.launch
import java.math.BigDecimal
import java.time.LocalDate

/** Machines wording (design OwnerMachines; same as iOS). */
object MachinesTexts {
    const val MAP = "Map"
    const val LIST = "List"
    const val THIS_WEEK = "THIS WEEK"
    const val NO_MACHINES = "No machines to show."
    const val MAP_EMPTY = "No machine has a known position."

    fun noReport(days: Int) = "No report ${Figures.days(days)}"
    const val NO_REPORT_YET = "No report yet"
    const val REJECTED = "Rejected"

    /** The pill of a machine that needs a report: "No report 4 days", "No report yet" (never reported / no starting reading), "Rejected". */
    fun pill(s: MachineReportStatusDto, reminderDays: Int?): String {
        val days = s.daysSinceReport
        val state = ReportPresentation.reportState(s, reminderDays)
        return when {
            // A rejected report is final: the machine is due again (a new report with a new reading).
            state == ReportState.DUE && s.rejectedReportId != null -> REJECTED
            state == ReportState.OPENING -> NO_REPORT_YET
            else -> if (days == null || days <= 0) NO_REPORT_YET else noReport(days)
        }
    }
    /** The row's supervisor by first name (design "Daudi"); null when there is none. */
    fun firstName(name: String?): String? = name?.trim()?.split(Regex("\\s+"))?.firstOrNull()?.takeIf { it.isNotEmpty() }

    fun tracker(engine: String, motion: String) ="Tracker: engine ${engine.lowercase()} · ${motion.lowercase()}"
}

/** One machine of the week (design: "300 h · 220 productive · last reading 1,510 h (pending)"). */
data class MachineWeek(
    val machineId: String,
    val title: String,
    /** The supervisor, or "No report 3 days" when the machine is overdue. */
    val subtitle: String?,
    val detail: String,
    val overdue: Boolean,
    val hours: BigDecimal,
    val productive: BigDecimal,
    /** Where a tap leads: the machine (fleet) or its report waiting. */
    val open: OwnerDestination?,
)

/** Pure per-machine aggregation of the week's reports (rejected ones left out; unit-tested). */
object MachinesPresentation {
    fun rows(
        statuses: List<MachineReportStatusDto>,
        reports: List<MachineReportDto>,
        fleet: List<MachineMapDto>,
        features: OwnerFeatures,
        /** The company's machine_report_reminder_days (null = reminders off). */
        reminderDays: Int? = CustomerHoursPolicy.DEFAULT_REMINDER_DAYS,
    ): List<MachineWeek> {
        val counted = reports.filter { it.status != MachineReportDto.REJECTED }
        val byMachine = counted.groupBy { it.machineId }
        val fleetById = fleet.associateBy { it.machineId.toString() }
        val ids = (statuses.map { it.machineId } + byMachine.keys).distinct()
        return ids.map { id ->
            val status = statuses.firstOrNull { it.machineId == id }
            val week = byMachine[id].orEmpty()
            val map = fleetById[id]
            val hours = Figures.sum(week.map { it.hours })
            val productive = Figures.sum(week.map { it.customerHours })
            val code = status?.machineCode ?: week.firstOrNull()?.machineCode ?: map?.assetCode ?: id.take(8)
            val name = status?.machineName ?: week.firstOrNull()?.machineName ?: map?.name
            val overdue = status != null && ReportPresentation.isOverdue(status, reminderDays)
            val latest = week.maxByOrNull { it.submittedAt }
            val reading = when {
                latest != null && latest.status == MachineReportDto.SUBMITTED -> "last reading ${MachineReportRules.formatHours(Figures.dec(latest.endReading))} h (pending)"
                latest != null -> "last reading ${MachineReportRules.formatHours(Figures.dec(latest.endReading))} h"
                status?.lastApprovedReading != null -> "last reading ${MachineReportRules.formatHours(Figures.dec(status.lastApprovedReading))} h"
                else -> null
            }
            val detail = if (overdue && week.isEmpty()) {
                map?.takeIf { features.tracking }?.let { MachinesTexts.tracker(OwnerFormat.humanize(it.observedEngine), OwnerFormat.humanize(it.observedMotion)) }
                    ?: (reading ?: ReportPresentation.overdueDetail(status!!))
            } else {
                listOfNotNull(Figures.hours(hours), "${MachineReportRules.formatHours(productive)} productive", reading).joinToString(" · ")
            }
            MachineWeek(
                machineId = id,
                title = listOfNotNull(code, name).joinToString(" · "),
                subtitle = if (overdue) MachinesTexts.pill(status!!, reminderDays) else MachinesTexts.firstName(map?.supervisor),
                detail = detail,
                overdue = overdue,
                hours = hours,
                productive = productive,
                open = when {
                    features.fleet -> OwnerDestination.Machine(id)
                    status?.pendingReportId != null && features.machineReports -> OwnerDestination.MachineReport(status.pendingReportId!!)
                    else -> null
                },
            )
        }.sortedWith(compareByDescending<MachineWeek> { it.overdue }.thenByDescending { it.hours }.thenBy { it.title })
    }
}

class MachinesViewModel(data: OwnerData, features: OwnerFeatures, refreshOn: Flow<Unit>, today: () -> LocalDate = { LocalDate.now() }) : ViewModel() {
    private val week = Period.WEEK.range(today())
    val fleet: Section<List<MachineMapDto>>? = if (features.fleet) Section(viewModelScope) { data.fleet() } else null
    val statuses: Section<List<MachineReportStatusDto>>? = if (features.machineReports) Section(viewModelScope) { data.machineReportStatus() } else null
    val reports: Section<List<MachineReportDto>>? = if (features.machineReports) Section(viewModelScope) { data.machineReportsBetween(week.from, week.to) } else null
    /** The company's reminder days (CUSTOMER_HOURS); 3 until read or when it cannot be read. */
    val reminder: Section<ReportReminder>? = if (features.machineReports) Section(viewModelScope) { data.reportReminder() } else null
    private val all = listOfNotNull(fleet, statuses, reports, reminder)

    init {
        refresh()
        viewModelScope.launch { refreshOn.collect { refresh() } }
    }

    fun refresh() = all.forEach { it.refresh() }
}

@Composable
fun MachinesScreen(vm: MachinesViewModel, features: OwnerFeatures, now: () -> Long, onOpen: (OwnerDestination) -> Unit) {
    var showMap by rememberSaveable { mutableStateOf(features.fleet) }
    val fleetState = vm.fleet?.state?.collectAsStateWithLifecycle()?.value
    val statusState = vm.statuses?.state?.collectAsStateWithLifecycle()?.value
    val reportState = vm.reports?.state?.collectAsStateWithLifecycle()?.value
    val fleet = fleetState?.data.orEmpty()
    val reminder = vm.reminder?.state?.collectAsStateWithLifecycle()?.value?.data
    val rows = MachinesPresentation.rows(statusState?.data.orEmpty(), reportState?.data.orEmpty(), fleet, features, ReportPresentation.reminderDays(reminder))
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 24.dp)) {
        if (features.fleet) item { PeriodTabs(listOf(true to MachinesTexts.MAP, false to MachinesTexts.LIST), showMap, { showMap = it }) }
        if (showMap && fleetState != null) {
            item {
                val snap = fleetState.snapshot
                val markers = if (snap == null) emptyList() else FleetRows.build(fleet, snap.source, snap.fetchedAtMs, now()).filter { it.machine.hasPosition }.map {
                    MapMarker(
                        it.machine.machineId.toString(), it.machine.latitude!!, it.machine.longitude!!,
                        OwnerColors.connectivity(it.connectivity), it.machine.name,
                        code = it.machine.assetCode, alerts = it.machine.openAlerts, live = it.connectivity == Connectivity.LIVE,
                    )
                }
                Column(Modifier.padding(horizontal = 20.dp, vertical = 12.dp)) {
                    StaleBanner(snap)
                    Box(Modifier.fillMaxWidth().height(280.dp).clip(RoundedCornerShape(18.dp))) {
                        MachineMap(markers, "Map with ${markers.size} machines. Use the List for details.", Modifier.fillMaxSize()) { onOpen(OwnerDestination.Machine(it)) }
                    }
                    if (snap != null && markers.isEmpty()) FootNote(MachinesTexts.MAP_EMPTY)
                    fleetState.error?.takeIf { fleetState.data == null }?.let { FootNote(it.message) }
                }
            }
        }
        if (features.machineReports) {
            item { SectionLabel(MachinesTexts.THIS_WEEK) }
            listOfNotNull(statusState?.error, reportState?.error).firstOrNull()?.takeIf { statusState?.data == null || reportState?.data == null }?.let { e ->
                item { Column(Modifier.padding(horizontal = 20.dp)) { FootNote(e.message) } }
            }
            if (rows.isEmpty() && statusState?.loading == false) item { EmptyState(MachinesTexts.NO_MACHINES) }
            rows.forEach { r ->
                item(key = r.machineId) {
                    ItemCard(onClick = r.open?.let { d -> { onOpen(d) } }) {
                        Row(Modifier.fillMaxWidth()) {
                            Text(r.title, fontSize = 16.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                            r.subtitle?.let { if (r.overdue) StatusPill(it, PillTone.BAD) else Text(it, fontSize = 13.sp, color = com.asseta.core.ui.theme.palette.secondaryText) }
                        }
                        CardDetail(r.detail, accent = !r.overdue)
                    }
                    CardGap()
                }
            }
        }
    }
}
