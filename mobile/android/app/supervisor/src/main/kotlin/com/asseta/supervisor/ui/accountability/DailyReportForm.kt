package com.asseta.supervisor.ui.accountability

import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.accountability.AccountabilityRules
import com.asseta.core.domain.accountability.DailyReportDraft
import com.asseta.core.domain.accountability.DailyReportRules
import com.asseta.core.domain.accountability.ReportReading
import com.asseta.core.domain.accountability.TenantZone
import com.asseta.core.domain.accountability.UnbillableDraft
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.owner.EngineHourReasonDto
import com.asseta.core.sync.data.IsoTime
import com.asseta.core.sync.usecase.DailyReportRequest
import com.asseta.core.ui.components.FilterChipRow
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.capture.CapturedPhoto
import com.asseta.supervisor.ui.LabeledRow
import com.asseta.supervisor.ui.LocalTime
import com.asseta.supervisor.ui.NoticeCard
import com.asseta.supervisor.ui.Section
import com.asseta.supervisor.ui.finance.DecimalField
import com.asseta.supervisor.ui.finance.PickerOption
import com.asseta.supervisor.ui.finance.SaveSection
import com.asseta.supervisor.ui.finance.SaveState
import com.asseta.supervisor.ui.finance.SearchablePickerField
import com.asseta.supervisor.ui.finance.TextInput
import com.asseta.supervisor.ui.finance.after
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.util.UUID

private val T = DailyReportTexts

data class DailyReportForm(
    val loading: Boolean = true,
    val blocked: String? = null,
    val machineLabel: String = "",
    val day: String = "",
    val dayFixed: Boolean = false,
    val days: List<String> = emptyList(),
    /** Every counted reading of the machine, newest first. */
    val readings: List<ReportReading> = emptyList(),
    val openingRef: String? = null,
    val closingRef: String? = null,
    val billable: String = "",
    val lines: List<UnbillableDraft> = emptyList(),
    val note: String = "",
    val photos: List<CapturedPhoto> = emptyList(),
    val repeat: Boolean = false,
    val supersedesId: String? = null,
    val evidenceRequired: Boolean = false,
    val reasons: List<EngineHourReasonDto> = emptyList(),
) {
    private fun value(id: String?) = readings.firstOrNull { it.id == id }?.reading

    val total get() = DailyReportRules.total(value(openingRef), value(closingRef))
    val notAccounted get() = DailyReportRules.notAccounted(total, billable, lines)

    fun draft() = DailyReportDraft(openingRef, closingRef, value(openingRef), value(closingRef), billable, lines, note, photos.size, evidenceRequired)
}

/** The form of one visit: its client id makes the report exactly-once. [supersedesKey]: the sent-back report it replaces. */
class DailyReportFormViewModel(
    private val field: FieldGraph,
    private val tenantId: String,
    private val machineId: String,
    private val supersedesKey: String?,
    private val permissions: Set<String>,
    private val device: ZoneId = ZoneId.systemDefault(),
) : ViewModel() {
    /** Days are the tenant's, as the server counts them; the phone's zone only until the server has named one. */
    private var zone: ZoneId = device
    private val clientId = UUID.randomUUID().toString()
    private val _form = MutableStateFlow(DailyReportForm())
    val form: StateFlow<DailyReportForm> = _form.asStateFlow()
    private val _save = MutableStateFlow(SaveState())
    val save: StateFlow<SaveState> = _save.asStateFlow()

    init {
        viewModelScope.launch { load() }
    }

    private fun applyAccess() = viewModelScope.launch {
        val access = field.accountability.access(tenantId, permissions)
        _form.update { it.copy(evidenceRequired = access.dailyReportEvidenceRequired, reasons = field.accountability.cache.value.unbillableReasons) }
    }

    private suspend fun load() {
        val access = field.accountability.access(tenantId, permissions)
        if (!access.dailyReport) return _form.update { it.copy(loading = false, blocked = T.NOT_FOUND_HINT) }
        zone = TenantZone.resolve(
            listOf(field.online.savedCash(tenantId)?.value?.reconciliations?.firstOrNull()?.timezone, field.accountability.cache.value.siteCheckins?.timezone),
            device,
        )
        val snapshot = field.inbox.observe(tenantId).first()
        val machine = snapshot.machines[machineId]
        val readings = snapshot.readings.filter { snapshot.machineOf(it) == machineId && it.counts }
            .map { ReportReading(it.id, it.reading, it.atMs, it.server != null || it.op?.status == ClientOperationStatus.ACKED) }
            .sortedByDescending { it.atMs }
        val today = Instant.ofEpochMilli(field.clock.nowMs()).atZone(zone).toLocalDate()
        _form.update {
            it.copy(
                machineLabel = machine?.let { m -> "${m.assetCode} · ${m.name}" }.orEmpty(), readings = readings, day = today.toString(),
                days = (0L..2L).map { n -> today.minusDays(n).toString() },
                evidenceRequired = access.dailyReportEvidenceRequired, reasons = field.accountability.cache.value.unbillableReasons,
            )
        }
        val old = supersedesKey?.let { field.dailyReports.report(tenantId, it) }
        if (old != null) {
            val dayStart = LocalDate.parse(old.reportDate).atStartOfDay(zone).toInstant().toEpochMilli()
            _form.update { f ->
                val known = f.readings.map { it.id }.toSet()
                val extra = listOf(old.openingRef to old.openingReading, old.closingRef to old.closingReading)
                    .filter { it.first !in known }.map { (id, r) -> ReportReading(id, r, dayStart, synced = true) }
                f.copy(
                    loading = false, day = old.reportDate, dayFixed = true, supersedesId = old.id, readings = (f.readings + extra).sortedByDescending { it.atMs },
                    openingRef = old.openingRef, closingRef = old.closingRef, billable = plain(old.billableHours),
                    lines = old.unbillable.map { UnbillableDraft(it.reasonId, plain(it.hours)) }, note = old.note.orEmpty(),
                )
            }
        } else {
            selectDay(_form.value.day)
            _form.update { it.copy(loading = false) }
        }
        // Newest reasons and policy, when the phone can reach the server; the form already works from the saved copy.
        if (field.accountability.refresh(tenantId, permissions)) applyAccess()
    }

    private fun plain(raw: String) = raw.toBigDecimalOrNull()?.let(AccountabilityRules::plain) ?: raw

    private fun dayBounds(day: String): Pair<Long, Long> {
        val date = LocalDate.parse(day)
        return date.atStartOfDay(zone).toInstant().toEpochMilli() to date.plusDays(1).atStartOfDay(zone).toInstant().toEpochMilli()
    }

    /** Readings offered for the day: at most its end, newest first (bounded so the picker stays short). */
    fun candidates(f: DailyReportForm): List<ReportReading> {
        if (f.day.isEmpty()) return emptyList()
        return f.readings.filter { it.atMs < dayBounds(f.day).second }.take(MAX_CANDIDATES)
    }

    fun selectDay(day: String) {
        if (_form.value.dayFixed) return
        val (start, end) = dayBounds(day)
        _form.update { f ->
            val (opening, closing) = DailyReportRules.prefill(f.readings, start, end)
            f.copy(day = day, openingRef = opening, closingRef = closing, repeat = false)
        }
        viewModelScope.launch {
            val server = field.dailyReports.prefill(machineId, day) ?: return@launch
            _form.update { f ->
                if (f.day != day) return@update f
                fun at(raw: String?) = raw?.let { runCatching { IsoTime.parse(it).toEpochMilli() }.getOrNull() } ?: start
                val known = f.readings.map { it.id }.toSet()
                val extra = listOfNotNull(
                    server.openingRef?.takeIf { it !in known }?.let { ReportReading(it, server.openingReading.orEmpty(), at(server.openingAt), true) },
                    server.closingRef?.takeIf { it !in known && it != server.openingRef }?.let { ReportReading(it, server.closingReading.orEmpty(), at(server.closingAt), true) },
                )
                f.copy(
                    readings = (f.readings + extra).sortedByDescending { it.atMs },
                    openingRef = f.openingRef ?: server.openingRef, closingRef = f.closingRef ?: server.closingRef,
                    repeat = server.existingReportIds.isNotEmpty(),
                )
            }
        }
    }

    fun edit(change: (DailyReportForm) -> DailyReportForm) = _form.update(change)

    fun onPhotoError(message: String) = _save.update { it.copy(messages = listOf("The photo could not be saved: $message")) }

    fun save() {
        if (_save.value.saving) return
        val f = _form.value
        _save.update { it.copy(saving = true, messages = emptyList()) }
        viewModelScope.launch {
            val result = field.dailyReportCapture.submit(
                DailyReportRequest(tenantId, clientId, machineId, f.day, f.draft(), f.photos.map { it.jpeg }, f.supersedesId, field.clock.nowMs()),
            )
            _save.update { it.after(result) }
        }
    }

    private companion object {
        const val MAX_CANDIDATES = 30
    }
}

@Composable
fun DailyReportFormScreen(vm: DailyReportFormViewModel, onDone: () -> Unit) {
    val f by vm.form.collectAsStateWithLifecycle()
    val save by vm.save.collectAsStateWithLifecycle()
    if (f.loading) return
    val editable = !save.saving && !save.saved
    FormColumn {
        f.blocked?.let {
            NoticeCard(T.NOT_FOUND, it, isError = true)
            return@FormColumn
        }
        Section(null, footer = if (f.supersedesId != null) T.RESUBMIT_FOOTER else null) {
            LabeledRow(T.MACHINE, f.machineLabel)
            if (f.dayFixed) LabeledRow(T.DAY, T.date(f.day))
        }
        if (!f.dayFixed) FilterChipRow(f.days.map { it to T.date(it) }, f.day, vm::selectDay)
        if (f.repeat && f.supersedesId == null) Text(T.REPEAT_WARNING, color = palette.warning)
        val options = vm.candidates(f).map { PickerOption(it.id, T.readingOption(it.reading, LocalTime.format(it.atMs), it.synced)) }
        Section(T.READINGS, footer = T.READINGS_FOOTER) {
            if (options.isEmpty()) Text(T.NO_READINGS, color = palette.secondaryText)
            Text(T.OPENING)
            SearchablePickerField(T.CHOOSE_READING, options, f.openingRef, { v -> vm.edit { it.copy(openingRef = v) } }, emptyText = T.NO_READINGS, enabled = editable)
            Text(T.CLOSING)
            SearchablePickerField(T.CHOOSE_READING, options, f.closingRef, { v -> vm.edit { it.copy(closingRef = v) } }, emptyText = T.NO_READINGS, enabled = editable)
            f.total?.let { LabeledRow(T.TOTAL, "${T.hours(it)} h") }
        }
        Section(T.BILLABLE_HOURS, footer = T.BILLABLE_FOOTER) {
            DecimalField(T.BILLABLE, f.billable, { v -> vm.edit { it.copy(billable = v) } }, editable)
        }
        Section(T.UNBILLABLE) {
            val reasons = f.reasons.map { PickerOption(it.id, it.name, it.description) }
            if (reasons.isEmpty()) Text(T.REASONS_EMPTY, color = palette.secondaryText)
            f.lines.forEachIndexed { i, line ->
                SearchablePickerField(T.CHOOSE_REASON, reasons, line.reasonId, { v -> vm.edit { it.copy(lines = it.lines.replaced(i, line.copy(reasonId = v))) } }, emptyText = T.REASONS_EMPTY, enabled = editable)
                DecimalField(T.REASON_HOURS, line.hoursText, { v -> vm.edit { it.copy(lines = it.lines.replaced(i, line.copy(hoursText = v))) } }, editable)
                if (editable) TextButton(onClick = { vm.edit { it.copy(lines = it.lines.filterIndexed { j, _ -> j != i }) } }) { Text(T.REMOVE, color = palette.offline) }
            }
            if (editable && reasons.isNotEmpty() && f.lines.size < DailyReportRules.MAX_LINES) {
                TextButton(onClick = { vm.edit { it.copy(lines = it.lines + UnbillableDraft(null, "")) } }) { Text(T.ADD_REASON) }
            }
            f.notAccounted?.takeIf { it.signum() != 0 }?.let { LabeledRow(T.NOT_ACCOUNTED, "${T.hours(it)} h") }
        }
        Section(null) { TextInput(T.NOTE, f.note, { v -> vm.edit { it.copy(note = v.take(DailyReportRules.MAX_NOTE)) } }, editable, singleLine = false) }
        EvidencePhotos(
            f.photos, { p -> vm.edit { it.copy(photos = (it.photos + p).take(DailyReportRules.MAX_PHOTOS)) } },
            { i -> vm.edit { it.copy(photos = it.photos.filterIndexed { j, _ -> j != i }) } }, vm::onPhotoError, editable,
            title = if (f.evidenceRequired) T.PHOTO_REQUIRED else T.PHOTO_OPTIONAL, footer = T.PHOTO_FOOTER, photograph = T.TAKE_PHOTO,
            addPhoto = T.ADD_PHOTO, remove = T.REMOVE,
        )
        SaveSection(save, vm::save, onDone, enabled = editable && f.openingRef != null && f.closingRef != null, label = T.SEND)
    }
}

private fun <E> List<E>.replaced(index: Int, value: E): List<E> = mapIndexed { i, old -> if (i == index) value else old }
