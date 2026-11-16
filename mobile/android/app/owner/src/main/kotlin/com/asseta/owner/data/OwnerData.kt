package com.asseta.owner.data

import com.asseta.core.model.owner.AlertActionIn
import com.asseta.core.model.owner.AlertDto
import com.asseta.core.model.owner.AnomalyCaseDetailDto
import com.asseta.core.model.owner.AnomalyCaseDto
import com.asseta.core.model.owner.ApprovalDecisionIn
import com.asseta.core.model.owner.ApprovalRequestDto
import com.asseta.core.model.owner.CashFloatIn
import com.asseta.core.model.owner.CashHandoverDto
import com.asseta.core.model.owner.CashSupervisorSummaryDto
import com.asseta.core.model.owner.ExceptionDto
import com.asseta.core.model.owner.ExpenseDto
import com.asseta.core.model.owner.FuelEventDto
import com.asseta.core.model.owner.HistoryDto
import com.asseta.core.model.owner.MachineDto
import com.asseta.core.model.owner.MachineMapDto
import com.asseta.core.model.owner.MeterCaptureDto
import com.asseta.core.model.owner.MeterResetDecisionIn
import com.asseta.core.model.owner.MeterResetDto
import com.asseta.core.model.owner.NotificationDto
import com.asseta.core.model.owner.PageDto
import com.asseta.core.model.owner.CustomerPaymentDto
import com.asseta.core.model.owner.PaymentReview
import com.asseta.core.model.owner.SettlementDecisionIn
import com.asseta.core.model.owner.TenantOverviewDto
import com.asseta.core.model.owner.AccountabilitySummaryDto
import com.asseta.core.model.owner.DecisionIn
import com.asseta.core.model.owner.MeterDecisionIn
import com.asseta.core.model.owner.RemittanceOverdueDto
import com.asseta.core.model.owner.DailyMachineSheetDetailDto
import com.asseta.core.model.owner.DailyMachineSheetRowDto
import com.asseta.core.model.owner.NonRevenueDecisionIn
import com.asseta.core.model.owner.RevenueDecisionIn
import com.asseta.core.model.owner.RevenueDifferenceDto
import com.asseta.core.model.owner.RevenueExplanationIn
import com.asseta.core.model.owner.RevenueReasonDto
import com.asseta.owner.ui.accountability.CashRecord
import com.asseta.owner.ui.accountability.CashRecords
import com.asseta.owner.ui.accountability.DecisionItem
import com.asseta.owner.ui.accountability.DecisionKind
import com.asseta.owner.ui.accountability.DecisionMapper
import com.asseta.core.model.sync.CreditActivationIn
import com.asseta.core.model.sync.CreditInvoiceDto
import com.asseta.core.model.sync.CreditInvoicePaymentIn
import com.asseta.core.model.sync.CustomerHoursSummaryDto
import com.asseta.core.model.sync.MachineReportDecisionIn
import com.asseta.core.model.sync.MachineReportDto
import com.asseta.core.model.sync.MachineReportRejectIn
import com.asseta.core.model.sync.MachineReportStatusDto
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import java.time.Instant
import java.time.LocalDate
import java.time.temporal.ChronoUnit

/**
 * Cash handovers with the custodians' names ([names] staff member id -> name, from the supervisor cash summary; a
 * handover whose custodian is not there shows "A supervisor").
 */
@Serializable
data class HandoverList(val items: List<CashHandoverDto>, val names: Map<String, String> = emptyMap()) {
    fun name(h: CashHandoverDto): String? = h.staffMemberName ?: names[h.staffMemberId.toString()]
}

/** The ledger of one machine-day ([day] null: the server has no row for it). */
@Serializable
data class MachineDayAllocations(
    val day: com.asseta.core.model.owner.AllocationDayDto? = null,
    val entries: List<com.asseta.core.model.owner.WorkAllocationDto> = emptyList(),
)

/** A purchase with its reversed payments ([reversedPayments] payment id -> when; only those that could be read). */
@Serializable
data class HoursPurchaseDetail(
    val purchase: com.asseta.core.model.owner.OwnerHoursPurchaseDto,
    val reversedPayments: Map<String, String> = emptyMap(),
)

/** Open meter exceptions ([jobNumbers]: kept so snapshots saved before ADR-008 still decode; no longer filled). */
@Serializable
data class ExceptionList(val items: List<ExceptionDto>, val jobNumbers: Map<String, String> = emptyMap()) {
    fun jobNumber(e: ExceptionDto): String? = e.jobId?.let { jobNumbers[it.toString()] }
}

/** ADR-008: a machine report with its meter reading when the role may read it ([capture] null otherwise). */
@Serializable
data class MachineReportDetail(val report: com.asseta.core.model.sync.MachineReportDto, val capture: MeterCaptureDto? = null)

/** ADR-008: a credit sale waiting for its credit part to be made usable, with what is left of the customer's limit. */
@Serializable
data class CreditSale(
    val purchase: com.asseta.core.model.owner.OwnerHoursPurchaseDto,
    /** `available` of the customer's credit exposure (null: no arrangement or not readable). */
    val limitLeft: String? = null,
)

/**
 * Typed owner reads for one tenant, each with a stable snapshot key (the offline cache), plus the few allowed
 * mutations. Keys never contain user input except server ids.
 */
class OwnerData(private val repo: OwnerRepository, val tenantId: String, private val clock: () -> Long = System::currentTimeMillis) {
    suspend fun overview(): Load<TenantOverviewDto> = repo.load(tenantId, "overview", TenantOverviewDto.serializer()) { overview() }

    suspend fun fleet(): Load<List<MachineMapDto>> = repo.load(tenantId, "fleet", ListSerializer(MachineMapDto.serializer())) { fleetMap() }

    suspend fun machineStatus(id: String): Load<MachineMapDto> = repo.load(tenantId, "machine:$id", MachineMapDto.serializer()) { machineStatus(id) }

    suspend fun machineInfo(id: String): Load<MachineDto> = repo.load(tenantId, "machine_info:$id", MachineDto.serializer()) { machine(id) }

    suspend fun machineAlerts(id: String): Load<PageDto<AlertDto>> =
        repo.load(tenantId, "machine_alerts:$id", PageDto.serializer(AlertDto.serializer())) { alerts(machineId = id, pageSize = 5) }

    suspend fun machineReadings(id: String): Load<PageDto<MeterCaptureDto>> =
        repo.load(tenantId, "machine_readings:$id", PageDto.serializer(MeterCaptureDto.serializer())) { meterCaptures(machineId = id, pageSize = 5) }

    /** Last 24 h track (bounded; a payload above the cache limit is simply not cached). */
    suspend fun machineTrack(id: String): Load<HistoryDto> {
        val to = Instant.ofEpochMilli(clock()).truncatedTo(ChronoUnit.SECONDS)
        val from = to.minus(24, ChronoUnit.HOURS)
        return repo.load(tenantId, "machine_track:$id", HistoryDto.serializer()) { machineHistory(id, from.toString(), to.toString()) }
    }

    /** Meter exceptions, [status] OPEN or null (all), optionally of one job. */
    suspend fun exceptions(status: String?, jobId: String?): Load<PageDto<ExceptionDto>> =
        repo.load(tenantId, "exceptions:${status ?: "ALL"}:${jobId ?: "ALL"}", PageDto.serializer(ExceptionDto.serializer())) {
            exceptions(status = status, jobId = jobId, pageSize = LIST_PAGE)
        }

    /** Expenses, [status] PENDING_APPROVAL (cached as "expenses:PENDING", as on iOS) or null (all). */
    suspend fun expenses(status: String?): Load<PageDto<ExpenseDto>> {
        val key = when (status) {
            null -> "ALL"
            "PENDING_APPROVAL" -> "PENDING"
            else -> status
        }
        return repo.load(tenantId, "expenses:$key", PageDto.serializer(ExpenseDto.serializer())) { expenses(status = status, pageSize = LIST_PAGE) }
    }

    suspend fun fuel(): Load<PageDto<FuelEventDto>> =
        repo.load(tenantId, "fuel:ALL", PageDto.serializer(FuelEventDto.serializer())) { fuelEvents(pageSize = LIST_PAGE) }

    /** Meter reset requests, [status] PENDING or null (all). */
    suspend fun meterResets(status: String?): Load<List<MeterResetDto>> =
        repo.load(tenantId, "meter_resets:${status ?: "ALL"}", ListSerializer(MeterResetDto.serializer())) { meterResets(status) }

    /** Cash with each supervisor over the local days [from]..[to]; [period] names the cached snapshot. */
    suspend fun cash(period: String, from: java.time.LocalDate, to: java.time.LocalDate): Load<List<CashSupervisorSummaryDto>> =
        repo.load(tenantId, "cash:$period", ListSerializer(CashSupervisorSummaryDto.serializer())) { cashSupervisorSummary(from.toString(), to.toString()) }

    /**
     * Cash handovers, [status] CLAIMED (waiting for a decision) or null (all), with the custodians' names. The names
     * come from today's supervisor cash summary and are best effort.
     */
    suspend fun handovers(status: String?): Load<HandoverList> =
        repo.load(tenantId, "handovers:${status ?: "ALL"}", HandoverList.serializer()) {
            val items = cashHandovers(status = status, pageSize = LIST_PAGE).items
            val today = java.time.LocalDate.ofInstant(Instant.ofEpochMilli(clock()), java.time.ZoneId.systemDefault()).toString()
            val names = if (items.isEmpty()) {
                emptyMap()
            } else {
                runCatching { cashSupervisorSummary(today, today) }.getOrDefault(emptyList())
                    .associate { it.staffMemberId.toString() to it.staffName }
            }
            HandoverList(items, names)
        }

    /** Customer payments waiting to be confirmed (CLAIMED), newest first. */
    suspend fun paymentsToConfirm(): Load<PageDto<CustomerPaymentDto>> =
        repo.load(tenantId, "payments:CLAIMED", PageDto.serializer(CustomerPaymentDto.serializer())) { customerPayments(status = "CLAIMED", pageSize = LIST_PAGE) }

    /** Petty cash fundings / top-ups (PROPOSED) and fund adjustments (PENDING) waiting for approval (DEC-033). */
    suspend fun pettyCashToApprove(): Load<com.asseta.owner.ui.approvals.PettyCashQueue> =
        repo.load(tenantId, "petty_cash:to_approve", com.asseta.owner.ui.approvals.PettyCashQueue.serializer()) {
            com.asseta.owner.ui.approvals.PettyCashQueue(
                pettyCashMovements(status = "PROPOSED", pageSize = LIST_PAGE).items,
                pettyCashAdjustments(status = "PENDING", pageSize = LIST_PAGE).items,
            )
        }

    /** One petty cash movement with the approved spending behind a top-up (best effort; never fails the movement). */
    suspend fun pettyCashMovementReview(id: String): Load<com.asseta.core.model.owner.PettyCashMovementReview> =
        repo.load(tenantId, "petty_cash_movement:$id", com.asseta.core.model.owner.PettyCashMovementReview.serializer()) {
            val movement = pettyCashMovement(id)
            val expenses = if (movement.kind == "TOP_UP") {
                runCatching { pettyCashMovementExpenses(id) }.onFailure { if (it is kotlinx.coroutines.CancellationException) throw it }
            } else Result.success(emptyList())
            com.asseta.core.model.owner.PettyCashMovementReview(movement, expenses.getOrDefault(emptyList()), expenses.isFailure)
        }

    suspend fun pettyCashAdjustmentReview(id: String): Load<com.asseta.core.model.owner.PettyCashAdjustmentReviewDto> =
        repo.load(tenantId, "petty_cash_adjustment:$id", com.asseta.core.model.owner.PettyCashAdjustmentReviewDto.serializer()) { pettyCashAdjustment(id) }

    /** Approve or reject a petty cash movement / adjustment; a rejection carries the reason. */
    suspend fun decidePettyCashMovement(id: String, approve: Boolean, note: String?) =
        repo.act { decidePettyCashMovement(id, com.asseta.core.model.owner.PettyCashDecisionIn(approve, note?.trim()?.takeIf { it.isNotEmpty() })) }

    suspend fun decidePettyCashAdjustment(id: String, approve: Boolean, note: String?) =
        repo.act { decidePettyCashAdjustment(id, com.asseta.core.model.owner.PettyCashDecisionIn(approve, note?.trim()?.takeIf { it.isNotEmpty() })) }

    /** One payment by id, with its evidence photos and the invoice numbers (both read beside it; never fails the payment). */
    suspend fun paymentReview(id: String): Load<PaymentReview> =
        repo.load(tenantId, "payment:$id", PaymentReview.serializer()) {
            val payment = customerPaymentDetail(id)
            val evidence = runCatching { paymentEvidence(id).map { it.attachmentId } }
                .onFailure { if (it is kotlinx.coroutines.CancellationException) throw it }
            val invoices = payment.allocations.filter { it.releasedAt == null }.map { it.invoiceId.toString() }.distinct().mapNotNull { invoice ->
                runCatching { invoiceNumber(invoice).invoiceNumber }.getOrNull()?.takeIf { it.isNotBlank() }?.let { invoice to it }
            }.toMap()
            PaymentReview(payment, evidence.getOrDefault(emptyList()), evidence.isFailure, invoices)
        }

    /** Open exceptions for the Approvals section. */
    suspend fun openExceptions(): Load<ExceptionList> =
        repo.load(tenantId, "exceptions_open", ExceptionList.serializer()) { ExceptionList(exceptions(status = "OPEN", pageSize = LIST_PAGE).items) }

    suspend fun alerts(status: String?): Load<PageDto<AlertDto>> =
        repo.load(tenantId, "alerts:${status ?: "ALL"}", PageDto.serializer(AlertDto.serializer())) { alerts(status = status, pageSize = LIST_PAGE) }

    /** The latest 200 alerts of any status; there is no single-alert endpoint, so the detail screen looks here. */
    suspend fun recentAlerts(): Load<PageDto<AlertDto>> =
        repo.load(tenantId, "alerts_recent", PageDto.serializer(AlertDto.serializer())) { alerts(status = null, pageSize = DETAIL_PAGE) }

    suspend fun approvals(status: String?): Load<PageDto<ApprovalRequestDto>> =
        repo.load(tenantId, "approvals:${status ?: "ALL"}", PageDto.serializer(ApprovalRequestDto.serializer())) { approvals(status = status, pageSize = LIST_PAGE) }

    /** The latest 200 requests of any status (no single-request endpoint). */
    suspend fun recentApprovals(): Load<PageDto<ApprovalRequestDto>> =
        repo.load(tenantId, "approvals_recent", PageDto.serializer(ApprovalRequestDto.serializer())) { approvals(status = null, pageSize = DETAIL_PAGE) }

    suspend fun cases(status: String?): Load<PageDto<AnomalyCaseDto>> =
        repo.load(tenantId, "cases:${status ?: "ALL"}", PageDto.serializer(AnomalyCaseDto.serializer())) { cases(status = status, pageSize = LIST_PAGE) }

    suspend fun case(id: String): Load<AnomalyCaseDetailDto> = repo.load(tenantId, "case:$id", AnomalyCaseDetailDto.serializer()) { case(id) }

    suspend fun notifications(): Load<PageDto<NotificationDto>> =
        repo.load(tenantId, "notifications", PageDto.serializer(NotificationDto.serializer())) { notifications(pageSize = LIST_PAGE) }

    // --- accountability (Approvals sections, decision screens, dashboard) ----------------------------------------
    /** Requests of [kind] waiting for a decision, ready to show (cached per kind for offline viewing). */
    suspend fun decisions(kind: DecisionKind): Load<List<DecisionItem>> {
        val zone = java.time.ZoneId.systemDefault()
        val status = kind.pendingStatus
        return repo.load(tenantId, "decisions:${kind.code}", ListSerializer(DecisionItem.serializer())) {
            when (kind) {
                DecisionKind.DISCOUNT -> customerDiscounts(status).items.map { DecisionMapper.discount(it, zone) }
                DecisionKind.CREDIT -> creditArrangements(status).items.map { DecisionMapper.credit(it, zone) }
                DecisionKind.HOURS_TRANSFER -> hoursTransfers(status).items.map(DecisionMapper::hoursTransfer)
                DecisionKind.CANCELLATION -> hoursCancellations(status).items.map(DecisionMapper::cancellation)
                DecisionKind.BASELINE -> meterBaselines(status).items.map { DecisionMapper.baseline(it, zone) }
                DecisionKind.CLASSIFICATION -> engineHourClassifications(status).items.map { DecisionMapper.classification(it, zone) }
                DecisionKind.CORRECTION -> meterCorrections(status).items.map(DecisionMapper::correction)
                DecisionKind.WRITE_OFF -> cashVariances(status).items.map(DecisionMapper::writeOff)
                DecisionKind.VARIANCE_CLOSURE -> cashVariances(status).items.map(DecisionMapper::varianceClosure)
                // No server filter on the partial approval: the newest remittances, those whose reason waits.
                DecisionKind.PARTIAL_REMITTANCE -> cashHandovers(pageSize = LIST_PAGE).items.filter { it.partialApproval?.status == "PENDING" }.map(DecisionMapper::partialRemittance)
                DecisionKind.RETENTION -> cashRetentions(status).items.map { DecisionMapper.retention(it, zone) }
                DecisionKind.ADJUSTMENT -> custodyAdjustments(status).items.map { DecisionMapper.adjustment(it, zone) }
                // Waiting for someone: to explain (OPEN) and explanations waiting for a decision.
                DecisionKind.REVENUE_DIFFERENCE -> (revenueDifferences("OPEN").items + revenueDifferences(status).items)
                    .map { DecisionMapper.revenueDifference(it, zone) }
                DecisionKind.NON_REVENUE -> nonRevenueApprovals(status).items.map { DecisionMapper.nonRevenue(it, zone) }
                DecisionKind.DAILY_REPORT -> dailyReports(status = status, pageSize = LIST_PAGE).items.map(DecisionMapper::dailyReport)
                DecisionKind.ALLOCATION_CORRECTION -> DecisionMapper.allocationCorrections(workAllocations(status = status, pageSize = LIST_PAGE).items)
                DecisionKind.ADJUSTMENT_REQUEST -> adjustmentRequests(status, LIST_PAGE).items.map(com.asseta.owner.ui.accountability.AdjustmentPresentation::item)
            }
        }
    }

    /**
     * One request of [kind] by id (any status; the exact record a notification names), as a one-item list so the
     * decision screen keeps its shape. Cached per record for offline viewing.
     */
    suspend fun decision(kind: DecisionKind, id: String): Load<List<DecisionItem>> {
        val zone = java.time.ZoneId.systemDefault()
        return repo.load(tenantId, "decision:${kind.code}:$id", ListSerializer(DecisionItem.serializer())) {
            listOf(
                when (kind) {
                    DecisionKind.DISCOUNT -> DecisionMapper.discount(customerDiscount(id), zone)
                    DecisionKind.CREDIT -> DecisionMapper.credit(creditArrangement(id), zone)
                    DecisionKind.HOURS_TRANSFER -> DecisionMapper.hoursTransfer(hoursTransfer(id))
                    DecisionKind.CANCELLATION -> DecisionMapper.cancellation(hoursCancellation(id))
                    DecisionKind.BASELINE -> DecisionMapper.baseline(meterBaseline(id), zone)
                    DecisionKind.CLASSIFICATION -> DecisionMapper.classification(engineHourClassification(id), zone)
                    DecisionKind.CORRECTION -> DecisionMapper.correction(meterCorrection(id))
                    DecisionKind.WRITE_OFF, DecisionKind.VARIANCE_CLOSURE -> DecisionMapper.variance(
                        cashVariance(id), runCatching { cashVarianceHistory(id) }.getOrDefault(emptyList()), zone, asClosure = kind == DecisionKind.VARIANCE_CLOSURE,
                    )
                    DecisionKind.PARTIAL_REMITTANCE -> DecisionMapper.partialRemittance(cashHandover(id))
                    DecisionKind.RETENTION -> DecisionMapper.retention(cashRetention(id), zone)
                    DecisionKind.ADJUSTMENT -> DecisionMapper.adjustment(custodyAdjustment(id), zone)
                    DecisionKind.REVENUE_DIFFERENCE -> DecisionMapper.revenueDifference(revenueDifference(id), zone)
                    DecisionKind.NON_REVENUE -> DecisionMapper.nonRevenue(nonRevenueApproval(id), zone)
                    DecisionKind.DAILY_REPORT -> DecisionMapper.dailyReport(dailyReport(id))
                    DecisionKind.ALLOCATION_CORRECTION -> {
                        val c = workAllocationCorrection(id)
                        val original = c.supersedesId?.let { old -> runCatching { workAllocation(old) }.getOrNull() }
                        DecisionMapper.allocationCorrection(c.groupId, c.status, c.entries, original)
                    }
                    DecisionKind.ADJUSTMENT_REQUEST -> com.asseta.owner.ui.accountability.AdjustmentPresentation.item(adjustmentRequest(id))
                },
            )
        }
    }

    /** One cash transfer or float ([float]) as a read-only record (DEC-030 G5). */
    suspend fun cashRecord(float: Boolean, id: String): Load<CashRecord> {
        val zone = java.time.ZoneId.systemDefault()
        return repo.load(tenantId, "cash_record:${if (float) "float" else "transfer"}:$id", CashRecord.serializer()) {
            if (float) CashRecords.float(cashFloat(id), zone) else CashRecords.transfer(cashTransfer(id), zone)
        }
    }

    /** Custodians flagged for cash not remitted by the cut-off on the local day [day] (tenant.finance.read). */
    suspend fun remittanceOverdue(day: java.time.LocalDate): Load<List<RemittanceOverdueDto>> =
        repo.load(tenantId, "remittance_overdue:$day", ListSerializer(RemittanceOverdueDto.serializer())) {
            remittanceOverdue(dayFrom = day.toString(), dayTo = day.toString(), pageSize = LIST_PAGE).items
        }

    suspend fun remittanceOverdueFlag(id: String): Load<RemittanceOverdueDto> =
        repo.load(tenantId, "remittance_overdue_flag:$id", RemittanceOverdueDto.serializer()) { remittanceOverdueFlag(id) }

    /** One remittance by id (a notification may name one that is in neither list). */
    suspend fun handover(id: String): Load<HandoverList> =
        repo.load(tenantId, "handover:$id", HandoverList.serializer()) { HandoverList(listOf(cashHandover(id))) }

    /** Approve or reject a request of [kind] (online only); meter decisions carry their note as APPROVE/REJECT. */
    suspend fun decide(kind: DecisionKind, id: String, approve: Boolean, note: String): ActionResult<Unit> {
        val text = note.trim().takeIf { it.isNotEmpty() }
        val decision = DecisionIn(approve, text)
        val meter = MeterDecisionIn(if (approve) MeterDecisionIn.APPROVE else MeterDecisionIn.REJECT, note.trim())
        return repo.act {
            when (kind) {
                DecisionKind.DISCOUNT -> decideCustomerDiscount(id, decision)
                DecisionKind.CREDIT -> decideCreditArrangement(id, decision)
                DecisionKind.HOURS_TRANSFER -> decideHoursTransfer(id, decision)
                DecisionKind.CANCELLATION -> decideHoursCancellation(id, decision)
                DecisionKind.BASELINE -> decideMeterBaseline(id, meter)
                DecisionKind.CLASSIFICATION -> decideEngineHourClassification(id, meter)
                DecisionKind.CORRECTION -> decideMeterCorrection(id, meter)
                DecisionKind.WRITE_OFF -> decideCashWriteOff(id, decision)
                DecisionKind.VARIANCE_CLOSURE -> decideCashVarianceClosure(id, decision)
                DecisionKind.PARTIAL_REMITTANCE -> decidePartialRemittanceReason(id, decision)
                DecisionKind.RETENTION -> decideCashRetention(id, decision)
                DecisionKind.ADJUSTMENT -> decideCustodyAdjustment(id, decision)
                DecisionKind.REVENUE_DIFFERENCE -> decideRevenueDifference(id, RevenueDecisionIn(meter.decision, meter.note))
                DecisionKind.NON_REVENUE -> decideNonRevenue(id, NonRevenueDecisionIn(meter.decision, meter.note))
                DecisionKind.DAILY_REPORT -> reviewDailyReport(
                    id, com.asseta.core.model.owner.DailyReportReviewIn(if (approve) com.asseta.core.model.owner.DailyReportReviewIn.REVIEWED else com.asseta.core.model.owner.DailyReportReviewIn.RETURNED, note.trim()),
                )
                DecisionKind.ALLOCATION_CORRECTION -> decideWorkAllocationCorrection(id, meter)
                DecisionKind.ADJUSTMENT_REQUEST -> decideAdjustmentRequest(
                    id, com.asseta.core.model.owner.AdjustmentDecisionIn(meter.decision, text),
                )
            }
            Unit
        }
    }

    /** The proposer takes back an adjustment request that still waits (online only). */
    suspend fun withdrawAdjustmentRequest(id: String, reason: String) =
        repo.act { withdrawAdjustmentRequest(id, com.asseta.core.model.owner.AdjustmentWithdrawIn(reason.trim())) }

    // --- revenue reconciliation (DEC-031 Phase 1; online actions, cached reads) ----------------------------------
    /** One revenue difference (any status), cached per record for offline viewing. */
    suspend fun revenueDifference(id: String): Load<RevenueDifferenceDto> =
        repo.load(tenantId, "revenue_difference:$id", RevenueDifferenceDto.serializer()) { revenueDifference(id) }

    /** The tenant's active revenue reasons, by name (the explain picker). */
    suspend fun revenueReasons(): Load<List<RevenueReasonDto>> =
        repo.load(tenantId, "revenue_reasons", ListSerializer(RevenueReasonDto.serializer())) {
            revenueReasons(pageSize = LIST_PAGE).items.filter { it.isActive }.sortedBy { it.name.lowercase() }
        }

    /** Explain an OPEN difference (tenant.revenue.explain); someone else decides. */
    suspend fun explainRevenue(id: String, reasonId: String, note: String) =
        repo.act { explainRevenueDifference(id, RevenueExplanationIn(reasonId, note.trim())) }

    /** APPROVE / REJECT the explanation, or CONFIRM the difference (tenant.revenue.decide; never the explainer). */
    suspend fun decideRevenue(id: String, decision: String, note: String) =
        repo.act { decideRevenueDifference(id, RevenueDecisionIn(decision, note.trim())) }

    /** The daily machine sheet of [machineId] for the local days [from]..[to] (newest first). */
    suspend fun dailySheet(machineId: String, from: java.time.LocalDate, to: java.time.LocalDate): Load<List<DailyMachineSheetRowDto>> =
        repo.load(tenantId, "daily_sheet:$machineId", ListSerializer(DailyMachineSheetRowDto.serializer())) {
            dailyMachineSheet(machineId = machineId, dayFrom = from.toString(), dayTo = to.toString(), pageSize = LIST_PAGE).items
                .sortedByDescending { it.day }
        }

    /** One machine on one local day, with its readings, jobs, money and flags. */
    suspend fun sheetDay(machineId: String, day: String): Load<DailyMachineSheetDetailDto> =
        repo.load(tenantId, "sheet_day:$machineId:$day", DailyMachineSheetDetailDto.serializer()) { dailyMachineSheetDay(machineId, day) }

    // --- work allocation ledger and daily reports (DEC-032 Phase 1) ---------------------------------------------------
    suspend fun dailyReport(id: String): Load<com.asseta.core.model.owner.DailyReportDto> =
        repo.load(tenantId, "daily_report:$id", com.asseta.core.model.owner.DailyReportDto.serializer()) { dailyReport(id) }

    /** REVIEWED or RETURNED with a note (tenant.meter.review; never the submitter). */
    suspend fun reviewDailyReport(id: String, decision: String, note: String) =
        repo.act { reviewDailyReport(id, com.asseta.core.model.owner.DailyReportReviewIn(decision, note.trim())) }

    /** One machine on one local day of the ledger: the reconciliation row and its active allocations. */
    suspend fun machineDayAllocations(machineId: String, day: String): Load<MachineDayAllocations> =
        repo.load(tenantId, "allocations:$machineId:$day", MachineDayAllocations.serializer()) {
            MachineDayAllocations(
                workAllocationReconciliation(day, day, machineId).firstOrNull(),
                workAllocations(machineId = machineId, from = day, to = day, pageSize = LIST_PAGE).items.sortedBy { it.startAt },
            )
        }

    /** The machine's days of the ledger for [from]..[to], newest first (the day list while revenue checks are off). */
    suspend fun allocationDays(machineId: String, from: java.time.LocalDate, to: java.time.LocalDate): Load<List<com.asseta.core.model.owner.AllocationDayDto>> =
        repo.load(tenantId, "allocation_days:$machineId", ListSerializer(com.asseta.core.model.owner.AllocationDayDto.serializer())) {
            workAllocationReconciliation(from.toString(), to.toString(), machineId).sortedByDescending { it.day }
        }

    // --- customer hours, read-only (DEC-031 P4) --------------------------------------------------------------------
    /** Open purchases with hours left or in use by running jobs, newest first. */
    suspend fun hoursPurchases(): Load<List<com.asseta.core.model.owner.OwnerHoursPurchaseDto>> =
        repo.load(tenantId, "hours_purchases", ListSerializer(com.asseta.core.model.owner.OwnerHoursPurchaseDto.serializer())) {
            com.asseta.owner.ui.accountability.HoursPresentation.open(ownerHoursPurchases(pageSize = LIST_PAGE).items)
        }

    /** [payments]: also read the released payments to mark reversed ones (best effort, bounded). */
    suspend fun hoursPurchase(id: String, payments: Boolean = false): Load<HoursPurchaseDetail> =
        repo.load(tenantId, "hours_purchase_detail:$id", HoursPurchaseDetail.serializer()) {
            val purchase = hoursPurchase(id)
            val released = if (payments) purchase.allocations.filter { it.releasedAt != null }.map { it.paymentId }.distinct().take(MAX_PAYMENT_LOOKUPS) else emptyList()
            HoursPurchaseDetail(
                purchase,
                released.mapNotNull { paymentId -> runCatching { customerPayment(paymentId) }.getOrNull()?.reversedAt?.let { paymentId to it } }.toMap(),
            )
        }

    /** One customer's hours statement for the local days [from]..[to] (cached per customer and period). */
    suspend fun hoursStatement(customerId: String, from: java.time.LocalDate, to: java.time.LocalDate): Load<com.asseta.core.model.owner.HoursStatementDto> =
        repo.load(tenantId, "hours_statement:$customerId:$from:$to", com.asseta.core.model.owner.HoursStatementDto.serializer()) {
            customerHoursStatement(customerId, from.toString(), to.toString())
        }

    /** The same statement as PDF bytes (online only, never cached). */
    suspend fun hoursStatementPdf(customerId: String, from: java.time.LocalDate, to: java.time.LocalDate): ActionResult<ByteArray> =
        repo.act { customerHoursStatementPdf(customerId, from.toString(), to.toString()).use { it.bytes() } }

    // --- oversight, read-only (DEC-031 Phase 5) -------------------------------------------------------------------
    /** One row per person for the local days [from]..[to] (cached per period). */
    suspend fun scorecard(from: java.time.LocalDate, to: java.time.LocalDate): Load<List<com.asseta.core.model.owner.ScorecardRowDto>> =
        repo.load(tenantId, "scorecard:$from:$to", ListSerializer(com.asseta.core.model.owner.ScorecardRowDto.serializer())) {
            scorecard(from.toString(), to.toString(), pageSize = LIST_PAGE).items
        }

    suspend fun scorecardPerson(staffId: String, from: java.time.LocalDate, to: java.time.LocalDate): Load<com.asseta.core.model.owner.ScorecardDetailDto> =
        repo.load(tenantId, "scorecard_person:$staffId:$from:$to", com.asseta.core.model.owner.ScorecardDetailDto.serializer()) {
            scorecardDetail(staffId, from.toString(), to.toString())
        }

    suspend fun idleMachines(): Load<List<com.asseta.core.model.owner.IdleMachineDto>> =
        repo.load(tenantId, "idle_machines", ListSerializer(com.asseta.core.model.owner.IdleMachineDto.serializer())) { idleMachines(pageSize = LIST_PAGE).items }

    // --- company closure (tenant.company.close) --------------------------------------------------------------------

    suspend fun companyClosure(): Load<com.asseta.core.model.owner.CompanyClosureStatusDto> =
        repo.load(tenantId, "company_closure", com.asseta.core.model.owner.CompanyClosureStatusDto.serializer()) { companyClosure() }

    suspend fun cancelCompanyClosure(reason: String): ActionResult<com.asseta.core.model.owner.CompanyClosureRequestDto> =
        repo.act { cancelCompanyClosure(com.asseta.core.model.owner.ClosureCancelIn(reason.trim())) }

    // --- go-live setup checklist -------------------------------------------------------------------------------------
    /**
     * Dashboard banner figures: seeded from `/me` when the company is entered, then replaced by every checklist this
     * session loads live or changes (so the banner follows the checklist without re-reading `/me`).
     */
    val setupProgress = kotlinx.coroutines.flow.MutableStateFlow<com.asseta.owner.ui.setup.SetupProgress?>(null)

    /** Seeds [setupProgress] from `/me` unless a checklist was already seen in this session. */
    fun seedSetupProgress(fromMe: com.asseta.owner.ui.setup.SetupProgress?) {
        if (setupProgress.value == null) setupProgress.value = fromMe
    }

    suspend fun setupChecklist(): Load<com.asseta.core.model.owner.SetupChecklistDto> =
        repo.load(tenantId, "setup_checklist", com.asseta.core.model.owner.SetupChecklistDto.serializer()) { setupChecklist() }.also {
            if (it is Load.Ok && !it.snapshot.stale) setupProgress.value = com.asseta.owner.ui.setup.SetupProgress.of(it.snapshot.data)
        }

    suspend fun markSetupStepNotNeeded(key: String, reason: String): ActionResult<com.asseta.core.model.owner.SetupChecklistDto> =
        setupWrite { markSetupStepNotNeeded(key, com.asseta.core.model.owner.SetupNotNeededIn(reason.trim())) }

    suspend fun undoSetupStepNotNeeded(key: String): ActionResult<com.asseta.core.model.owner.SetupChecklistDto> =
        setupWrite { undoSetupStepNotNeeded(key) }

    suspend fun confirmSetupControls(note: String?): ActionResult<com.asseta.core.model.owner.SetupChecklistDto> =
        setupWrite { confirmSetupControls(com.asseta.core.model.owner.SetupConfirmControlsIn(note?.trim()?.takeIf { n -> n.isNotEmpty() })) }

    private suspend fun setupWrite(
        block: suspend com.asseta.core.network.TenantApi.() -> com.asseta.core.model.owner.SetupChecklistDto,
    ): ActionResult<com.asseta.core.model.owner.SetupChecklistDto> = repo.act(block).also {
        if (it is ActionResult.Done) setupProgress.value = com.asseta.owner.ui.setup.SetupProgress.of(it.value)
    }

    /** The accountability dashboard summary (tiles the tenant hides come back null). */
    suspend fun accountabilitySummary(from: java.time.LocalDate? = null, to: java.time.LocalDate? = null): Load<AccountabilitySummaryDto> =
        repo.load(tenantId, "accountability_summary:$from:$to", AccountabilitySummaryDto.serializer()) { accountabilitySummary(from?.toString(), to?.toString()) }

    /** One employee's accountability over local days. */
    suspend fun employeeAccountability(staffId: String, from: java.time.LocalDate?, to: java.time.LocalDate?): Load<com.asseta.core.model.owner.EmployeeAccountabilityDto> =
        repo.load(tenantId, "employee:$staffId:$from:$to", com.asseta.core.model.owner.EmployeeAccountabilityDto.serializer()) {
            employeeAccountability(staffId, from?.toString(), to?.toString())
        }

    /** Find a record by reference (online only, never cached). */
    suspend fun lookup(reference: String) = repo.act { lookup(reference) }

    // --- owner mutations (online only, never queued) ---------------------------------------------------------------
    suspend fun acknowledgeAlert(id: String) = repo.act { alertAction(id, AlertActionIn(AlertActionIn.ACKNOWLEDGE)) }

    suspend fun resolveAlert(id: String, note: String) = repo.act { alertAction(id, AlertActionIn(AlertActionIn.RESOLVE, note.trim())) }

    suspend fun decideApproval(id: String, approve: Boolean, note: String?) =
        repo.act { decideApproval(id, ApprovalDecisionIn(approve, note?.trim()?.takeIf { it.isNotEmpty() })) }

    suspend fun decideMeterReset(id: String, approve: Boolean, note: String) = repo.act {
        decideMeterReset(id, MeterResetDecisionIn(if (approve) MeterResetDecisionIn.APPROVE else MeterResetDecisionIn.REJECT, note.trim()))
    }

    /**
     * Confirm ([verified]) or dispute a claimed cash handover (remittance); a dispute carries the reason. Confirming
     * records the [amountReceived] actually counted (null = the declared amount); a difference opens a cash variance.
     */
    suspend fun decideHandover(id: String, verified: Boolean, note: String?, amountReceived: String? = null) =
        repo.act {
            decideCashHandover(id, SettlementDecisionIn(verified, note?.trim()?.takeIf { it.isNotEmpty() }, amountReceived?.takeIf { verified }))
        }

    /** Confirm ([verified]) or reject a claimed customer payment; a rejection carries the reason. */
    suspend fun decidePayment(id: String, verified: Boolean, note: String?) =
        repo.act { decideCustomerPayment(id, SettlementDecisionIn(verified, note?.trim()?.takeIf { it.isNotEmpty() })) }

    /** Record the review of a meter exception: [outcome] EXPLAINED or CONFIRMED, with the review note. */
    suspend fun reviewException(id: String, outcome: String, note: String) =
        repo.act { reviewException(id, MeterResetDecisionIn(outcome, note.trim())) }

    /** Issue a cash float of [amount] [currency] to a supervisor. */
    suspend fun issueFloat(staffMemberId: String, amount: String, currency: String, note: String?) = repo.act {
        issueCashFloat(CashFloatIn(staffMemberId, amount.trim(), currency, note?.trim()?.takeIf { it.isNotEmpty() }))
    }

    // --- ADR-008: machine reports, credit sales, orders, customer hours, credit invoices -------------------------------
    /**
     * Expense requests waiting for a decision with their expenses ([details]: `tenant.expense.read`, best effort) so a
     * row can say what was bought and from whom.
     */
    suspend fun expenseApprovals(details: Boolean): Load<com.asseta.owner.ui.approvals.ExpenseQueue> =
        repo.load(tenantId, "expense_approvals", com.asseta.owner.ui.approvals.ExpenseQueue.serializer()) {
            val requests = approvals(status = "PENDING", pageSize = LIST_PAGE).items
            val expenses = if (details && requests.isNotEmpty()) {
                runCatching { expenses(status = "PENDING_APPROVAL", pageSize = LIST_PAGE).items }
                    .onFailure { if (it is kotlinx.coroutines.CancellationException) throw it }.getOrDefault(emptyList())
            } else emptyList()
            com.asseta.owner.ui.approvals.ExpenseQueue(requests, expenses.associateBy { it.id.toString() })
        }

    /** Machine reports waiting for a decision (the approval queue), oldest first. */
    suspend fun pendingMachineReports(): Load<List<MachineReportDto>> =
        repo.load(tenantId, "machine_reports:pending", ListSerializer(MachineReportDto.serializer())) {
            pages { p -> machineReports(queue = "PENDING", page = p, pageSize = BIG_PAGE) }.sortedBy { it.submittedAt }
        }

    /** Reports submitted on the local days [from]..[to] (any status; rejected ones are left out by the screens). */
    suspend fun machineReportsBetween(from: LocalDate, to: LocalDate): Load<List<MachineReportDto>> =
        repo.load(tenantId, "machine_reports:$from:$to", ListSerializer(MachineReportDto.serializer())) {
            pages { p -> machineReports(dateFrom = from.toString(), dateTo = to.toString(), page = p, pageSize = BIG_PAGE) }
        }

    /**
     * One report with its lines, findings and the tracker cross-check; [reading]: also its meter reading (OCR value,
     * GPS fix; `tenant.meter.read`, best effort: never fails the report).
     */
    suspend fun machineReport(id: String, reading: Boolean = false): Load<MachineReportDetail> =
        repo.load(tenantId, "machine_report:$id", MachineReportDetail.serializer()) {
            val report = machineReport(id)
            val capture = if (reading) {
                runCatching { meterCapture(report.captureId) }.onFailure { if (it is kotlinx.coroutines.CancellationException) throw it }.getOrNull()
            } else null
            MachineReportDetail(report, capture)
        }

    /** Where each machine stands for its next report (days since the last one, a report waiting). */
    suspend fun machineReportStatus(): Load<List<MachineReportStatusDto>> =
        repo.load(tenantId, "machine_report_status", ListSerializer(MachineReportStatusDto.serializer())) { machineReportStatus() }

    suspend fun approveMachineReport(id: String, note: String?) =
        repo.act { approveMachineReport(id, MachineReportDecisionIn(note?.trim()?.takeIf { it.isNotEmpty() })) }

    suspend fun rejectMachineReport(id: String, reason: String) = repo.act { rejectMachineReport(id, MachineReportRejectIn(reason.trim())) }

    /**
     * Orders with a credit part still waiting to be made usable (queue AWAITING_ACTIVATION with a credit amount), with
     * what is left of each customer's credit limit (best effort, bounded).
     */
    suspend fun creditSalesToApprove(): Load<List<CreditSale>> =
        repo.load(tenantId, "credit_sales:waiting", ListSerializer(CreditSale.serializer())) {
            val waiting = ownerOrders(queue = "AWAITING_ACTIVATION", pageSize = LIST_PAGE).items
                .filter { com.asseta.owner.ui.approvals.CreditSales.waiting(it) }
            val left = waiting.map { it.customerId }.distinct().take(MAX_EXPOSURE_LOOKUPS).mapNotNull { customer ->
                runCatching { customerCreditExposure(customer) }.onFailure { if (it is kotlinx.coroutines.CancellationException) throw it }
                    .getOrNull()?.let { customer to it.available }
            }.toMap()
            waiting.map { CreditSale(it, left[it.customerId]) }
        }

    /** Make [hours] of a credit sale usable ([key]: one per approval attempt, so a retry never activates twice). */
    suspend fun approveCredit(purchaseId: String, hours: String, reason: String, key: String) =
        repo.act { activateHoursOnCreditKeyed(purchaseId, CreditActivationIn(hours, reason.trim()), key) }

    /** Turn a credit sale down: ask for its order to be cancelled, with the reason. */
    suspend fun turnDownCredit(purchaseId: String, reason: String) =
        repo.act { requestOrderCancellation(purchaseId, com.asseta.core.model.owner.PurchaseCancellationIn(reason.trim())) }

    /** Orders recorded on the local days [from]..[to] (not cancelled): sold hours and money by method. */
    suspend fun ordersBetween(from: LocalDate, to: LocalDate): Load<List<com.asseta.core.model.owner.OwnerHoursPurchaseDto>> =
        repo.load(tenantId, "orders:$from:$to", ListSerializer(com.asseta.core.model.owner.OwnerHoursPurchaseDto.serializer())) {
            pages { p -> ownerOrders(dateFrom = from.toString(), dateTo = to.toString(), page = p, pageSize = BIG_PAGE) }
        }

    /** Hours bought / used / left and credit owed per customer. */
    suspend fun customerHoursSummary(): Load<List<CustomerHoursSummaryDto>> =
        repo.load(tenantId, "customer_hours_summary", ListSerializer(CustomerHoursSummaryDto.serializer())) { customerHours() }

    /** Credit invoices, newest first (all statuses, bounded). */
    suspend fun creditInvoices(): Load<List<CreditInvoiceDto>> =
        repo.load(tenantId, "credit_invoices", ListSerializer(CreditInvoiceDto.serializer())) {
            pages { p -> creditInvoices(page = p, pageSize = BIG_PAGE) }.sortedByDescending { it.issuedAt }
        }

    /** One customer's credit invoices (the Customers row). */
    suspend fun creditInvoicesOf(customerId: String): Load<List<CreditInvoiceDto>> =
        repo.load(tenantId, "credit_invoices:$customerId", ListSerializer(CreditInvoiceDto.serializer())) {
            creditInvoices(customerId = customerId, pageSize = BIG_PAGE).items.sortedByDescending { it.issuedAt }
        }

    /** Record a payment of a credit invoice ([key]: the form visit's Idempotency-Key, also its `client_id`). */
    suspend fun recordInvoicePayment(invoiceId: String, body: CreditInvoicePaymentIn, key: String) =
        repo.act { recordCreditInvoicePaymentKeyed(invoiceId, body, key) }

    /** Every page of a list (bounded): the screens sum a period, so a first page alone would undercount. */
    private suspend fun <T> pages(fetch: suspend (Int) -> PageDto<T>): List<T> {
        val all = mutableListOf<T>()
        var page = 1
        while (page <= MAX_PAGES) {
            val p = fetch(page)
            all += p.items
            if (p.items.size < p.pageSize || all.size >= p.total) break
            page++
        }
        return all
    }

    // --- online-only helpers (never cached) -------------------------------------------------------------------
    suspend fun attachmentUrl(attachmentId: String) = repo.act { attachmentUrl(attachmentId) }
    suspend fun receiptUrl(expenseId: String, attachmentId: String) = repo.act { receiptUrl(expenseId, attachmentId) }
    suspend fun remittanceEvidenceUrl(handoverId: String, attachmentId: String) = repo.act { remittanceEvidenceUrl(handoverId, attachmentId) }
    suspend fun paymentEvidenceUrl(paymentId: String, attachmentId: String) = repo.act { paymentEvidenceUrl(paymentId, attachmentId) }
    suspend fun expense(id: String) = repo.act { expense(id) }
    suspend fun notification(id: String) = repo.act { notification(id) }
    suspend fun markRead(ids: List<String>) = repo.act { markRead(com.asseta.core.model.owner.NotificationMarkReadIn(ids)) }
    suspend fun markAllRead() = repo.act { markAllRead() }
    suspend fun unreadCount() = repo.act { unreadCount() }

    // --- settings (online only) ---------------------------------------------------------------------------------
    suspend fun routing() = repo.act { notificationRouting() }
    suspend fun updateRouting(changes: List<com.asseta.core.model.owner.NotificationRoutingChangeIn>) =
        repo.act { updateNotificationRouting(com.asseta.core.model.owner.NotificationRoutingIn(changes)) }
    suspend fun pushDevices() = repo.act { pushDevices().items }
    suspend fun deactivatePushDevice(id: String) = repo.act { deactivatePushDevice(id) }

    private companion object {
        /** List page size (same as iOS). */
        const val LIST_PAGE = 100
        const val DETAIL_PAGE = 200

        /** Page size of the ADR-008 lists (the contract's maximum) and how many pages a period may span. */
        const val BIG_PAGE = 200
        const val MAX_PAGES = 10

        /** Distinct customers whose credit limit is looked up for the credit sales waiting. */
        const val MAX_EXPOSURE_LOOKUPS = 25

        /** Released payments looked up on one purchase. */
        const val MAX_PAYMENT_LOOKUPS = 25
    }
}
