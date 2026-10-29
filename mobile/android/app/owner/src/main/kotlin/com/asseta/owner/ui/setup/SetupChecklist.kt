package com.asseta.owner.ui.setup

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.DataSource
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.MutationGate
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.owner.SetupChecklistDto
import com.asseta.core.model.owner.SetupCheckDto
import com.asseta.core.model.owner.SetupStepDto
import com.asseta.core.ui.components.ButtonRow
import com.asseta.core.ui.components.GroupedSection
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.OwnerNavigation
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.common.BlockedNote
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.ZoneId

/** Go-live checklist wording (docs/requirements/accountability-mobile-strings.md "Go-live checklist"; same as iOS). */
object SetupTexts {
    const val MORE = "Go-live checklist"
    const val TITLE = "Go-live checklist"
    const val BANNER_CAPTION = "Open the go-live checklist to see what is left."
    const val COMPLETE = "Everything is ready. You can go live."
    const val FOOTER = "Each step is checked against your company's records and updates by itself as the work is done. " +
        "Most steps are done on the web."
    const val CHECK_DONE = "Done"
    const val CHECK_TODO = "To do"
    const val OPTIONAL = "Optional"
    const val OPEN_WEB = "Open on the web"
    const val NEEDS_ACCESS = "Someone with access to this screen must do this step."
    const val MARK_NOT_NEEDED = "Mark as not needed"
    const val NOT_NEEDED_REASON = "Why this step does not apply"
    const val NOT_NEEDED_HINT = "At least 3 characters."
    const val UNDO = "Undo"
    const val CONTROLS_FINE = "Our default controls are fine"
    const val CONTROLS_TITLE = "Keep the default controls?"
    const val CONTROLS_MESSAGE = "Asseta's default controls stay in place. You can change them on the web at any time."
    const val CONTROLS_NOTE = "Note (optional)"
    const val CONTROLS_CONFIRM = "Keep the defaults"
    const val CANCEL = "Cancel"
    const val ERROR_STEP_REQUIRED = "This step is needed before going live, so it cannot be marked as not needed."
    private const val SOMEONE = "someone"

    fun banner(done: Int, total: Int) = "Get ready to go live — $done of $total done"
    fun progress(done: Int, total: Int) = "$done of $total done"
    fun count(done: Int, total: Int) = "$done of $total"
    fun asOf(dateTime: String) = "Checked $dateTime"
    fun openScreen(screen: String) = "Open $screen"
    fun notNeededTitle(step: String) = "Mark \"$step\" as not needed?"
    fun notNeededBy(name: String?, date: String, reason: String?) =
        "Marked not needed by ${name ?: SOMEONE} on $date" + (reason?.takeIf { it.isNotBlank() }?.let { ": $it" } ?: "")
    fun controlsBy(name: String?, date: String) = "Controls confirmed by ${name ?: SOMEONE} on $date"

    fun status(raw: String): String = when (raw) {
        SetupStatus.DONE -> "Done"
        SetupStatus.TODO -> "To do"
        SetupStatus.NOT_NEEDED -> "Not needed"
        SetupStatus.NOT_APPLICABLE -> "Does not apply"
        else -> OwnerFormat.humanize(raw)
    }

    /** Refusal wording: SETUP_STEP_REQUIRED in plain words, other codes as the standard error text. */
    fun error(code: String?, message: String): String = if (code == "SETUP_STEP_REQUIRED") ERROR_STEP_REQUIRED else message
}

object SetupStatus {
    const val DONE = "DONE"
    const val TODO = "TODO"
    const val NOT_NEEDED = "NOT_NEEDED"
    const val NOT_APPLICABLE = "NOT_APPLICABLE"
}

/** The step that carries "Our default controls are fine". */
const val CONTROLS_STEP = "CONTROLS_CHOSEN"

/** Dashboard banner figures (from `/me`, later from the checklist itself). */
data class SetupProgress(val done: Int, val total: Int, val complete: Boolean, val dismissed: Boolean) {
    /** The banner shows while there is something left to do and the owner has not hidden it. */
    val showBanner: Boolean get() = !complete && !dismissed && total > 0

    companion object {
        /** Null when `/me` carries no figures (the user may not read the checklist). */
        fun fromMe(t: TenantAccess): SetupProgress? {
            val total = t.setupStepsTotal ?: return null
            return SetupProgress(t.setupStepsDone ?: 0, total, t.setupComplete ?: false, t.setupDismissed ?: false)
        }

        fun of(c: SetupChecklistDto) = SetupProgress(c.stepsDone, c.stepsTotal, c.complete, c.dismissed)
    }
}

/** Where a step / check action leads: an Owner app screen, or the web console in the browser. */
sealed interface SetupTarget {
    val label: String

    data class App(val destination: OwnerDestination, override val label: String) : SetupTarget
    data class Web(val url: String) : SetupTarget {
        override val label: String get() = SetupTexts.OPEN_WEB
    }
}

/** Maps checklist web routes to Owner app screens (the table in the strings doc); everything else opens the web. */
object SetupLinks {
    fun appScreen(link: String, f: OwnerFeatures): OwnerDestination? {
        val path = link.substringBefore('?').trimEnd('/')
        val hasQuery = '?' in link
        return when (path) {
            "/tenant/machines" -> OwnerDestination.Fleet.takeIf { !hasQuery && f.fleet }
            "/tenant/jobs" -> OwnerDestination.Jobs.takeIf { f.jobs }
            "/tenant/approvals", "/tenant/meter-baselines" -> OwnerDestination.Approvals().takeIf { f.approvals }
            "/tenant/hours", "/tenant/hours/purchases" -> OwnerDestination.CustomerHours.takeIf { f.customerHours }
            "/tenant/finance/cash" -> OwnerDestination.Cash.takeIf { !hasQuery && f.finance }
            else -> null
        }
    }

    /** [base] (e.g. `https://asseta.co.tz/`) + [link] (`/tenant/policies`), with exactly one slash between. */
    fun webUrl(base: String, link: String): String = base.trimEnd('/') + "/" + link.trimStart('/')

    fun target(link: String, f: OwnerFeatures, webBase: String): SetupTarget =
        appScreen(link, f)?.let { SetupTarget.App(it, SetupTexts.openScreen(OwnerNavigation.title(it))) } ?: SetupTarget.Web(webUrl(webBase, link))
}

/** What the screen offers on one step (pure, unit tested). */
object SetupPresentation {
    fun steps(c: SetupChecklistDto): List<SetupStepDto> = c.steps.sortedBy { it.order }

    fun countLine(done: Int?, total: Int?): String? = if (total == null) null else SetupTexts.count(done ?: 0, total)

    /** The step's own action: none once done, not needed or not applicable. */
    fun hasAction(s: SetupStepDto): Boolean = s.status == SetupStatus.TODO

    fun canMarkNotNeeded(s: SetupStepDto): Boolean = s.canMarkNotNeeded && s.status == SetupStatus.TODO

    fun canUndo(s: SetupStepDto): Boolean = s.status == SetupStatus.NOT_NEEDED

    fun canConfirmControls(s: SetupStepDto, c: SetupChecklistDto): Boolean =
        s.key == CONTROLS_STEP && s.status == SetupStatus.TODO && c.controlsConfirmedAt == null

    /** "Someone with access…" when the user lacks the permission the step's screen needs. */
    fun needsAccess(s: SetupStepDto, permissions: Set<String>): Boolean = s.requiredPermission.isNotBlank() && s.requiredPermission !in permissions

    /** Reason accepted by the server: 3–500 characters once trimmed. */
    fun reasonValid(reason: String): Boolean = reason.trim().length in 3..500

    fun manageGate(f: OwnerFeatures, online: Boolean, source: DataSource?, readOnly: Boolean): MutationCheck =
        MutationGate.check(online, source ?: DataSource.CACHE, f.setupManage, readOnly)
}

class SetupChecklistViewModel(val data: OwnerData, refreshOn: Flow<Unit>) :
    SnapshotViewModel<SetupChecklistDto>({ data.setupChecklist() }, refreshOn) {
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    fun markNotNeeded(key: String, reason: String) {
        if (!SetupPresentation.reasonValid(reason)) return
        write { data.markSetupStepNotNeeded(key, reason) }
    }

    fun undo(key: String) = write { data.undoSetupStepNotNeeded(key) }

    fun confirmControls(note: String) = write { data.confirmSetupControls(note) }

    private fun write(call: suspend () -> ActionResult<SetupChecklistDto>) {
        if (_busy.value) return
        _busy.value = true
        _error.value = null
        viewModelScope.launch {
            when (val r = call()) {
                is ActionResult.Done -> replaceData { r.value }
                is ActionResult.Refused -> {
                    _error.value = SetupTexts.error(r.code, r.error.message)
                    if (r.reload) refresh()
                }
            }
            _busy.value = false
        }
    }
}

/** Overview banner: "Get ready to go live — N of M done", opens the checklist. */
@Composable
fun SetupBanner(progress: SetupProgress, onOpen: () -> Unit) {
    val p = palette
    Column(
        Modifier.fillMaxWidth().background(p.accent.copy(alpha = 0.15f), RoundedCornerShape(12.dp))
            .clickable(role = Role.Button, onClickLabel = SetupTexts.TITLE, onClick = onOpen)
            .padding(12.dp).testTag("setup-banner").semantics(mergeDescendants = true) {},
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(SetupTexts.banner(progress.done, progress.total), style = AssetaType.headline)
        LinearProgressIndicator(
            progress = { if (progress.total > 0) progress.done.toFloat() / progress.total else 0f },
            modifier = Modifier.fillMaxWidth(), color = p.accent,
        )
        Text(SetupTexts.BANNER_CAPTION, style = AssetaType.caption, color = p.secondaryText)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SetupChecklistScreen(vm: SetupChecklistViewModel, session: OwnerSession, online: Boolean, webBase: String, open: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val features = session.features
    val uri = LocalUriHandler.current
    var pulled by remember { mutableStateOf(false) }
    LaunchedEffect(state.loading) { if (!state.loading) pulled = false }
    var notNeededFor by rememberSaveable { mutableStateOf<String?>(null) }
    var confirmControls by rememberSaveable { mutableStateOf(false) }
    val go: (SetupTarget) -> Unit = { t ->
        when (t) {
            is SetupTarget.App -> open(t.destination)
            is SetupTarget.Web -> runCatching { uri.openUri(t.url) }
        }
    }
    val zone = ZoneId.systemDefault()
    PullToRefreshBox(isRefreshing = pulled && state.loading, onRefresh = { pulled = true; vm.refresh() }, modifier = Modifier.fillMaxSize()) {
        SnapshotScaffold(state, vm::refresh) { c ->
            val gate = SetupPresentation.manageGate(features, online, state.snapshot?.source, session.readOnly)
            val canManage = gate !is MutationCheck.Blocked
            LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
                item(key = "progress") {
                    GroupedSection(footer = SetupTexts.FOOTER) {
                        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(SetupTexts.progress(c.stepsDone, c.stepsTotal), style = AssetaType.headline)
                            LinearProgressIndicator(progress = { c.percent.coerceIn(0, 100) / 100f }, modifier = Modifier.fillMaxWidth(), color = palette.accent)
                            if (c.complete) Text(SetupTexts.COMPLETE, color = OwnerColors.Live)
                            FootNote(SetupTexts.asOf(OwnerFormat.dateTime(c.asOf, zone)))
                        }
                        if (features.setupManage && gate is MutationCheck.Blocked) BlockedNote(gate.reason)
                    }
                }
                error?.let { e ->
                    item(key = "error") {
                        Text(
                            e, color = MaterialTheme.colorScheme.error,
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp).semantics { liveRegion = LiveRegionMode.Polite },
                        )
                    }
                }
                SetupPresentation.steps(c).forEach { step ->
                    item(key = step.key) {
                        StepCard(
                            step, c, features, session.permissions, webBase, zone, canManage && !busy, go,
                            onNotNeeded = { notNeededFor = step.key },
                            onUndo = { vm.undo(step.key) },
                            onControls = { confirmControls = true },
                        )
                    }
                }
            }
            notNeededFor?.let { key ->
                val step = c.steps.firstOrNull { it.key == key }
                if (step == null) notNeededFor = null else NotNeededDialog(step.title, onDismiss = { notNeededFor = null }) { reason ->
                    notNeededFor = null
                    vm.markNotNeeded(key, reason)
                }
            }
            if (confirmControls) ControlsDialog(onDismiss = { confirmControls = false }) { note ->
                confirmControls = false
                vm.confirmControls(note)
            }
        }
    }
}

@Composable
private fun StepCard(
    step: SetupStepDto,
    c: SetupChecklistDto,
    features: OwnerFeatures,
    permissions: Set<String>,
    webBase: String,
    zone: ZoneId,
    canManage: Boolean,
    go: (SetupTarget) -> Unit,
    onNotNeeded: () -> Unit,
    onUndo: () -> Unit,
    onControls: () -> Unit,
) {
    val muted = step.status == SetupStatus.NOT_APPLICABLE
    val p = palette
    GroupedSection {
        Row(Modifier.fillMaxWidth().semantics(mergeDescendants = true) {}, verticalAlignment = Alignment.CenterVertically) {
            Text(
                "${step.order}. ${step.title}", style = AssetaType.headline, modifier = Modifier.weight(1f),
                color = if (muted) p.secondaryText else MaterialTheme.colorScheme.onSurface,
            )
            StatusPill(SetupTexts.status(step.status), statusColor(step.status))
        }
        Text(step.description, style = MaterialTheme.typography.bodyMedium, color = p.secondaryText)
        SetupPresentation.countLine(step.doneCount, step.totalCount)?.let { FootNote(it) }
        step.checks.forEach { check -> CheckRow(check, features, webBase, go, enabled = !muted) }
        step.notNeeded?.let { FootNote(SetupTexts.notNeededBy(it.markedByName, OwnerFormat.date(it.markedAt, zone), it.reason)) }
        if (step.key == CONTROLS_STEP && c.controlsConfirmedAt != null) {
            FootNote(SetupTexts.controlsBy(c.controlsConfirmedByName, OwnerFormat.date(c.controlsConfirmedAt, zone)))
        }
        if (SetupPresentation.hasAction(step)) {
            if (SetupPresentation.needsAccess(step, permissions)) FootNote(SetupTexts.NEEDS_ACCESS)
            val target = SetupLinks.target(step.link, features, webBase)
            ButtonRow(target.label, Modifier.testTag("setup-open-${step.key}")) { go(target) }
        }
        if (features.setupManage) {
            if (SetupPresentation.canConfirmControls(step, c)) {
                ButtonRow(SetupTexts.CONTROLS_FINE, Modifier.testTag("setup-controls"), enabled = canManage, onClick = onControls)
            }
            if (SetupPresentation.canMarkNotNeeded(step)) {
                ButtonRow(SetupTexts.MARK_NOT_NEEDED, Modifier.testTag("setup-not-needed-${step.key}"), enabled = canManage, onClick = onNotNeeded)
            }
            if (SetupPresentation.canUndo(step)) {
                ButtonRow(SetupTexts.UNDO, Modifier.testTag("setup-undo-${step.key}"), enabled = canManage, onClick = onUndo)
            }
        }
    }
}

@Composable
private fun CheckRow(check: SetupCheckDto, features: OwnerFeatures, webBase: String, go: (SetupTarget) -> Unit, enabled: Boolean) {
    val p = palette
    val target = if (!check.done && enabled) SetupLinks.target(check.link, features, webBase) else null
    val base = Modifier.fillMaxWidth()
    Row(
        (if (target != null) base.clickable(role = Role.Button, onClickLabel = target.label) { go(target) } else base)
            .semantics(mergeDescendants = true) {},
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(if (check.done) "✓" else "○", color = if (check.done) OwnerColors.Live else p.secondaryText)
        Column(Modifier.weight(1f)) {
            Text(check.label, style = MaterialTheme.typography.bodyMedium, color = if (target != null) p.accent else MaterialTheme.colorScheme.onSurface)
            val caption = listOfNotNull(
                if (check.done) SetupTexts.CHECK_DONE else SetupTexts.CHECK_TODO,
                SetupPresentation.countLine(check.doneCount, check.totalCount),
                SetupTexts.OPTIONAL.takeIf { check.optional },
            ).joinToString(" · ")
            Text(caption, style = AssetaType.caption, color = p.secondaryText)
        }
    }
}

@Composable
private fun statusColor(status: String) = when (status) {
    SetupStatus.DONE -> OwnerColors.Live
    SetupStatus.TODO -> OwnerColors.Warning
    else -> OwnerColors.Neutral
}

@Composable
private fun NotNeededDialog(stepTitle: String, onDismiss: () -> Unit, onConfirm: (String) -> Unit) {
    var reason by rememberSaveable { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(SetupTexts.notNeededTitle(stepTitle)) },
        text = {
            OutlinedTextField(
                reason, { reason = it.take(500) }, Modifier.fillMaxWidth().testTag("setup-reason"),
                label = { Text(SetupTexts.NOT_NEEDED_REASON) }, supportingText = { Text(SetupTexts.NOT_NEEDED_HINT) }, minLines = 2,
            )
        },
        confirmButton = {
            TextButton({ onConfirm(reason.trim()) }, enabled = SetupPresentation.reasonValid(reason)) { Text(SetupTexts.MARK_NOT_NEEDED) }
        },
        dismissButton = { TextButton(onDismiss) { Text(SetupTexts.CANCEL) } },
    )
}

@Composable
private fun ControlsDialog(onDismiss: () -> Unit, onConfirm: (String) -> Unit) {
    var note by rememberSaveable { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(SetupTexts.CONTROLS_TITLE) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(SetupTexts.CONTROLS_MESSAGE)
                OutlinedTextField(note, { note = it.take(500) }, Modifier.fillMaxWidth(), label = { Text(SetupTexts.CONTROLS_NOTE) }, minLines = 2)
            }
        },
        confirmButton = { TextButton({ onConfirm(note) }) { Text(SetupTexts.CONTROLS_CONFIRM) } },
        dismissButton = { TextButton(onDismiss) { Text(SetupTexts.CANCEL) } },
    )
}
