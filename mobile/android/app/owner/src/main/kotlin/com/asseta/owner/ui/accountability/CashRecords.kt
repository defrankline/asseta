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
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.accountability.DisplayNames
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.domain.owner.RecordKinds
import com.asseta.core.model.owner.CashCustodyEntryDto
import com.asseta.core.model.owner.RemittanceOverdueDto
import com.asseta.core.model.sync.CashTransferDto
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.LabeledValue
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.approvals.ApprovalText
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.Serializable
import java.time.LocalDate
import java.time.ZoneId
import com.asseta.core.ui.R as CoreR

private val T = OwnerAccountabilityTexts

/** A read-only cash custody record (transfer or float) ready to show (DEC-030 G5: a notification opens it exactly). */
@Serializable
data class CashRecord(val headline: String, val status: String, val fields: List<DecisionField>, val note: String? = null)

/** Pure mapping of cash transfers, floats and overdue flags (unit-tested). Names first, short id only when null. */
object CashRecords {
    private fun money(amount: String, currency: String): String =
        amount.toBigDecimalOrNull()?.let { OwnerFormat.money(it, currency) } ?: "$amount $currency"

    private fun fields(vararg pairs: Pair<String, String?>): List<DecisionField> =
        pairs.mapNotNull { (l, v) -> v?.takeIf { it.isNotBlank() }?.let { DecisionField(l, it) } }

    fun transfer(t: CashTransferDto, zone: ZoneId) = CashRecord(
        money(t.amountDeclared, t.currency), t.status,
        fields(
            T.F_FROM to DisplayNames.of(t.fromStaffName, t.fromStaffId), T.F_TO to DisplayNames.of(t.toStaffName, t.toStaffId),
            T.F_DECLARED to money(t.amountDeclared, t.currency), T.F_RECEIVED to t.amountReceived?.let { money(it, t.currency) },
            T.F_TRANSFERRED to OwnerFormat.dateTime(t.transferredAt, zone), T.F_RECORDED_BY to DisplayNames.of(t.recordedByName, t.recordedBy),
            T.F_ACKNOWLEDGED_BY to DisplayNames.of(t.acknowledgedByName, t.acknowledgedBy),
        ),
        note = t.ackNote ?: t.note,
    )

    fun float(f: CashCustodyEntryDto, zone: ZoneId) = CashRecord(
        money(f.amount.toPlainString(), f.currency), f.ackStatus,
        fields(
            T.F_CUSTODIAN to DisplayNames.of(f.staffMemberName, f.staffMemberId.toString()),
            T.F_AMOUNT to money(f.amount.toPlainString(), f.currency), T.F_RECEIVED to f.amountReceived?.let { money(it.toPlainString(), f.currency) },
            T.F_ISSUED to OwnerFormat.dateTime(f.occurredAt, zone), T.F_RECORDED_BY to DisplayNames.of(f.createdByName, f.createdBy?.toString()),
            T.F_ACKNOWLEDGED_BY to DisplayNames.of(f.acknowledgedByName, f.acknowledgedBy?.toString()),
        ),
        note = f.note,
    )

    /** "TZS 50,000.00, USD 20.00" (the amounts still held when flagged). */
    fun amounts(o: RemittanceOverdueDto): String = o.amounts.joinToString(", ") { money(it.amount, it.currency) }

    fun overdueName(o: RemittanceOverdueDto): String = DisplayNames.of(o.staffMemberName, o.staffMemberId).orEmpty()

    /** Held longer than the allowance (DEC-031 D3) rather than past the daily cut-off. */
    fun heldTooLong(o: RemittanceOverdueDto): Boolean = o.reason == RemittanceOverdueDto.HELD_TOO_LONG

    fun overdueReason(o: RemittanceOverdueDto): String = if (heldTooLong(o)) T.OVERDUE_REASON_HELD else T.OVERDUE_REASON_CUTOFF

    private fun heldSince(o: RemittanceOverdueDto, zone: ZoneId): String? = o.heldSince?.let { OwnerFormat.date(it, zone) }?.takeIf { it != "—" }

    /** The cut-off row belongs to CUTOFF flags only; HELD_TOO_LONG shows since when the cash is held and the allowance. */
    fun overdueFields(o: RemittanceOverdueDto, zone: ZoneId): List<DecisionField> = fields(
        T.F_CUSTODIAN to overdueName(o), T.F_NOT_REMITTED to amounts(o), T.F_REASON to overdueReason(o), T.F_DAY to o.localDay,
        T.F_CUTOFF to T.hour(o.cutoffHour).takeIf { !heldTooLong(o) },
        T.F_HELD_SINCE to heldSince(o, zone)?.takeIf { heldTooLong(o) },
        T.F_ALLOWED to o.maxHoldingDays?.takeIf { heldTooLong(o) }?.let(T::days),
        T.F_FLAGGED to OwnerFormat.dateTime(o.flaggedAt, zone),
    )

    /** The detail footer: the cut-off line, or since when the cash is held against the allowance. */
    fun overdueLine(o: RemittanceOverdueDto, zone: ZoneId): String {
        if (!heldTooLong(o)) return T.overdueLine(o.cutoffHour, o.localDay)
        val since = heldSince(o, zone)
        val days = o.maxHoldingDays
        return if (since != null && days != null) T.overdueHeldLine(since, days) else T.OVERDUE_HELD_LINE_SHORT
    }
}

class CashRecordViewModel(data: OwnerData, val kind: String, id: String, refreshOn: Flow<Unit>) :
    SnapshotViewModel<CashRecord>({ data.cashRecord(kind == RecordKinds.CASH_FLOAT, id) }, refreshOn)

@Composable
fun CashRecordScreen(vm: CashRecordViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { record ->
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
            item {
                SectionCard(null) {
                    Text(record.headline, style = AssetaType.headline)
                    record.fields.forEach { KeyValue(it.label, it.value) }
                    record.note?.takeIf { it.isNotBlank() }?.let { KeyValue(T.F_NOTE, it) }
                    LabeledValue(T.F_STATUS) { StatusPill(OwnerFormat.humanize(record.status), ApprovalText.statusColor(record.status)) }
                }
            }
        }
    }
}

/** Today's overdue remittances (custodians flagged after the tenant's cut-off). */
class RemittanceOverdueListViewModel(data: OwnerData, refreshOn: Flow<Unit>, today: () -> LocalDate = { LocalDate.now() }) :
    SnapshotViewModel<List<RemittanceOverdueDto>>({ data.remittanceOverdue(today()) }, refreshOn)

class RemittanceOverdueViewModel(data: OwnerData, id: String, refreshOn: Flow<Unit>) :
    SnapshotViewModel<RemittanceOverdueDto>({ data.remittanceOverdueFlag(id) }, refreshOn)

@Composable
fun RemittanceOverdueListScreen(vm: RemittanceOverdueListViewModel, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { list ->
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
            if (list.isEmpty()) {
                item { EmptyState(T.OVERDUE_EMPTY, icon = CoreR.drawable.ic_empty_tray) }
                return@LazyColumn
            }
            groupedSection(
                keyPrefix = "overdue", header = null,
                items = list.map { o ->
                    GroupedItem(o.id, onClick = { onOpen(OwnerDestination.RemittanceOverdue(o.id)) }) {
                        Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(CashRecords.overdueName(o), style = AssetaType.headline)
                            Text(CashRecords.amounts(o), style = AssetaType.subheadline, color = palette.secondaryText)
                            Text(CashRecords.overdueReason(o), style = AssetaType.caption, color = palette.secondaryText)
                        }
                    }
                },
            )
        }
    }
}

@Composable
fun RemittanceOverdueScreen(vm: RemittanceOverdueViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { o ->
        val zone = ZoneId.systemDefault()
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
            item {
                SectionCard(null, footer = CashRecords.overdueLine(o, zone)) {
                    Text(CashRecords.overdueName(o), style = AssetaType.headline)
                    CashRecords.overdueFields(o, zone).forEach { KeyValue(it.label, it.value) }
                }
            }
        }
    }
}
