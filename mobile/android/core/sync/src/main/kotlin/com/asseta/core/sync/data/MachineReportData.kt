package com.asseta.core.sync.data

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.domain.reports.MachineReportRules
import com.asseta.core.domain.reports.ReportState
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.SyncAccount
import com.asseta.core.model.sync.AvailableHoursDto
import com.asseta.core.model.sync.CreditInvoiceDto
import com.asseta.core.model.sync.CreditInvoicePaymentPayload
import com.asseta.core.model.sync.MachineReportDto
import com.asseta.core.model.sync.MachineReportLineDto
import com.asseta.core.model.sync.MachineReportOps
import com.asseta.core.model.sync.MachineReportPayload
import com.asseta.core.model.sync.MachineReportReasonDto
import com.asseta.core.model.sync.MachineReportStatusDto
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import java.math.BigDecimal

/** A MACHINE_REPORT this phone queued (until the server's copy replaces it). */
data class LocalReport(
    val operationId: String,
    val machineId: String,
    val status: ClientOperationStatus,
    val createdAtMs: Long,
    val payload: MachineReportPayload,
    val errorCode: String?,
    val error: String?,
) {
    /** Still to be decided by the server (not acknowledged, not refused). */
    val waiting: Boolean get() = status == ClientOperationStatus.PENDING || status == ClientOperationStatus.SENT || status == ClientOperationStatus.QUARANTINED
    val refused: Boolean get() = status == ClientOperationStatus.CONFLICT || status == ClientOperationStatus.FAILED
    val hours: BigDecimal get() = payload.lines.fold(BigDecimal.ZERO) { s, l -> s + (l.hours.toBigDecimalOrNull() ?: BigDecimal.ZERO) }
    val customerHours: BigDecimal
        get() = payload.lines.filter { it.kind == MachineReportLineDto.CUSTOMER }.fold(BigDecimal.ZERO) { s, l -> s + (l.hours.toBigDecimalOrNull() ?: BigDecimal.ZERO) }
}

/** A credit-invoice payment this phone queued. */
data class LocalInvoicePayment(val operationId: String, val status: ClientOperationStatus, val createdAtMs: Long, val payload: CreditInvoicePaymentPayload)

/** One of my machines with where it stands for its next report. */
data class ReportMachine(
    val status: MachineReportStatusDto,
    val state: ReportState,
    /** The newest report on this phone not yet replaced by the server's copy. */
    val local: LocalReport?,
    /** The rejected report to correct (same reading, new split). */
    val rejected: MachineReportDto?,
) {
    val id: String get() = status.machineId
    val code: String get() = status.machineCode ?: status.machineName ?: status.machineId.take(8)
    val label: String get() = listOfNotNull(status.machineCode, status.machineName).joinToString(" · ").ifEmpty { code }
    val decimals: Int get() = status.meterDecimalPlaces
    val previous: BigDecimal? get() = status.previousReading?.toBigDecimalOrNull()
}

/** Everything the machine report screens show, from the synced snapshots and this phone's queued reports. */
data class MachineReportView(
    val states: List<MachineReportStatusDto> = emptyList(),
    val reasons: List<MachineReportReasonDto> = emptyList(),
    val hours: List<AvailableHoursDto> = emptyList(),
    val myReports: List<MachineReportDto> = emptyList(),
    val local: List<LocalReport> = emptyList(),
    val invoices: List<CreditInvoiceDto> = emptyList(),
    val invoicePayments: List<LocalInvoicePayment> = emptyList(),
    val loaded: Boolean = false,
) {
    /** My machines with their state; [reminderDays] is the company's `machine_report_reminder_days`. */
    fun machines(reminderDays: Int?): List<ReportMachine> = states.map { s ->
        val local = local.filter { it.machineId == s.machineId && !acknowledgedByServer(it) }.maxByOrNull { it.createdAtMs }
        val rejected = s.rejectedReportId?.let { id -> myReports.firstOrNull { it.id == id } }
            ?: myReports.filter { it.machineId == s.machineId }.maxByOrNull { it.submittedAt }?.takeIf { it.status == MachineReportDto.REJECTED && it.correctedById == null }
        val state = MachineReportRules.state(
            previousReading = s.previousReading,
            pendingOnServer = s.pendingReportId != null,
            pendingOnPhone = local?.waiting == true,
            rejected = rejected != null,
            daysSinceReport = s.daysSinceReport,
            reminderDays = reminderDays,
        )
        ReportMachine(s, state, local, rejected)
    }.sortedWith(compareBy({ !it.state.needsReport }, { it.code }))

    /** A queued report the server already has (its copy is in my reports): the phone's row is no longer needed. */
    private fun acknowledgedByServer(r: LocalReport) = myReports.any { it.id == r.operationId }

    /**
     * Hours each customer can still get in a report on [machineId]: the server's available hours (per machine when the
     * company's scope is MACHINE) less what this phone's unsent reports already give them.
     */
    fun available(machineId: String): Map<String, BigDecimal> {
        val scoped = hours.filter { it.machineId == null || it.machineId == machineId }
        val base = scoped.groupBy { it.customerId }.mapValues { (_, rows) -> rows.fold(BigDecimal.ZERO) { s, r -> s + (r.available.toBigDecimalOrNull() ?: BigDecimal.ZERO) } }
        // CUSTOMER scope (rows without a machine): any of my unsent reports draws on the same hours; MACHINE scope: only this machine's.
        val customerScope = hours.none { it.machineId != null }
        val pending = local.filter { it.waiting && !acknowledgedByServer(it) && (customerScope || it.machineId == machineId) }.flatMap { r ->
            r.payload.lines.filter { it.kind == MachineReportLineDto.CUSTOMER && it.customerId != null }
        }.groupBy { it.customerId!! }.mapValues { (_, lines) -> lines.fold(BigDecimal.ZERO) { s, l -> s + (l.hours.toBigDecimalOrNull() ?: BigDecimal.ZERO) } }
        return base.mapValues { (id, v) -> (v - (pending[id] ?: BigDecimal.ZERO)).max(BigDecimal.ZERO) }
    }

    /** Customer names from the available-hours snapshot. */
    fun customerName(id: String): String? = hours.firstOrNull { it.customerId == id }?.customerName

    /** Open credit invoices less what this phone already queued against them (balance never below 0). */
    fun openInvoices(): List<Pair<CreditInvoiceDto, BigDecimal>> = invoices.map { inv ->
        val queued = invoicePayments.filter { it.payload.invoiceId == inv.id && it.status != ClientOperationStatus.ACKED && it.status != ClientOperationStatus.FAILED }
            .fold(BigDecimal.ZERO) { s, p -> s + (p.payload.amount.toBigDecimalOrNull() ?: BigDecimal.ZERO) }
        inv to ((inv.balance.toBigDecimalOrNull() ?: BigDecimal.ZERO) - queued).max(BigDecimal.ZERO)
    }.filter { it.second.signum() > 0 }
}

/** Reads the ADR-008 snapshots saved by sync and this phone's MACHINE_REPORT / CREDIT_INVOICE_PAYMENT operations. */
class MachineReportData(private val db: () -> AssetaDatabase, private val json: Json, private val account: () -> SyncAccount?) {
    fun observe(tenantId: String): Flow<MachineReportView> {
        val field = db().fieldDataDao()
        fun <T> kind(kind: String, serializer: KSerializer<T>): Flow<List<T>> =
            field.observeReferences(tenantId, kind).let { flow ->
                kotlinx.coroutines.flow.flow { flow.collect { rows -> emit(rows.mapNotNull { runCatching { json.decodeFromString(serializer, it.json) }.getOrNull() }) } }
            }
        val ops = db().clientOperationDao().observeByOpTypes(tenantId, ownerSubject(account), listOf(MachineReportOps.MACHINE_REPORT, MachineReportOps.CREDIT_INVOICE_PAYMENT))
        val snapshots = combine(
            kind(ServerDataWriter.KIND_REPORT_STATE, MachineReportStatusDto.serializer()),
            kind(ServerDataWriter.KIND_REPORT_REASON, MachineReportReasonDto.serializer()),
            kind(ServerDataWriter.KIND_REPORT_HOURS, com.asseta.core.model.sync.AvailableHoursDto.serializer()),
            kind(ServerDataWriter.KIND_MY_REPORT, MachineReportDto.serializer()),
            kind(ServerDataWriter.KIND_CREDIT_INVOICE, CreditInvoiceDto.serializer()),
        ) { states, reasons, hours, reports, invoices ->
            MachineReportView(
                states = states,
                reasons = reasons.filter { it.isActive }.sortedBy { it.name.lowercase() },
                hours = hours,
                myReports = reports.sortedByDescending { it.submittedAt },
                invoices = invoices.sortedBy { it.dueDate },
            )
        }
        return combine(snapshots, ops) { view, list -> view.copy(local = list.mapNotNull(::localReport), invoicePayments = list.mapNotNull(::localPayment), loaded = true) }
    }

    private fun localReport(op: ClientOperationEntity): LocalReport? {
        if (op.opType != MachineReportOps.MACHINE_REPORT) return null
        val payload = runCatching { json.decodeFromString(MachineReportPayload.serializer(), op.payloadJson) }.getOrNull() ?: return null
        return LocalReport(op.id, payload.machineId, op.status, op.createdAtDevice, payload, op.errorCode, op.lastError)
    }

    private fun localPayment(op: ClientOperationEntity): LocalInvoicePayment? {
        if (op.opType != MachineReportOps.CREDIT_INVOICE_PAYMENT) return null
        val payload = runCatching { json.decodeFromString(CreditInvoicePaymentPayload.serializer(), op.payloadJson) }.getOrNull() ?: return null
        return LocalInvoicePayment(op.id, op.status, op.createdAtDevice, payload)
    }
}
