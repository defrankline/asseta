package com.asseta.supervisor.ui.accountability

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.domain.accountability.CheckinSummary
import com.asseta.core.domain.accountability.SiteCheckinRules
import com.asseta.core.domain.accountability.SlotState
import com.asseta.core.domain.accountability.SlotView
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.inbox.Tone
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.owner.MySiteCheckinsDto
import com.asseta.core.model.sync.AccountabilityOps
import com.asseta.core.sync.data.FieldAccountabilityCache
import com.asseta.core.sync.data.InboxSnapshot
import com.asseta.core.sync.usecase.FinanceResult
import com.asseta.core.ui.components.GroupedSection
import com.asseta.core.ui.components.Pill
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.capture.GpsLocator
import com.asseta.supervisor.ui.Busy
import com.asseta.supervisor.ui.InboxRow
import com.asseta.supervisor.ui.Section
import com.asseta.supervisor.ui.toneColor
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.ZoneId
import java.util.UUID

/** Wording of site check-ins (DEC-031 M3; keys `field.checkin.*`, same on iOS). */
object SiteCheckinTexts {
    const val ENTRY = "Site check-in"
    const val TITLE = "Site check-ins"
    const val NONE_LEFT = "No more check-ins today"
    const val TODAY = "Today"
    const val TODAY_EMPTY = "No check-ins are scheduled for you today."
    const val ACTION = "Check in now"
    const val LOCATING = "Getting your location…"
    const val SAVED = "Check-in saved. It is sent when the phone is online."
    const val FOOTER = "Your company asks you to check in at the site at these times. Your location is recorded with each check-in. " +
        "Check-ins are saved on the phone and sent when you are online."
    const val MINE = "My check-ins"
    const val MINE_EMPTY = "No check-ins in the last 7 days."
    const val NO_SITE = "No site"
    const val OUTSIDE = "Further from the site than allowed"
    const val NO_LOCATION = "Recorded without location"
    const val WAITING = "Waiting to sync"
    const val NOT_ACCEPTED = "Not accepted"
    const val NEVER = "Your check-in times appear here after you connect."
    const val OUTBOX = "Site check-in"

    fun due(time: String) = "Check-in due now, until $time"
    fun next(time: String) = "Next check-in at $time"
    fun window(from: String, to: String) = "Between $from and $to"
    fun distanceFooter(metres: Int) = "Check in within $metres m of the site."
    fun distance(metres: String) = "$metres m from the site"
    fun savedAt(time: String) = "Schedule from $time. Connect to update it."

    fun status(state: SlotState): String = when (state) {
        SlotState.MADE -> "Checked in"
        SlotState.SAVED -> "Saved on this phone"
        SlotState.MISSED -> "Missed"
        SlotState.DUE -> "Due now"
        SlotState.UPCOMING -> "Upcoming"
    }

    fun tone(state: SlotState): Tone = when (state) {
        SlotState.MADE -> Tone.GOOD
        SlotState.SAVED -> Tone.INFO
        SlotState.MISSED -> Tone.BAD
        SlotState.DUE -> Tone.WARNING
        SlotState.UPCOMING -> Tone.NEUTRAL
    }

    /** Plain words for the server's refusals of a check-in (null: another code). */
    fun conflict(code: String?): String? = when (code) {
        "SITE_CHECKIN_DISABLED" -> "Your company has switched off site check-ins, so this check-in was not accepted."
        "CHECKIN_ID_CONFLICT" -> "This check-in could not be saved because its id is already used. Check in again."
        "STAFF_NOT_LINKED" -> "Your account is not linked to a staff record, so check-ins cannot be saved. Ask the office."
        "CHECKIN_IN_FUTURE" -> "The phone's clock is ahead, so this check-in was not accepted. Correct the phone's time and check in again."
        "JOB_SITE_NOT_FOUND" -> "The site of this check-in no longer exists. Check in again."
        else -> null
    }

    /** The Jobs tab line under "Site check-in". */
    fun summary(s: CheckinSummary, zone: ZoneId): String = when (s) {
        is CheckinSummary.Due -> due(SiteCheckinRules.time(s.until, zone))
        is CheckinSummary.Next -> next(SiteCheckinRules.time(s.at, zone))
        CheckinSummary.NoneLeft -> NONE_LEFT
    }
}

/** One row of "My check-ins": label (date-time), value (site), caption, and the sync state of this phone's own. */
data class CheckinRow(val key: String, val atMs: Long, val label: String, val value: String, val caption: String?, val tone: Tone?)

/** Pure presentation of the check-in screen (unit-tested; same rules as iOS). */
object SiteCheckinPresentation {
    private val REFUSED = setOf(ClientOperationStatus.FAILED, ClientOperationStatus.QUARANTINED, ClientOperationStatus.CONFLICT)

    fun checkinOps(ops: List<ClientOperationEntity>) = ops.filter { it.opType == AccountabilityOps.SITE_CHECKIN }

    private fun at(op: ClientOperationEntity, payloadOf: (ClientOperationEntity) -> Map<String, String?>): Instant =
        SiteCheckinRules.instant(payloadOf(op)["captured_at"]) ?: Instant.ofEpochMilli(op.createdAtDevice)

    /** Check-in times the server has: its list and this phone's acknowledged check-ins. */
    fun confirmed(saved: MySiteCheckinsDto?, ops: List<ClientOperationEntity>, payloadOf: (ClientOperationEntity) -> Map<String, String?>): List<Instant> =
        saved?.checkins.orEmpty().mapNotNull { SiteCheckinRules.instant(it.capturedAt) } +
            checkinOps(ops).filter { it.status == ClientOperationStatus.ACKED }.map { at(it, payloadOf) }

    /** This phone's check-ins not synced yet (refused ones do not count). */
    fun pending(ops: List<ClientOperationEntity>, payloadOf: (ClientOperationEntity) -> Map<String, String?>): List<Instant> =
        checkinOps(ops).filter { it.status == ClientOperationStatus.PENDING || it.status == ClientOperationStatus.SENT }.map { at(it, payloadOf) }

    fun slots(cache: FieldAccountabilityCache, ops: List<ClientOperationEntity>, payloadOf: (ClientOperationEntity) -> Map<String, String?>, now: Instant): List<SlotView> =
        SiteCheckinRules.today(cache.siteCheckins, confirmed(cache.siteCheckins, ops, payloadOf), pending(ops, payloadOf), now)

    /** The server's check-ins and this phone's not on the server list yet, newest first. */
    fun mine(saved: MySiteCheckinsDto?, ops: List<ClientOperationEntity>, payloadOf: (ClientOperationEntity) -> Map<String, String?>): List<CheckinRow> {
        val zone = SiteCheckinRules.zone(saved)
        val server = saved?.checkins.orEmpty().map { c ->
            val at = SiteCheckinRules.instant(c.capturedAt) ?: Instant.EPOCH
            val caption = if (c.gpsStatus != "FIX") {
                SiteCheckinTexts.NO_LOCATION
            } else {
                c.distanceM?.let { d ->
                    SiteCheckinTexts.distance(SiteCheckinRules.metres(d)) + if (c.withinDistance == false) " · " + SiteCheckinTexts.OUTSIDE else ""
                }
            }
            CheckinRow(c.clientId, at.toEpochMilli(), SiteCheckinRules.dateTime(at, zone), c.jobSiteName ?: SiteCheckinTexts.NO_SITE, caption,
                if (c.withinDistance == false) Tone.WARNING else null)
        }
        val known = saved?.checkins.orEmpty().map { it.clientId }.toSet()
        val local = checkinOps(ops).filter { it.entityId !in known && it.status != ClientOperationStatus.ACKED }.map { op ->
            val at = at(op, payloadOf)
            val refused = op.status in REFUSED
            val caption = if (refused) {
                listOfNotNull(SiteCheckinTexts.NOT_ACCEPTED, SiteCheckinTexts.conflict(op.errorCode)).joinToString(" · ")
            } else {
                SiteCheckinTexts.WAITING
            }
            CheckinRow(op.entityId, at.toEpochMilli(), SiteCheckinRules.dateTime(at, zone), "", caption,
                if (refused) Tone.BAD else Tone.INFO)
        }
        return (local + server).sortedByDescending { it.atMs }
    }

    /** Footer lines: what the company asks, the distance limit, and how old the saved schedule is. */
    fun footer(cache: FieldAccountabilityCache, online: Boolean, zone: ZoneId): String = listOfNotNull(
        SiteCheckinTexts.FOOTER,
        cache.siteCheckins?.maxDistanceM?.let(SiteCheckinTexts::distanceFooter),
        cache.siteCheckinsAtMs.takeIf { !online && it > 0 }?.let { SiteCheckinTexts.savedAt(SiteCheckinRules.dateTime(Instant.ofEpochMilli(it), zone)) },
    ).joinToString(" ")
}

/** The check-in screen: refreshes the schedule online, checks in with a fresh GPS attempt (offline-capable). */
class SiteCheckinViewModel(private val field: FieldGraph, private val tenantId: String, private val permissions: Set<String>) : ViewModel() {
    val cache: StateFlow<FieldAccountabilityCache> = field.accountability.cache
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()
    private val _message = MutableStateFlow<Pair<String, Boolean>?>(null)

    /** The last outcome (text, is error). */
    val message: StateFlow<Pair<String, Boolean>?> = _message.asStateFlow()

    init {
        viewModelScope.launch { field.accountability.load(tenantId) }
    }

    fun refresh() {
        viewModelScope.launch { field.accountability.refreshSiteCheckins(tenantId, permissions) }
    }

    /** [granted]: the location permission (asked once); without it the check-in is recorded as PERMISSION_DENIED. */
    fun checkIn(granted: Boolean) {
        if (_busy.value) return
        _busy.value = true
        _message.value = null
        val clientId = UUID.randomUUID().toString()
        val at = field.clock.nowMs()
        viewModelScope.launch {
            val gps = if (granted) field.gps.attempt() else GpsOutcome.PermissionDenied
            _message.value = when (val r = field.accountabilityCapture.siteCheckin(tenantId, clientId, at, gps)) {
                is FinanceResult.Saved, FinanceResult.AlreadySaved -> SiteCheckinTexts.SAVED to false
                is FinanceResult.Blocked -> r.message to true
                is FinanceResult.Invalid -> r.messages.joinToString(" ") to true
            }
            _busy.value = false
        }
    }
}

@Composable
private fun rememberNow(): Instant {
    val now by produceState(Instant.now()) {
        while (true) {
            delay(30_000)
            value = Instant.now()
        }
    }
    return now
}

/** The "Site check-in" row of the Jobs tab (shown when the server, the role and the company ask for check-ins). */
@Composable
fun SiteCheckinEntry(field: FieldGraph, tenantId: String, permissions: Set<String>, snapshot: InboxSnapshot, syncing: Boolean, onOpen: () -> Unit) {
    val cache by field.accountability.cache.collectAsStateWithLifecycle()
    LaunchedEffect(tenantId, syncing) { if (!syncing) field.accountability.refreshSiteCheckins(tenantId, permissions) }
    val now = rememberNow()
    val zone = SiteCheckinRules.zone(cache.siteCheckins)
    val slots = SiteCheckinPresentation.slots(cache, snapshot.accountabilityOps, field.inbox::payloadText, now)
    val line = if (cache.siteCheckins == null) SiteCheckinTexts.NEVER else SiteCheckinTexts.summary(SiteCheckinRules.summary(slots), zone)
    val due = slots.any { it.state == SlotState.DUE }
    GroupedSection {
        com.asseta.core.ui.components.LinkRow(onOpen) {
            Column(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(SiteCheckinTexts.ENTRY, style = AssetaType.headline)
                Text(line, style = AssetaType.subheadline, color = if (due) palette.warning else palette.secondaryText)
            }
        }
    }
}

@Composable
fun SiteCheckinScreen(vm: SiteCheckinViewModel, field: FieldGraph, snapshot: InboxSnapshot, online: Boolean) {
    val cache by vm.cache.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    val now = rememberNow()
    LaunchedEffect(online) { if (online) vm.refresh() }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        vm.checkIn(result.values.any { it })
    }
    val zone = SiteCheckinRules.zone(cache.siteCheckins)
    val ops = snapshot.accountabilityOps
    val slots = SiteCheckinPresentation.slots(cache, ops, field.inbox::payloadText, now)
    val rows = SiteCheckinPresentation.mine(cache.siteCheckins, ops, field.inbox::payloadText)
    com.asseta.supervisor.ui.accountability.FormColumn {
        Section(SiteCheckinTexts.TODAY, footer = SiteCheckinPresentation.footer(cache, online, zone)) {
            when {
                cache.siteCheckins == null -> Text(SiteCheckinTexts.NEVER, color = palette.secondaryText)
                slots.isEmpty() -> Text(SiteCheckinTexts.TODAY_EMPTY, color = palette.secondaryText)
                else -> slots.forEach { s -> SlotRow(s, zone) }
            }
        }
        if (busy) {
            Busy(SiteCheckinTexts.LOCATING)
        } else {
            Button(
                onClick = { if (field.gps.hasPermission()) vm.checkIn(true) else permission.launch(GpsLocator.PERMISSIONS) },
                modifier = Modifier.fillMaxWidth().testTag("site-checkin"),
            ) { Text(SiteCheckinTexts.ACTION) }
        }
        message?.let { (text, error) -> Text(text, color = if (error) palette.offline else palette.secondaryText, style = AssetaType.subheadline) }
        Section(SiteCheckinTexts.MINE) {
            if (rows.isEmpty()) Text(SiteCheckinTexts.MINE_EMPTY, color = palette.secondaryText)
            rows.forEach { r ->
                Column(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    InboxRow(r.label, null, r.value.takeIf { it.isNotBlank() })
                    r.caption?.let { Text(it, style = AssetaType.caption, color = r.tone?.let { t -> toneColor(t) } ?: palette.secondaryText) }
                }
            }
        }
    }
}

@Composable
private fun SlotRow(s: SlotView, zone: ZoneId) {
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(SiteCheckinRules.time(s.at, zone), style = AssetaType.headline)
            Text(SiteCheckinTexts.window(SiteCheckinRules.time(s.from, zone), SiteCheckinRules.time(s.to, zone)), style = AssetaType.caption, color = palette.secondaryText)
        }
        Pill(SiteCheckinTexts.status(s.state), toneColor(SiteCheckinTexts.tone(s.state)))
    }
}
