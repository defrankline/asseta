package com.asseta.supervisor.ui.accountability

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.accountability.DisplayNames
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.RemittanceOverdueDto
import com.asseta.core.ui.theme.AssetaType
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.ui.LabeledRow
import com.asseta.supervisor.ui.LocalTime
import com.asseta.supervisor.ui.Section
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.ZoneId

private val T = FieldAccountabilityTexts

/** Pure wording of the Supervisor "Overdue remittance" screen (unit-tested; same lines on iOS). */
object RemittanceOverdueText {
    /** The custodian's name, else the short id. */
    fun name(o: RemittanceOverdueDto): String = DisplayNames.of(o.staffMemberName, o.staffMemberId).orEmpty()

    /** "TZS 50,000.00, USD 20.00" (the amounts still held when flagged). */
    fun amounts(o: RemittanceOverdueDto): String = o.amounts.joinToString(", ") { a ->
        a.amount.toBigDecimalOrNull()?.let { OwnerFormat.money(it, a.currency) } ?: "${a.amount} ${a.currency}"
    }

    /** True when the cash was held longer than the allowance (DEC-031 D3), not merely past the daily cut-off. */
    fun heldTooLong(o: RemittanceOverdueDto): Boolean = o.reason == RemittanceOverdueDto.HELD_TOO_LONG

    fun reason(o: RemittanceOverdueDto): String = if (heldTooLong(o)) T.OVERDUE_REASON_HELD else T.OVERDUE_REASON_CUTOFF

    /** "24 Oct 2026" in [zone] (the date the oldest unremitted cash was received); null when the server sent none. */
    fun heldSince(o: RemittanceOverdueDto, zone: ZoneId): String? = o.heldSince?.let { OwnerFormat.date(it, zone) }?.takeIf { it != "—" }

    /**
     * Label/value rows in screen order ([flagged] formats the server timestamp). The cut-off row belongs to CUTOFF
     * flags only; HELD_TOO_LONG shows since when the cash is held and the allowance instead.
     */
    fun rows(o: RemittanceOverdueDto, flagged: (String) -> String = { it }, zone: ZoneId = ZoneId.systemDefault()): List<Pair<String, String>> = listOfNotNull(
        T.OVERDUE_CUSTODIAN to name(o),
        T.OVERDUE_NOT_REMITTED to amounts(o),
        T.OVERDUE_REASON to reason(o),
        T.OVERDUE_DAY to o.localDay,
        (T.OVERDUE_CUTOFF to T.hour(o.cutoffHour)).takeIf { !heldTooLong(o) },
        heldSince(o, zone)?.takeIf { heldTooLong(o) }?.let { T.OVERDUE_HELD_SINCE to it },
        o.maxHoldingDays?.takeIf { heldTooLong(o) }?.let { T.OVERDUE_ALLOWED to T.days(it) },
        T.OVERDUE_FLAGGED to flagged(o.flaggedAt),
    ).filter { it.second.isNotBlank() }

    fun line(o: RemittanceOverdueDto, zone: ZoneId = ZoneId.systemDefault()): String {
        if (!heldTooLong(o)) return T.overdueLine(o.cutoffHour, o.localDay)
        val since = heldSince(o, zone)
        val days = o.maxHoldingDays
        return if (since != null && days != null) T.overdueHeldLine(since, days) else T.OVERDUE_HELD_LINE_SHORT
    }

    fun footer(o: RemittanceOverdueDto, zone: ZoneId = ZoneId.systemDefault()): String = "${line(o, zone)} ${T.OVERDUE_HINT}"
}

/** My overdue remittance flag [id], read online (shown from this session's last read while it reloads). */
class RemittanceOverdueViewModel(private val field: FieldGraph, private val id: String) : ViewModel() {
    private val _flag = MutableStateFlow(field.accountability.savedOverdue(id))
    val flag: StateFlow<RemittanceOverdueDto?> = _flag.asStateFlow()
    private val _loading = MutableStateFlow(false)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()

    init { refresh() }

    fun refresh() {
        viewModelScope.launch {
            _loading.value = true
            field.accountability.remittanceOverdue(id)?.let { _flag.value = it }
            _loading.value = false
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RemittanceOverdueScreen(vm: RemittanceOverdueViewModel) {
    val flag by vm.flag.collectAsStateWithLifecycle()
    val loading by vm.loading.collectAsStateWithLifecycle()
    PullToRefreshBox(isRefreshing = loading, onRefresh = vm::refresh, modifier = Modifier.fillMaxSize()) {
        Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            val o = flag ?: return@Column
            Section(null, footer = RemittanceOverdueText.footer(o)) {
                Text(RemittanceOverdueText.name(o), style = AssetaType.headline, modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp))
                RemittanceOverdueText.rows(o, LocalTime::formatIso).forEach { (label, value) -> LabeledRow(label, value) }
            }
        }
    }
}
