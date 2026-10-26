package com.asseta.owner.data

import com.asseta.core.model.owner.AcknowledgementDto
import com.asseta.core.model.owner.ActivityDto
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
import com.asseta.core.model.owner.JobDto
import com.asseta.core.model.owner.JobIn
import com.asseta.core.model.owner.JobSummaryDto
import com.asseta.core.model.owner.JobTransitionIn
import com.asseta.core.model.owner.MachineDto
import com.asseta.core.model.owner.MachineMapDto
import com.asseta.core.model.owner.MeterCaptureDto
import com.asseta.core.model.owner.MeterResetDecisionIn
import com.asseta.core.model.owner.MeterResetDto
import com.asseta.core.model.owner.NotificationDto
import com.asseta.core.model.owner.PageDto
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
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import java.time.Instant
import java.time.temporal.ChronoUnit

/**
 * Job detail composed from the summary, its readings, the customer acknowledgements, the work log and (when the role
 * may read expenses) its expenses and fuel. The newer parts have defaults so snapshots saved before them still decode.
 */
@Serializable
data class JobDetail(
    val summary: JobSummaryDto,
    val captures: List<MeterCaptureDto>,
    val acknowledgements: List<AcknowledgementDto>,
    val activities: List<ActivityDto> = emptyList(),
    val expenses: List<ExpenseDto>? = null,
    val fuel: List<FuelEventDto>? = null,
)

/**
 * Cash handovers with the custodians' names ([names] staff member id -> name, from the supervisor cash summary; a
 * handover whose custodian is not there shows "A supervisor").
 */
@Serializable
data class HandoverList(val items: List<CashHandoverDto>, val names: Map<String, String> = emptyMap()) {
    fun name(h: CashHandoverDto): String? = h.staffMemberName ?: names[h.staffMemberId.toString()]
}

/** Open meter exceptions with their jobs' numbers ([jobNumbers] job id -> number, when the role may read jobs). */
@Serializable
data class ExceptionList(val items: List<ExceptionDto>, val jobNumbers: Map<String, String> = emptyMap()) {
    fun jobNumber(e: ExceptionDto): String? = e.jobId?.let { jobNumbers[it.toString()] }
}

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

    suspend fun machineJobs(id: String): Load<PageDto<JobDto>> =
        repo.load(tenantId, "machine_jobs:$id", PageDto.serializer(JobDto.serializer())) { jobs(machineId = id, status = "IN_PROGRESS", pageSize = 5) }

    /** Last 24 h track (bounded; a payload above the cache limit is simply not cached). */
    suspend fun machineTrack(id: String): Load<HistoryDto> {
        val to = Instant.ofEpochMilli(clock()).truncatedTo(ChronoUnit.SECONDS)
        val from = to.minus(24, ChronoUnit.HOURS)
        return repo.load(tenantId, "machine_track:$id", HistoryDto.serializer()) { machineHistory(id, from.toString(), to.toString()) }
    }

    /** Jobs list; only the unfiltered first page per status filter is cached. */
    suspend fun jobs(status: String?): Load<PageDto<JobDto>> =
        repo.load(tenantId, "jobs:${status ?: "ALL"}", PageDto.serializer(JobDto.serializer())) { jobs(status = status, pageSize = LIST_PAGE) }

    /** [spend]: also fetch the job's expenses and fuel (`tenant.expense.read`); otherwise they stay null (hidden). */
    suspend fun job(id: String, spend: Boolean = false): Load<JobDetail> = repo.load(tenantId, "job:$id", JobDetail.serializer()) {
        JobDetail(
            jobSummary(id), jobCaptures(id), jobAcknowledgements(id), jobActivities(id),
            expenses = if (spend) expenses(jobId = id, pageSize = LIST_PAGE).items else null,
            fuel = if (spend) fuelEvents(jobId = id, pageSize = LIST_PAGE).items else null,
        )
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

    /** Open exceptions for the Approvals section; [jobNumbers]: also look up their jobs' numbers (`tenant.job.read`). */
    suspend fun openExceptions(jobNumbers: Boolean): Load<ExceptionList> =
        repo.load(tenantId, "exceptions_open", ExceptionList.serializer()) {
            val items = exceptions(status = "OPEN", pageSize = LIST_PAGE).items
            val numbers = if (!jobNumbers) {
                emptyMap()
            } else {
                items.mapNotNull { it.jobId?.toString() }.distinct().take(MAX_JOB_LOOKUPS).mapNotNull { id ->
                    runCatching { id to jobSummary(id).job.jobNumber }.getOrNull()
                }.toMap()
            }
            ExceptionList(items, numbers)
        }

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
                DecisionKind.RETENTION -> cashRetentions(status).items.map { DecisionMapper.retention(it, zone) }
                DecisionKind.ADJUSTMENT -> custodyAdjustments(status).items.map { DecisionMapper.adjustment(it, zone) }
                // Waiting for someone: to explain (OPEN) and explanations waiting for a decision.
                DecisionKind.REVENUE_DIFFERENCE -> (revenueDifferences("OPEN").items + revenueDifferences(status).items)
                    .map { DecisionMapper.revenueDifference(it, zone) }
                DecisionKind.NON_REVENUE -> nonRevenueApprovals(status).items.map { DecisionMapper.nonRevenue(it, zone) }
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
                    DecisionKind.WRITE_OFF -> DecisionMapper.writeOff(cashVariance(id))
                    DecisionKind.RETENTION -> DecisionMapper.retention(cashRetention(id), zone)
                    DecisionKind.ADJUSTMENT -> DecisionMapper.adjustment(custodyAdjustment(id), zone)
                    DecisionKind.REVENUE_DIFFERENCE -> DecisionMapper.revenueDifference(revenueDifference(id), zone)
                    DecisionKind.NON_REVENUE -> DecisionMapper.nonRevenue(nonRevenueApproval(id), zone)
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
                DecisionKind.RETENTION -> decideCashRetention(id, decision)
                DecisionKind.ADJUSTMENT -> decideCustodyAdjustment(id, decision)
                DecisionKind.REVENUE_DIFFERENCE -> decideRevenueDifference(id, RevenueDecisionIn(meter.decision, meter.note))
                DecisionKind.NON_REVENUE -> decideNonRevenue(id, NonRevenueDecisionIn(meter.decision, meter.note))
            }
            Unit
        }
    }

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

    // --- customer hours, read-only (DEC-031 P4) --------------------------------------------------------------------
    /** Open purchases with hours left or in use by running jobs, newest first. */
    suspend fun hoursPurchases(): Load<List<com.asseta.core.model.owner.OwnerHoursPurchaseDto>> =
        repo.load(tenantId, "hours_purchases", ListSerializer(com.asseta.core.model.owner.OwnerHoursPurchaseDto.serializer())) {
            com.asseta.owner.ui.accountability.HoursPresentation.open(ownerHoursPurchases(pageSize = LIST_PAGE).items)
        }

    suspend fun hoursPurchase(id: String): Load<com.asseta.core.model.owner.OwnerHoursPurchaseDto> =
        repo.load(tenantId, "hours_purchase:$id", com.asseta.core.model.owner.OwnerHoursPurchaseDto.serializer()) { hoursPurchase(id) }

    /** One customer's hours statement for the local days [from]..[to] (cached per customer and period). */
    suspend fun hoursStatement(customerId: String, from: java.time.LocalDate, to: java.time.LocalDate): Load<com.asseta.core.model.owner.HoursStatementDto> =
        repo.load(tenantId, "hours_statement:$customerId:$from:$to", com.asseta.core.model.owner.HoursStatementDto.serializer()) {
            customerHoursStatement(customerId, from.toString(), to.toString())
        }

    /** The same statement as PDF bytes (online only, never cached). */
    suspend fun hoursStatementPdf(customerId: String, from: java.time.LocalDate, to: java.time.LocalDate): ActionResult<ByteArray> =
        repo.act { customerHoursStatementPdf(customerId, from.toString(), to.toString()).use { it.bytes() } }

    /** The accountability dashboard summary (tiles the tenant hides come back null). */
    suspend fun accountabilitySummary(): Load<AccountabilitySummaryDto> =
        repo.load(tenantId, "accountability_summary", AccountabilitySummaryDto.serializer()) { accountabilitySummary() }

    // --- owner mutations (online only, never queued) ---------------------------------------------------------------
    suspend fun acknowledgeAlert(id: String) = repo.act { alertAction(id, AlertActionIn(AlertActionIn.ACKNOWLEDGE)) }

    suspend fun resolveAlert(id: String, note: String) = repo.act { alertAction(id, AlertActionIn(AlertActionIn.RESOLVE, note.trim())) }

    suspend fun decideApproval(id: String, approve: Boolean, note: String?) =
        repo.act { decideApproval(id, ApprovalDecisionIn(approve, note?.trim()?.takeIf { it.isNotEmpty() })) }

    suspend fun decideMeterReset(id: String, approve: Boolean, note: String) = repo.act {
        decideMeterReset(id, MeterResetDecisionIn(if (approve) MeterResetDecisionIn.APPROVE else MeterResetDecisionIn.REJECT, note.trim()))
    }

    /** Approve a job waiting for approval; [hourlyRate] prices a field request without a rate card (PENDING_PRICE). */
    suspend fun approveJob(id: String, hourlyRate: String?) =
        repo.act { transitionJob(id, JobTransitionIn(JobTransitionIn.APPROVE, hourlyRate = hourlyRate?.trim()?.takeIf { it.isNotEmpty() })) }

    /** Decline a job waiting for approval (CANCEL with the reason the supervisor is told). */
    suspend fun declineJob(id: String, reason: String) = repo.act { transitionJob(id, JobTransitionIn(JobTransitionIn.CANCEL, reason = reason.trim())) }

    /**
     * Confirm ([verified]) or dispute a claimed cash handover (remittance); a dispute carries the reason. Confirming
     * records the [amountReceived] actually counted (null = the declared amount); a difference opens a cash variance.
     */
    suspend fun decideHandover(id: String, verified: Boolean, note: String?, amountReceived: String? = null) =
        repo.act {
            decideCashHandover(id, SettlementDecisionIn(verified, note?.trim()?.takeIf { it.isNotEmpty() }, amountReceived?.takeIf { verified }))
        }

    /** Record the review of a meter exception: [outcome] EXPLAINED or CONFIRMED, with the review note. */
    suspend fun reviewException(id: String, outcome: String, note: String) =
        repo.act { reviewException(id, MeterResetDecisionIn(outcome, note.trim())) }

    /** Issue a cash float of [amount] [currency] to a supervisor. */
    suspend fun issueFloat(staffMemberId: String, amount: String, currency: String, note: String?) = repo.act {
        issueCashFloat(CashFloatIn(staffMemberId, amount.trim(), currency, note?.trim()?.takeIf { it.isNotEmpty() }))
    }

    /** Create a DRAFT job; [key] is the form visit's Idempotency-Key so a retry never creates a second job. */
    suspend fun createJob(body: JobIn, key: String) = repo.act { createJob(body, key) }

    /** SUBMIT a DRAFT job for approval ([key]: stable per form visit). */
    suspend fun submitJob(id: String, key: String) = repo.act { transitionJob(id, JobTransitionIn(JobTransitionIn.SUBMIT), key) }

    /** APPROVE a job just created at its own price ([key]: stable per form visit); the supervisor is notified. */
    suspend fun approveNewJob(id: String, key: String) = repo.act { transitionJob(id, JobTransitionIn(JobTransitionIn.APPROVE), key) }

    // --- "New job" lookups (online only, never cached; same endpoints as the web form) --------------------------
    /** Contracts matching [q] (CLOSED ones are hidden by the server, as in the web picker). */
    suspend fun searchContracts(q: String) = repo.act { contracts(q = q.trim().ifEmpty { null }).items }
    suspend fun searchMachines(q: String) = repo.act { machines(q = q.trim().ifEmpty { null }).items }
    suspend fun searchSupervisors(q: String) = repo.act { staff(q = q.trim().ifEmpty { null }, kind = "SUPERVISOR").items }
    suspend fun searchJobSites(q: String) = repo.act { jobSites(q = q.trim().ifEmpty { null }) }

    // --- online-only helpers (never cached) -------------------------------------------------------------------
    suspend fun attachmentUrl(attachmentId: String) = repo.act { attachmentUrl(attachmentId) }
    suspend fun receiptUrl(expenseId: String, attachmentId: String) = repo.act { receiptUrl(expenseId, attachmentId) }
    suspend fun remittanceEvidenceUrl(handoverId: String, attachmentId: String) = repo.act { remittanceEvidenceUrl(handoverId, attachmentId) }
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

        /** Distinct jobs whose numbers are looked up for the open exceptions (bounded network work). */
        const val MAX_JOB_LOOKUPS = 25
    }
}
