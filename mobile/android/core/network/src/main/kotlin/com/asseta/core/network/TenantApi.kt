package com.asseta.core.network

import com.asseta.core.model.owner.AcknowledgementDto
import com.asseta.core.model.owner.ActivityDto
import com.asseta.core.model.owner.AlertActionIn
import com.asseta.core.model.owner.AlertDto
import com.asseta.core.model.owner.AnomalyCaseDetailDto
import com.asseta.core.model.owner.AnomalyCaseDto
import com.asseta.core.model.owner.ApprovalDecisionIn
import com.asseta.core.model.owner.ApprovalRequestDto
import com.asseta.core.model.owner.CashCustodyEntryDto
import com.asseta.core.model.owner.CashFloatIn
import com.asseta.core.model.owner.CashHandoverDto
import com.asseta.core.model.owner.CashSupervisorSummaryDto
import com.asseta.core.model.owner.ExceptionDto
import com.asseta.core.model.owner.ExpenseDto
import com.asseta.core.model.owner.FuelEventDto
import com.asseta.core.model.owner.HistoryDto
import com.asseta.core.model.owner.JobDto
import com.asseta.core.model.owner.JobSummaryDto
import com.asseta.core.model.owner.MachineDto
import com.asseta.core.model.owner.MachineMapDto
import com.asseta.core.model.owner.MeterCaptureDto
import com.asseta.core.model.owner.MeterResetDecisionIn
import com.asseta.core.model.owner.MeterResetDto
import com.asseta.core.model.owner.NotificationDto
import com.asseta.core.model.owner.NotificationMarkReadIn
import com.asseta.core.model.owner.NotificationMarkReadResultDto
import com.asseta.core.model.owner.NotificationRoutingDto
import com.asseta.core.model.owner.NotificationRoutingIn
import com.asseta.core.model.owner.NotificationUnreadCountDto
import com.asseta.core.model.owner.PageDto
import com.asseta.core.model.owner.PhotoUrlDto
import com.asseta.core.model.owner.PushDeviceDto
import com.asseta.core.model.owner.PushDeviceIn
import com.asseta.core.model.owner.SettlementDecisionIn
import com.asseta.core.model.owner.TenantOverviewDto
import com.asseta.core.model.owner.JobTransitionIn
import com.asseta.core.model.sync.CashReconciliationDto
import com.asseta.core.model.sync.FieldContractDto
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Online tenant endpoints used by the Owner app (operationIds from contracts/openapi.json). `X-Tenant-ID` comes from
 * the selected tenant ([TenantInterceptor]); every mutation gets an `Idempotency-Key`. The server authorizes every
 * call; the app only hides what it cannot do.
 */
interface TenantApi {
    /** getTenantOverview */
    @GET("api/v1/tenant/overview")
    suspend fun overview(): TenantOverviewDto

    /** getFleetMap */
    @GET("api/v1/tenant/fleet/map")
    suspend fun fleetMap(@Query("q") q: String? = null, @Query("connectivity") connectivity: String? = null): List<MachineMapDto>

    /** getMachineStatus */
    @GET("api/v1/tenant/fleet/machines/{id}")
    suspend fun machineStatus(@Path("id") machineId: String): MachineMapDto

    /** getMachineHistory (ISO-8601 instants; range at most 31 days). */
    @GET("api/v1/tenant/fleet/machines/{id}/history")
    suspend fun machineHistory(@Path("id") machineId: String, @Query("from") from: String, @Query("to") to: String): HistoryDto

    /** getMachine */
    @GET("api/v1/tenant/machines/{id}")
    suspend fun machine(@Path("id") machineId: String): MachineDto

    /** listJobs */
    @GET("api/v1/tenant/jobs")
    suspend fun jobs(
        @Query("status") status: String? = null,
        @Query("machine_id") machineId: String? = null,
        @Query("q") q: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 50,
        @Query("sort") sort: String? = null,
    ): PageDto<JobDto>

    /** transitionJob: APPROVE (with hourly_rate for a PENDING_PRICE job) or CANCEL with a reason (needs tenant.job.approve). */
    @POST("api/v1/tenant/jobs/{id}/transitions")
    suspend fun transitionJob(@Path("id") jobId: String, @Body body: JobTransitionIn): JobDto

    /** getJobSummary */
    @GET("api/v1/tenant/jobs/{id}")
    suspend fun jobSummary(@Path("id") jobId: String): JobSummaryDto

    /** listJobCaptures */
    @GET("api/v1/tenant/jobs/{id}/meter-captures")
    suspend fun jobCaptures(@Path("id") jobId: String): List<MeterCaptureDto>

    /** listJobAcknowledgements */
    @GET("api/v1/tenant/jobs/{id}/acknowledgements")
    suspend fun jobAcknowledgements(@Path("id") jobId: String): List<AcknowledgementDto>

    /** listJobActivities (work log, oldest first) */
    @GET("api/v1/tenant/jobs/{id}/activities")
    suspend fun jobActivities(@Path("id") jobId: String): List<ActivityDto>

    /** listMeterCaptures (latest captured first) */
    @GET("api/v1/tenant/meter-captures")
    suspend fun meterCaptures(
        @Query("machine_id") machineId: String? = null,
        @Query("page_size") pageSize: Int = 5,
    ): PageDto<MeterCaptureDto>

    /** getAttachmentUrl: presigned, short-lived; fetched on demand only. */
    @GET("api/v1/tenant/attachments/{id}/url")
    suspend fun attachmentUrl(@Path("id") attachmentId: String): PhotoUrlDto

    /** getExpenseReceiptUrl */
    @GET("api/v1/tenant/expenses/{expenseId}/receipts/{attachmentId}/url")
    suspend fun receiptUrl(@Path("expenseId") expenseId: String, @Path("attachmentId") attachmentId: String): PhotoUrlDto

    /** listTrackingAlerts */
    @GET("api/v1/tenant/alerts")
    suspend fun alerts(
        @Query("status") status: String? = null,
        @Query("machine_id") machineId: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 50,
    ): PageDto<AlertDto>

    /** actOnTrackingAlert (needs tenant.fleet.alert_manage) */
    @POST("api/v1/tenant/alerts/{id}/action")
    suspend fun alertAction(@Path("id") alertId: String, @Body body: AlertActionIn): AlertDto

    /** listApprovalRequests */
    @GET("api/v1/tenant/approvals")
    suspend fun approvals(@Query("status") status: String? = null, @Query("page") page: Int = 1, @Query("page_size") pageSize: Int = 50): PageDto<ApprovalRequestDto>

    /** decideApprovalRequest (needs tenant.approval.expense; segregation of duties enforced by the server) */
    @POST("api/v1/tenant/approvals/{id}/decision")
    suspend fun decideApproval(@Path("id") approvalId: String, @Body body: ApprovalDecisionIn): ApprovalRequestDto

    /** getExpense */
    @GET("api/v1/tenant/expenses/{id}")
    suspend fun expense(@Path("id") expenseId: String): ExpenseDto

    /** listExpenses (newest first) */
    @GET("api/v1/tenant/expenses")
    suspend fun expenses(
        @Query("job_id") jobId: String? = null,
        @Query("status") status: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 50,
    ): PageDto<ExpenseDto>

    /** listFuelEvents (latest first) */
    @GET("api/v1/tenant/fuel-events")
    suspend fun fuelEvents(
        @Query("job_id") jobId: String? = null,
        @Query("event_type") eventType: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 50,
    ): PageDto<FuelEventDto>

    /** listJobExceptions (newest first) */
    @GET("api/v1/tenant/exceptions")
    suspend fun exceptions(
        @Query("status") status: String? = null,
        @Query("job_id") jobId: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 50,
    ): PageDto<ExceptionDto>

    /** reviewJobException (needs tenant.meter.review): EXPLAINED or CONFIRMED with a 5..2000 character note. */
    @POST("api/v1/tenant/exceptions/{id}/review")
    suspend fun reviewException(@Path("id") exceptionId: String, @Body body: MeterResetDecisionIn): ExceptionDto

    /** listMeterResets (plain list, newest first) */
    @GET("api/v1/tenant/meter-resets")
    suspend fun meterResets(@Query("status") status: String? = null): List<MeterResetDto>

    /** decideMeterReset (needs tenant.meter.approve; the requester cannot decide their own reset) */
    @POST("api/v1/tenant/meter-resets/{id}/decision")
    suspend fun decideMeterReset(@Path("id") resetId: String, @Body body: MeterResetDecisionIn): MeterResetDto

    /** listCashSupervisorSummaries: every custodian x currency over tenant-local days [from, to] (YYYY-MM-DD). */
    @GET("api/v1/tenant/cash/supervisor-summary")
    suspend fun cashSupervisorSummary(@Query("from") from: String, @Query("to") to: String): List<CashSupervisorSummaryDto>

    /** listCashHandovers (newest first); [status] CLAIMED, VERIFIED or REJECTED. */
    @GET("api/v1/tenant/cash/handovers")
    suspend fun cashHandovers(
        @Query("status") status: String? = null,
        @Query("staff_member_id") staffMemberId: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 50,
    ): PageDto<CashHandoverDto>

    /** decideCashHandover (needs tenant.finance.verify; the recorder cannot decide it). */
    @POST("api/v1/tenant/cash/handovers/{id}/decision")
    suspend fun decideCashHandover(@Path("id") handoverId: String, @Body body: SettlementDecisionIn): CashHandoverDto

    /** issueCashFloat (needs tenant.finance.cash): a float into a supervisor's custody. */
    @POST("api/v1/tenant/cash/floats")
    suspend fun issueCashFloat(@Body body: CashFloatIn): CashCustodyEntryDto

    /** listAnomalyCases */
    @GET("api/v1/tenant/cases")
    suspend fun cases(@Query("status") status: String? = null, @Query("page") page: Int = 1, @Query("page_size") pageSize: Int = 50): PageDto<AnomalyCaseDto>

    /** getAnomalyCase */
    @GET("api/v1/tenant/cases/{id}")
    suspend fun case(@Path("id") caseId: String): AnomalyCaseDetailDto

    /** listMyNotifications */
    @GET("api/v1/tenant/notifications")
    suspend fun notifications(@Query("unread_only") unreadOnly: Boolean = false, @Query("page") page: Int = 1, @Query("page_size") pageSize: Int = 50): PageDto<NotificationDto>

    /** getMyNotification */
    @GET("api/v1/tenant/notifications/{id}")
    suspend fun notification(@Path("id") notificationId: String): NotificationDto

    /** getMyUnreadCount */
    @GET("api/v1/tenant/notifications/unread-count")
    suspend fun unreadCount(): NotificationUnreadCountDto

    /** markMyNotificationsRead */
    @POST("api/v1/tenant/notifications/read")
    suspend fun markRead(@Body body: NotificationMarkReadIn): NotificationMarkReadResultDto

    /** markAllMyNotificationsRead */
    @POST("api/v1/tenant/notifications/read-all")
    suspend fun markAllRead(): NotificationMarkReadResultDto

    /** getMyNotificationRouting */
    @GET("api/v1/tenant/notification-routing")
    suspend fun notificationRouting(): List<NotificationRoutingDto>

    /** updateMyNotificationRouting */
    @PUT("api/v1/tenant/notification-routing")
    suspend fun updateNotificationRouting(@Body body: NotificationRoutingIn): List<NotificationRoutingDto>

    /** listMyPushDevices */
    @GET("api/v1/me/push-devices")
    suspend fun pushDevices(@Query("include_inactive") includeInactive: Boolean = false): PageDto<PushDeviceDto>

    /** registerPushDevice (binds the device to the selected tenant via X-Tenant-ID) */
    @POST("api/v1/me/push-devices")
    suspend fun registerPushDevice(@Body body: PushDeviceIn): PushDeviceDto

    /** deactivatePushDevice */
    @DELETE("api/v1/me/push-devices/{id}")
    suspend fun deactivatePushDevice(@Path("id") deviceId: String): PushDeviceDto

    /** listFieldContracts: active contracts a supervisor can request a job under (Supervisor app). */
    @GET("api/v1/tenant/field/contracts")
    suspend fun fieldContracts(): List<FieldContractDto>

    /** listMyFieldMachines: machines the supervisor works on (Supervisor app). */
    @GET("api/v1/tenant/field/machines")
    suspend fun fieldMachines(): List<com.asseta.core.model.sync.MachineDto>

    /** getMyCashReconciliation: the signed-in supervisor's day-by-day custody (Supervisor app, online only). */
    @GET("api/v1/tenant/cash/custody/me/reconciliation")
    suspend fun myCashReconciliation(@Query("date") date: String? = null, @Query("currency") currency: String? = null): List<CashReconciliationDto>
}
