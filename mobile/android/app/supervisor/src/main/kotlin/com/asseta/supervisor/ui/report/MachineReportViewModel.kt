package com.asseta.supervisor.ui.report

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.accountability.CustomerHoursPolicy
import com.asseta.core.domain.accountability.FieldAccess
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.capture.OcrFlow
import com.asseta.core.domain.capture.OcrStep
import com.asseta.core.domain.capture.ReadingInput
import com.asseta.core.domain.capture.ReadingValidator
import com.asseta.core.domain.forms.FormLeave
import com.asseta.core.domain.forms.LeaveAction
import com.asseta.core.domain.ocr.OcrReading
import com.asseta.core.domain.policy.CaptureMode
import com.asseta.core.domain.policy.CapturePolicyDecision
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.domain.reports.MachineReportRules
import com.asseta.core.domain.reports.ReportLineDraft
import com.asseta.core.domain.reports.ReportState
import com.asseta.core.sync.data.MachineReportView
import com.asseta.core.sync.data.ReportMachine
import com.asseta.core.sync.usecase.FinanceResult
import com.asseta.core.sync.usecase.MachineReportRequest
import com.asseta.core.sync.usecase.ReportReading
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.capture.CapturedPhoto
import com.asseta.supervisor.capture.MeterOcr
import com.asseta.supervisor.ui.CaptureIssues
import com.asseta.supervisor.ui.CaptureUi
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.math.BigDecimal
import java.util.UUID

/** The three steps of a machine report (approved designs MachineReading, Reconcile, ReviewSubmit). */
enum class ReportStep { READING, SPLIT, REVIEW }

/** One report in progress. [capture] is the step-1 reading (camera, on-phone OCR, fresh GPS). */
data class ReportForm(
    val step: ReportStep = ReportStep.READING,
    val machineId: String? = null,
    val capture: CaptureUi = CaptureUi(ReadingKind.DAILY, loading = false),
    val lines: List<ReportLineDraft> = emptyList(),
    val note: String = "",
    /** The phone geocoder's area label of the reading's GPS fix (online only; never waited for). */
    val place: FixPlace? = null,
    /** The last visit's area label found on this phone when the server has none (display only, never sent). */
    val lastVisitPlace: String? = null,
    val saving: Boolean = false,
    val saved: Boolean = false,
    val messages: List<String> = emptyList(),
    /** Leaving was asked with entered work: "Discard this report?" is shown. */
    val confirmDiscard: Boolean = false,
)

/** The area label found for one GPS fix. */
data class FixPlace(val latitude: Double, val longitude: Double, val name: String?)

/**
 * A machine report: pick one of my machines, take its reading (always a new reading: a rejected report is final),
 * split the hours across customers and non-productive reasons, review, submit (queued offline as
 * MACHINE_REPORT). The report id is generated once per visit (exactly-once).
 */
class MachineReportViewModel(
    private val field: FieldGraph,
    private val tenantId: String,
    private val permissions: Set<String>,
    initialMachineId: String?,
) : ViewModel() {
    private val reportId = UUID.randomUUID().toString()
    private val captureId = UUID.randomUUID().toString()
    private val _form = MutableStateFlow(ReportForm())
    val form: StateFlow<ReportForm> = _form.asStateFlow()
    val view: StateFlow<MachineReportView> = field.machineReports.observe(tenantId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), MachineReportView())
    private val _access = MutableStateFlow<FieldAccess?>(null)
    val access: StateFlow<FieldAccess?> = _access.asStateFlow()
    private var gpsJob: Job? = null
    private var placeJob: Job? = null
    private var lastVisitJob: Job? = null

    init {
        viewModelScope.launch {
            _access.value = field.accountability.access(tenantId, permissions)
            val machines = field.machineReports.observe(tenantId).first().machines(reminderDays())
            (initialMachineId ?: machines.singleOrNull()?.id ?: machines.firstOrNull { it.state.needsReport }?.id)?.let { select(it) }
        }
    }

    fun reminderDays(): Int? = CustomerHoursPolicy.reminderDays(_access.value?.hours)

    fun machines(v: MachineReportView = view.value): List<ReportMachine> = v.machines(reminderDays())

    fun machine(v: MachineReportView = view.value): ReportMachine? = machines(v).firstOrNull { it.id == _form.value.machineId }

    /** Choose the machine; every report takes a new reading (a rejected report is final). */
    fun select(machineId: String?) {
        _form.update { ReportForm(machineId = machineId) }
        machineId ?: return
        viewModelScope.launch {
            val m = machines(field.machineReports.observe(tenantId).first()).firstOrNull { it.id == machineId } ?: return@launch
            nameLastVisit(m)
            when (val decision = field.repository.capturePolicy(tenantId, machineId)) {
                is CapturePolicyDecision.Blocked -> _form.update { it.copy(capture = it.capture.copy(blocked = decision.message, decimals = m.decimals)) }
                is CapturePolicyDecision.Allowed -> _form.update {
                    it.copy(capture = it.capture.copy(
                        blocked = null, machineLabel = m.label, decimals = m.decimals,
                        mode = decision.policy.requiredMode(ReadingKind.DAILY), policy = decision.policy, policyStamp = decision.snapshot.versionStamp,
                    ))
                }
            }
        }
    }

    /** The reading of the report: the one typed / read from the photo. */
    fun reading(f: ReportForm = _form.value): BigDecimal? {
        val m = machine() ?: return null
        return (ReadingValidator.validate(f.capture.readingText, m.decimals) as? ReadingInput.Valid)?.normalized?.toBigDecimalOrNull()
    }

    /** The reading the report starts from: the machine's last approved reading (or its baseline / reset). */
    fun previous(): BigDecimal? = machine()?.previous

    /** When the reading was taken (the photo), else now: the end of "Time since last visit". */
    fun visitAtMs(): Long = _form.value.capture.photo?.takenAtMs ?: field.clock.nowMs()

    /**
     * The last visit's area label: the server's, else (online) the phone geocoder's for display only, never sent.
     */
    fun lastVisitPlace(m: ReportMachine): String? = m.status.lastVisitPlace?.takeIf { it.isNotBlank() } ?: _form.value.lastVisitPlace

    private fun nameLastVisit(m: ReportMachine) {
        val s = m.status
        if (!s.lastVisitPlace.isNullOrBlank()) return
        val lat = s.lastVisitLat ?: return
        val lng = s.lastVisitLng ?: return
        lastVisitJob?.cancel()
        lastVisitJob = viewModelScope.launch {
            val name = field.places.placeName(lat, lng) ?: return@launch
            _form.update { if (it.machineId == m.id) it.copy(lastVisitPlace = name) else it }
        }
    }

    /** Names the place of a fresh GPS fix in the background (online, ~3 s); the reading never waits for it. */
    private fun namePlace(gps: GpsOutcome?) {
        val fix = gps as? GpsOutcome.Fix ?: return
        placeJob?.cancel()
        placeJob = viewModelScope.launch {
            val name = field.places.placeName(fix.latitude, fix.longitude)
            _form.update { it.copy(place = FixPlace(fix.latitude, fix.longitude, name)) }
        }
    }

    /** The place name of [gps] if it was already found (never waited for). */
    private fun placeOf(gps: GpsOutcome?, f: ReportForm = _form.value): String? {
        val fix = gps as? GpsOutcome.Fix ?: return null
        return f.place?.takeIf { it.latitude == fix.latitude && it.longitude == fix.longitude }?.name
    }

    fun difference(): BigDecimal? = reading()?.let { r -> MachineReportRules.difference(previous(), r) }

    /** What still blocks step 1 (capture evidence, then the reading against the last one). */
    fun readingIssues(): List<String> {
        val m = machine() ?: return listOf(ReportTexts.CHOOSE_MACHINE)
        if (m.state == ReportState.AWAITING_APPROVAL) return listOf(ReportTexts.state(ReportState.AWAITING_APPROVAL))
        val c = _form.value.capture
        c.blocked?.let { return listOf(it) }
        if (c.mode == null) return listOf(ReportTexts.CHOOSE_MACHINE)
        val issues = CaptureIssues.of(c)
        if (issues.isNotEmpty()) return issues
        return listOfNotNull(MachineReportRules.readingProblem(previous(), reading()))
    }

    fun available(): Map<String, BigDecimal> = _form.value.machineId?.let { view.value.available(it) } ?: emptyMap()

    // --- Step 1: the reading ----------------------------------------------------------------------------------------

    fun onLocationDecision(granted: Boolean) {
        _form.update { it.copy(capture = it.capture.copy(locationDecided = true)) }
        if (granted) attemptGps() else _form.update { it.copy(capture = it.capture.copy(gps = GpsOutcome.PermissionDenied, gpsAttemptAtMs = field.clock.nowMs())) }
    }

    fun attemptGps() {
        if (gpsJob?.isActive == true) return
        gpsJob = viewModelScope.launch {
            _form.update { it.copy(capture = it.capture.copy(gpsBusy = true, gps = null)) }
            val startedAt = field.clock.nowMs()
            val outcome = field.gps.attempt()
            _form.update { it.copy(capture = it.capture.copy(gpsBusy = false, gps = outcome, gpsAttemptAtMs = startedAt)) }
            namePlace(outcome)
        }
    }

    fun onPhoto(photo: CapturedPhoto) {
        val current = _form.value.capture
        val attempts = current.attempts + 1
        _form.update { it.copy(capture = it.capture.copy(photo = photo, attempts = attempts, error = null, ocr = null, ocrStep = null), messages = emptyList()) }
        refreshGpsIfStale(photo.takenAtMs)
        if (current.mode != CaptureMode.AUTOMATIC) return
        val policy = current.policy ?: return
        viewModelScope.launch {
            _form.update { it.copy(capture = it.capture.copy(ocrBusy = true)) }
            val reading = withContext(Dispatchers.Default) {
                val bitmap = MeterOcr.decodeForOcr(photo.jpeg, photo.rotationDegrees)
                if (bitmap == null) null else runCatching { field.ocr.read(bitmap, current.decimals, policy.minOcrConfidence) }.getOrNull()
            } ?: OcrReading(null, 0.0, "", "OCR_FAILED", emptySet())
            val step = OcrFlow.next(attempts, reading, policy)
            _form.update {
                it.copy(capture = it.capture.copy(ocrBusy = false, ocr = reading, ocrStep = step, readingText = if (step == OcrStep.RECAPTURE) "" else reading.value.orEmpty()))
            }
        }
    }

    fun onPhotoError(message: String) = _form.update { it.copy(messages = listOf("The photo could not be saved: $message")) }

    fun onReadingChanged(text: String) = _form.update { it.copy(capture = it.capture.copy(readingText = text.filter { c -> c.isDigit() || c == '.' || c == ',' }), messages = emptyList()) }

    /** Step 1 → step 2 (an opening report has nothing to split: it is submitted from step 1). */
    fun next() {
        if (readingIssues().isNotEmpty()) return
        _form.update { it.copy(step = ReportStep.SPLIT, messages = emptyList()) }
    }

    // --- Step 2: the split --------------------------------------------------------------------------------------------

    fun addCustomer(id: String, name: String) = _form.update { f ->
        if (f.lines.any { it is ReportLineDraft.Customer && it.customerId == id }) f
        else f.copy(lines = f.lines + ReportLineDraft.Customer(id, name, suggestedHours(f)), messages = emptyList())
    }

    fun addNonProductive(id: String, name: String) = _form.update { f -> f.copy(lines = f.lines + ReportLineDraft.NonProductive(id, name, suggestedHours(f), ""), messages = emptyList()) }

    /** A new line starts with the hours still to account for (empty when none are left). */
    private fun suggestedHours(f: ReportForm): String {
        machine() ?: return ""
        val left = difference()?.let { MachineReportRules.left(it, f.lines) } ?: return ""
        return if (left.signum() > 0) left.stripTrailingZeros().toPlainString() else ""
    }

    fun editLine(index: Int, change: (ReportLineDraft) -> ReportLineDraft) =
        _form.update { f -> f.copy(lines = f.lines.mapIndexed { i, l -> if (i == index) change(l) else l }, messages = emptyList()) }

    fun removeLine(index: Int) = _form.update { f -> f.copy(lines = f.lines.filterIndexed { i, _ -> i != index }) }

    fun canReview(): Boolean {
        machine() ?: return false
        val d = difference() ?: return false
        return MachineReportRules.canReview(d, _form.value.lines, available())
    }

    fun review() {
        if (canReview()) _form.update { it.copy(step = ReportStep.REVIEW, messages = emptyList()) }
    }

    fun back(): Boolean {
        val f = _form.value
        if (f.saving || f.saved) return false
        return when (f.step) {
            ReportStep.READING -> false
            ReportStep.SPLIT -> { _form.update { it.copy(step = ReportStep.READING) }; true }
            ReportStep.REVIEW -> { _form.update { it.copy(step = ReportStep.SPLIT) }; true }
        }
    }

    /** A photo, a typed reading, a note or changed lines: leaving would throw them away. */
    fun hasEnteredData(f: ReportForm = _form.value): Boolean = FormLeave.reportEntered(
        hasPhoto = f.capture.photo != null,
        typedReading = f.capture.readingText,
        lines = f.lines, startingLines = emptyList(), note = f.note,
    )

    /**
     * Leaving (system Back, the bar's Back): steps back first; then, with entered work, asks "Discard this report?"
     * instead of leaving. True when handled here (stay on the screen).
     */
    fun onLeave(): Boolean {
        if (back()) return true
        val f = _form.value
        return when (FormLeave.decide(f.saving, f.saved, hasEnteredData(f))) {
            LeaveAction.LEAVE -> false
            LeaveAction.STAY -> true
            LeaveAction.ASK -> { _form.update { it.copy(confirmDiscard = true) }; true }
        }
    }

    fun keepEditing() = _form.update { it.copy(confirmDiscard = false) }

    // --- Step 3: submit -------------------------------------------------------------------------------------------------

    fun onNote(text: String) = _form.update { it.copy(note = text.take(MachineReportRules.MAX_NOTE)) }

    fun submit() {
        val f = _form.value
        if (f.saving || f.saved) return
        val m = machine() ?: return
        _form.update { it.copy(saving = true, messages = emptyList()) }
        viewModelScope.launch {
            val c = f.capture
            refreshGpsIfStale(c.photo?.takenAtMs ?: field.clock.nowMs())
            gpsJob?.join()
            val latest = _form.value.capture
            val result = field.reportCapture.submit(
                MachineReportRequest(
                    tenantId = tenantId, reportId = reportId, machineId = m.id, decimals = m.decimals, previous = previous(),
                    reading = ReportReading(
                        captureId, latest.mode ?: CaptureMode.MANUAL, latest.readingText, latest.photo?.jpeg,
                        latest.attempts.takeIf { latest.mode == CaptureMode.AUTOMATIC } ?: 0, latest.ocr, latest.gps,
                        latest.photo?.takenAtMs ?: field.clock.nowMs(),
                        placeName = placeOf(latest.gps),
                    ),
                    lines = f.lines, available = available(), note = f.note, createdAtMs = field.clock.nowMs(),
                ),
            )
            _form.update {
                when (result) {
                    is FinanceResult.Saved, FinanceResult.AlreadySaved -> it.copy(saving = false, saved = true)
                    is FinanceResult.Blocked -> it.copy(saving = false, messages = listOf(result.message))
                    is FinanceResult.Invalid -> it.copy(saving = false, messages = result.messages)
                }
            }
        }
    }

    private fun refreshGpsIfStale(captureAtMs: Long) {
        val s = _form.value.capture
        if (!s.locationDecided || s.gps == GpsOutcome.PermissionDenied && !field.gps.hasPermission()) return
        val last = s.gpsAttemptAtMs
        if (s.gps == null || last == null || captureAtMs - last > MAX_GPS_AGE_MS) attemptGps()
    }

    private companion object {
        const val MAX_GPS_AGE_MS = 90_000L
    }
}
