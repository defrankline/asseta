package com.asseta.owner.data

import com.asseta.core.model.owner.AcknowledgementDto
import com.asseta.core.model.owner.ActivityDto
import com.asseta.core.model.owner.AlertActionIn
import com.asseta.core.model.owner.AlertDto
import com.asseta.core.model.owner.AnomalyCaseDetailDto
import com.asseta.core.model.owner.AnomalyCaseDto
import com.asseta.core.model.owner.ApprovalDecisionIn
import com.asseta.core.model.owner.ApprovalRequestDto
import com.asseta.core.model.owner.CashSupervisorSummaryDto
import com.asseta.core.model.owner.ExceptionDto
import com.asseta.core.model.owner.ExpenseDto
import com.asseta.core.model.owner.FuelEventDto
import com.asseta.core.model.owner.HistoryDto
import com.asseta.core.model.owner.JobDto
import com.asseta.core.model.owner.JobSummaryDto
import com.asseta.core.model.owner.JobTransitionIn
import com.asseta.core.model.owner.MachineDto
import com.asseta.core.model.owner.MachineMapDto
import com.asseta.core.model.owner.MeterCaptureDto
import com.asseta.core.model.owner.MeterResetDecisionIn
import com.asseta.core.model.owner.MeterResetDto
import com.asseta.core.model.owner.NotificationDto
import com.asseta.core.model.owner.PageDto
import com.asseta.core.model.owner.TenantOverviewDto
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

    // --- the only owner mutations (online only) ---------------------------------------------------------------
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

    // --- online-only helpers (never cached) -------------------------------------------------------------------
    suspend fun attachmentUrl(attachmentId: String) = repo.act { attachmentUrl(attachmentId) }
    suspend fun receiptUrl(expenseId: String, attachmentId: String) = repo.act { receiptUrl(expenseId, attachmentId) }
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
    }
}
