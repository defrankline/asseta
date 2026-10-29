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
import com.asseta.core.model.owner.RemittanceOverdueDto
import com.asseta.core.model.owner.CashSupervisorSummaryDto
import com.asseta.core.model.owner.ContractDto
import com.asseta.core.model.owner.ExceptionDto
import com.asseta.core.model.owner.ExpenseDto
import com.asseta.core.model.owner.FuelEventDto
import com.asseta.core.model.owner.HistoryDto
import com.asseta.core.model.owner.JobDto
import com.asseta.core.model.owner.JobIn
import com.asseta.core.model.owner.JobSiteDto
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
import com.asseta.core.model.owner.StaffDto
import com.asseta.core.model.owner.TenantOverviewDto
import com.asseta.core.model.owner.JobTransitionIn
import com.asseta.core.model.owner.AccountabilitySummaryDto
import com.asseta.core.model.owner.BaselineDto
import com.asseta.core.model.owner.CashRetentionDto
import com.asseta.core.model.owner.CashVarianceDto
import com.asseta.core.model.owner.ClassificationDto
import com.asseta.core.model.owner.CorrectionDto
import com.asseta.core.model.owner.CreditArrangementDto
import com.asseta.core.model.owner.CustodyAdjustmentDto
import com.asseta.core.model.owner.DecisionIn
import com.asseta.core.model.owner.DiscountDto
import com.asseta.core.model.owner.HoursCancellationDto
import com.asseta.core.model.owner.HoursTransferDto
import com.asseta.core.model.owner.MeterDecisionIn
import com.asseta.core.model.sync.CashReasonDto
import com.asseta.core.model.sync.CashReconciliationDto
import com.asseta.core.model.sync.CashRetentionIn
import com.asseta.core.model.sync.CashTransferDto
import com.asseta.core.model.sync.CustodianDto
import com.asseta.core.model.sync.EffectivePolicyDto
import com.asseta.core.model.sync.FieldContractDto
import com.asseta.core.model.sync.FieldHoursPurchaseDto
import com.asseta.core.model.sync.FloatEntryDto
import com.asseta.core.model.sync.ReasonCodeDto
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Header
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

    /**
     * transitionJob: SUBMIT (tenant.job.write), APPROVE (with hourly_rate for a PENDING_PRICE job) or CANCEL with a
     * reason (tenant.job.approve). [idempotencyKey]: a stable key so a retried step is not applied twice (else random).
     */
    @POST("api/v1/tenant/jobs/{id}/transitions")
    suspend fun transitionJob(
        @Path("id") jobId: String,
        @Body body: JobTransitionIn,
        @Header(AssetaHeaders.IDEMPOTENCY_KEY) idempotencyKey: String? = null,
    ): JobDto

    /** createJob (needs tenant.job.write): a DRAFT job; [idempotencyKey] is kept for the whole form visit. */
    @POST("api/v1/tenant/jobs")
    suspend fun createJob(@Body body: JobIn, @Header(AssetaHeaders.IDEMPOTENCY_KEY) idempotencyKey: String): JobDto

    /** listContracts: CLOSED contracts are hidden by default; `q` searches number / reference. */
    @GET("api/v1/tenant/contracts")
    suspend fun contracts(
        @Query("q") q: String? = null,
        @Query("status") status: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20,
    ): PageDto<ContractDto>

    /** listMachines: `q` searches asset code / name. */
    @GET("api/v1/tenant/machines")
    suspend fun machines(@Query("q") q: String? = null, @Query("page") page: Int = 1, @Query("page_size") pageSize: Int = 20): PageDto<MachineDto>

    /** listStaff: `kind=SUPERVISOR` for the job's supervisor. */
    @GET("api/v1/tenant/staff")
    suspend fun staff(
        @Query("q") q: String? = null,
        @Query("kind") kind: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20,
    ): PageDto<StaffDto>

    /** listJobSites (plain list): `q` searches code and name (needs tenant.geofence.read). */
    @GET("api/v1/tenant/job-sites")
    suspend fun jobSites(@Query("q") q: String? = null): List<JobSiteDto>

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

    /** getRemittanceEvidenceUrl: a deposit slip / payment confirmation photo of a remittance (on demand only). */
    @GET("api/v1/tenant/cash/handovers/{handoverId}/evidence/{attachmentId}/url")
    suspend fun remittanceEvidenceUrl(@Path("handoverId") handoverId: String, @Path("attachmentId") attachmentId: String): PhotoUrlDto

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

    // --- accountability: field reads (Supervisor app; cached encrypted for offline use) ----------------------------

    /** getEffectivePolicy: a field user may read CASH_CUSTODY / CUSTOMER_HOURS with the matching capture permission. */
    @GET("api/v1/tenant/policies/{type}/effective")
    suspend fun effectivePolicy(@Path("type") policyType: String): EffectivePolicyDto

    /** listCashCustodians: staff who can hold company cash (a login is not required). */
    @GET("api/v1/tenant/cash/custodians")
    suspend fun cashCustodians(@Query("q") q: String? = null, @Query("page") page: Int = 1, @Query("page_size") pageSize: Int = 100): PageDto<CustodianDto>

    /** listCashTransfers: [staffMemberId] as sender or receiver; [status] PENDING_ACKNOWLEDGEMENT, ACKNOWLEDGED or DISPUTED. */
    @GET("api/v1/tenant/cash/transfers")
    suspend fun cashTransfers(
        @Query("status") status: String? = null,
        @Query("staff_member_id") staffMemberId: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 100,
    ): PageDto<CashTransferDto>

    /** listCashFloats: floats with their acknowledgement state. */
    @GET("api/v1/tenant/cash/floats")
    suspend fun cashFloats(
        @Query("staff_member_id") staffMemberId: String? = null,
        @Query("awaiting_acknowledgement") awaitingAcknowledgement: Boolean? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 100,
    ): PageDto<FloatEntryDto>

    /** listHoursPurchases (open purchases; `cancelled=false`). */
    @GET("api/v1/tenant/hours-purchases")
    suspend fun hoursPurchases(
        @Query("machine_id") machineId: String? = null,
        @Query("cancelled") cancelled: Boolean? = false,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 100,
    ): PageDto<FieldHoursPurchaseDto>

    /** listHoursReasonCodes: the tenant's reasons of [kind] (DISCOUNT, CREDIT, TRANSFER, CANCELLATION). */
    @GET("api/v1/tenant/hours-reason-codes")
    suspend fun hoursReasonCodes(@Query("kind") kind: String? = null, @Query("page_size") pageSize: Int = 100): PageDto<ReasonCodeDto>

    /** listCashReasons: the tenant's cash reasons of [kind] (VARIANCE, WRITE_OFF, RETENTION, ADJUSTMENT). */
    @GET("api/v1/tenant/cash/reasons")
    suspend fun cashReasons(@Query("kind") kind: String? = null, @Query("page_size") pageSize: Int = 100): PageDto<CashReasonDto>

    /** requestCashRetention (tenant.collection.record): ask to keep some cash instead of remitting it (online only). */
    @POST("api/v1/tenant/cash/retentions")
    suspend fun requestCashRetention(@Body body: CashRetentionIn, @Header(AssetaHeaders.IDEMPOTENCY_KEY) idempotencyKey: String): CashRetentionDto

    // --- accountability: owner approvals and dashboard --------------------------------------------------------

    /** getAccountabilitySummary (tenant.accountability.read). */
    @GET("api/v1/tenant/accountability/summary")
    suspend fun accountabilitySummary(): AccountabilitySummaryDto

    @GET("api/v1/tenant/customer-discounts")
    suspend fun customerDiscounts(@Query("status") status: String? = null, @Query("page_size") pageSize: Int = 100): PageDto<DiscountDto>

    @POST("api/v1/tenant/customer-discounts/{id}/decision")
    suspend fun decideCustomerDiscount(@Path("id") id: String, @Body body: DecisionIn): DiscountDto

    @GET("api/v1/tenant/credit-arrangements")
    suspend fun creditArrangements(@Query("status") status: String? = null, @Query("page_size") pageSize: Int = 100): PageDto<CreditArrangementDto>

    @POST("api/v1/tenant/credit-arrangements/{id}/decision")
    suspend fun decideCreditArrangement(@Path("id") id: String, @Body body: DecisionIn): CreditArrangementDto

    @GET("api/v1/tenant/hours-transfers")
    suspend fun hoursTransfers(@Query("status") status: String? = null, @Query("page_size") pageSize: Int = 100): PageDto<HoursTransferDto>

    @POST("api/v1/tenant/hours-transfers/{id}/decision")
    suspend fun decideHoursTransfer(@Path("id") id: String, @Body body: DecisionIn): HoursTransferDto

    @GET("api/v1/tenant/hours-cancellations")
    suspend fun hoursCancellations(@Query("status") status: String? = null, @Query("page_size") pageSize: Int = 100): PageDto<HoursCancellationDto>

    @POST("api/v1/tenant/hours-cancellations/{id}/decision")
    suspend fun decideHoursCancellation(@Path("id") id: String, @Body body: DecisionIn): HoursCancellationDto

    @GET("api/v1/tenant/meter-baselines")
    suspend fun meterBaselines(@Query("status") status: String? = null, @Query("page_size") pageSize: Int = 100): PageDto<BaselineDto>

    @POST("api/v1/tenant/meter-baselines/{id}/decision")
    suspend fun decideMeterBaseline(@Path("id") id: String, @Body body: MeterDecisionIn): BaselineDto

    @GET("api/v1/tenant/engine-hours/classifications")
    suspend fun engineHourClassifications(@Query("status") status: String? = null, @Query("page_size") pageSize: Int = 100): PageDto<ClassificationDto>

    @POST("api/v1/tenant/engine-hours/classifications/{id}/decision")
    suspend fun decideEngineHourClassification(@Path("id") id: String, @Body body: MeterDecisionIn): ClassificationDto

    @GET("api/v1/tenant/meter-corrections")
    suspend fun meterCorrections(@Query("status") status: String? = null, @Query("page_size") pageSize: Int = 100): PageDto<CorrectionDto>

    @POST("api/v1/tenant/meter-corrections/{id}/decision")
    suspend fun decideMeterCorrection(@Path("id") id: String, @Body body: MeterDecisionIn): CorrectionDto

    @GET("api/v1/tenant/cash/variances")
    suspend fun cashVariances(@Query("status") status: String? = null, @Query("page_size") pageSize: Int = 100): PageDto<CashVarianceDto>

    /** decideCashVarianceWriteOff (tenant.finance.writeoff; not the proposer). */
    @POST("api/v1/tenant/cash/variances/{id}/write-off-decision")
    suspend fun decideCashWriteOff(@Path("id") id: String, @Body body: DecisionIn): CashVarianceDto

    @GET("api/v1/tenant/cash/retentions")
    suspend fun cashRetentions(@Query("status") status: String? = null, @Query("page_size") pageSize: Int = 100): PageDto<CashRetentionDto>

    @POST("api/v1/tenant/cash/retentions/{id}/decision")
    suspend fun decideCashRetention(@Path("id") id: String, @Body body: DecisionIn): CashRetentionDto

    @GET("api/v1/tenant/cash/adjustments")
    suspend fun custodyAdjustments(@Query("status") status: String? = null, @Query("page_size") pageSize: Int = 100): PageDto<CustodyAdjustmentDto>

    @POST("api/v1/tenant/cash/adjustments/{id}/decision")
    suspend fun decideCustodyAdjustment(@Path("id") id: String, @Body body: DecisionIn): CustodyAdjustmentDto
    // --- accountability: one record by id (DEC-030 G5, notification taps open the exact record) -------------------

    @GET("api/v1/tenant/customer-discounts/{id}")
    suspend fun customerDiscount(@Path("id") id: String): DiscountDto

    @GET("api/v1/tenant/credit-arrangements/{id}")
    suspend fun creditArrangement(@Path("id") id: String): CreditArrangementDto

    @GET("api/v1/tenant/hours-transfers/{id}")
    suspend fun hoursTransfer(@Path("id") id: String): HoursTransferDto

    @GET("api/v1/tenant/hours-cancellations/{id}")
    suspend fun hoursCancellation(@Path("id") id: String): HoursCancellationDto

    @GET("api/v1/tenant/meter-baselines/{id}")
    suspend fun meterBaseline(@Path("id") id: String): BaselineDto

    @GET("api/v1/tenant/engine-hours/classifications/{id}")
    suspend fun engineHourClassification(@Path("id") id: String): ClassificationDto

    @GET("api/v1/tenant/meter-corrections/{id}")
    suspend fun meterCorrection(@Path("id") id: String): CorrectionDto

    @GET("api/v1/tenant/cash/variances/{id}")
    suspend fun cashVariance(@Path("id") id: String): CashVarianceDto

    /** getCashRetention (custody read: office readers any, field recorders their own). */
    @GET("api/v1/tenant/cash/retentions/{id}")
    suspend fun cashRetention(@Path("id") id: String): CashRetentionDto

    @GET("api/v1/tenant/cash/adjustments/{id}")
    suspend fun custodyAdjustment(@Path("id") id: String): CustodyAdjustmentDto

    @GET("api/v1/tenant/cash/transfers/{id}")
    suspend fun cashTransfer(@Path("id") id: String): CashTransferDto

    /** getCashFloat: one float with its acknowledgement state. */
    @GET("api/v1/tenant/cash/floats/{id}")
    suspend fun cashFloat(@Path("id") id: String): CashCustodyEntryDto

    @GET("api/v1/tenant/cash/handovers/{id}")
    suspend fun cashHandover(@Path("id") id: String): CashHandoverDto

    /** listCashRemittanceOverdue (tenant.finance.read): custodians flagged past the daily cut-off, latest day first. */
    @GET("api/v1/tenant/cash/remittance-overdue")
    suspend fun remittanceOverdue(
        @Query("day_from") dayFrom: String? = null,
        @Query("day_to") dayTo: String? = null,
        @Query("page_size") pageSize: Int = 100,
    ): PageDto<RemittanceOverdueDto>

    @GET("api/v1/tenant/cash/remittance-overdue/{id}")
    suspend fun remittanceOverdueFlag(@Path("id") id: String): RemittanceOverdueDto

    // --- DEC-031 Phase 1: revenue reconciliation (online only; 422 REVENUE_RECONCILIATION_DISABLED while off) ------
    /** listDailyMachineSheet (tenant.revenue.read): one row per machine per local day, at most 93 days. */
    @GET("api/v1/tenant/daily-machine-sheet")
    suspend fun dailyMachineSheet(
        @Query("machine_id") machineId: String? = null,
        @Query("day_from") dayFrom: String? = null,
        @Query("day_to") dayTo: String? = null,
        @Query("page_size") pageSize: Int = 100,
    ): PageDto<com.asseta.core.model.owner.DailyMachineSheetRowDto>

    @GET("api/v1/tenant/daily-machine-sheet/{machine_id}/{day}")
    suspend fun dailyMachineSheetDay(@Path("machine_id") machineId: String, @Path("day") day: String): com.asseta.core.model.owner.DailyMachineSheetDetailDto

    @GET("api/v1/tenant/revenue-differences")
    suspend fun revenueDifferences(
        @Query("status") status: String? = null,
        @Query("machine_id") machineId: String? = null,
        @Query("page_size") pageSize: Int = 100,
    ): PageDto<com.asseta.core.model.owner.RevenueDifferenceDto>

    @GET("api/v1/tenant/revenue-differences/{id}")
    suspend fun revenueDifference(@Path("id") id: String): com.asseta.core.model.owner.RevenueDifferenceDto

    /** explainRevenueDifference (tenant.revenue.explain): OPEN -> EXPLANATION_PROPOSED. */
    @POST("api/v1/tenant/revenue-differences/{id}/explanation")
    suspend fun explainRevenueDifference(
        @Path("id") id: String,
        @Body body: com.asseta.core.model.owner.RevenueExplanationIn,
    ): com.asseta.core.model.owner.RevenueDifferenceDto

    /** decideRevenueDifference (tenant.revenue.decide; never the explainer). */
    @POST("api/v1/tenant/revenue-differences/{id}/decision")
    suspend fun decideRevenueDifference(
        @Path("id") id: String,
        @Body body: com.asseta.core.model.owner.RevenueDecisionIn,
    ): com.asseta.core.model.owner.RevenueDifferenceDto

    /** listRevenueReasons (tenant.revenue.read); inactive ones are left out unless asked for. */
    @GET("api/v1/tenant/revenue-reasons")
    suspend fun revenueReasons(@Query("page_size") pageSize: Int = 100): PageDto<com.asseta.core.model.owner.RevenueReasonDto>

    /** listNonRevenueActivities (tenant.revenue.read): non-revenue work-log entries with their approval status. */
    @GET("api/v1/tenant/non-revenue-activities")
    suspend fun nonRevenueActivities(
        @Query("job_id") jobId: String? = null,
        @Query("machine_id") machineId: String? = null,
        @Query("page_size") pageSize: Int = 100,
    ): PageDto<com.asseta.core.model.owner.NonRevenueActivityDto>

    @GET("api/v1/tenant/non-revenue-approvals")
    suspend fun nonRevenueApprovals(
        @Query("status") status: String? = null,
        @Query("page_size") pageSize: Int = 100,
    ): PageDto<com.asseta.core.model.owner.NonRevenueApprovalDto>

    @GET("api/v1/tenant/non-revenue-approvals/{id}")
    suspend fun nonRevenueApproval(@Path("id") id: String): com.asseta.core.model.owner.NonRevenueApprovalDto

    /** proposeNonRevenue (tenant.revenue.explain): 409 NON_REVENUE_PENDING, 422 NON_REVENUE_APPROVAL_NOT_REQUIRED. */
    @POST("api/v1/tenant/non-revenue-approvals")
    suspend fun proposeNonRevenue(@Body body: com.asseta.core.model.owner.NonRevenueApprovalIn): com.asseta.core.model.owner.NonRevenueApprovalDto

    /** decideNonRevenue (tenant.revenue.decide; never the proposer). */
    @POST("api/v1/tenant/non-revenue-approvals/{id}/decision")
    suspend fun decideNonRevenue(
        @Path("id") id: String,
        @Body body: com.asseta.core.model.owner.NonRevenueDecisionIn,
    ): com.asseta.core.model.owner.NonRevenueApprovalDto

    // --- customer hours, read-only (DEC-031 P4) ----------------------------------------------------------------------

    /** listHoursPurchases for the Owner list (open purchases, with names). */
    @GET("api/v1/tenant/hours-purchases")
    suspend fun ownerHoursPurchases(
        @Query("cancelled") cancelled: Boolean? = false,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 100,
    ): PageDto<com.asseta.core.model.owner.OwnerHoursPurchaseDto>

    /** getHoursPurchase */
    @GET("api/v1/tenant/hours-purchases/{id}")
    suspend fun hoursPurchase(@Path("id") id: String): com.asseta.core.model.owner.OwnerHoursPurchaseDto

    /** getCustomerHoursStatement: [dateFrom]..[dateTo] local days (at most 366). */
    @GET("api/v1/tenant/customers/{customer_id}/hours-statement")
    suspend fun customerHoursStatement(
        @Path("customer_id") customerId: String,
        @Query("date_from") dateFrom: String,
        @Query("date_to") dateTo: String,
        @Query("machine_id") machineId: String? = null,
    ): com.asseta.core.model.owner.HoursStatementDto

    /** downloadCustomerHoursStatementPdf: the same statement as a PDF. */
    @retrofit2.http.Streaming
    @GET("api/v1/tenant/customers/{customer_id}/hours-statement.pdf")
    suspend fun customerHoursStatementPdf(
        @Path("customer_id") customerId: String,
        @Query("date_from") dateFrom: String,
        @Query("date_to") dateTo: String,
        @Query("machine_id") machineId: String? = null,
    ): okhttp3.ResponseBody

    // --- oversight (DEC-031 Phase 5) ---------------------------------------------------------------------------------

    /** listScorecard: one row per person for the local days [dayFrom]..[dayTo] (at most 93). */
    @GET("api/v1/tenant/scorecard")
    suspend fun scorecard(
        @Query("day_from") dayFrom: String? = null,
        @Query("day_to") dayTo: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 100,
    ): PageDto<com.asseta.core.model.owner.ScorecardRowDto>

    /** getScorecard: one person's figures and the records behind them. */
    @GET("api/v1/tenant/scorecard/{staff_member_id}")
    suspend fun scorecardDetail(
        @Path("staff_member_id") staffMemberId: String,
        @Query("day_from") dayFrom: String? = null,
        @Query("day_to") dayTo: String? = null,
        @Query("item") item: String? = null,
    ): com.asseta.core.model.owner.ScorecardDetailDto

    /** listUnbilledWork */
    @GET("api/v1/tenant/unbilled-work")
    suspend fun unbilledWork(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 100,
    ): PageDto<com.asseta.core.model.owner.UnbilledJobDto>

    /** listIdleMachines */
    @GET("api/v1/tenant/idle-machines")
    suspend fun idleMachines(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 100,
    ): PageDto<com.asseta.core.model.owner.IdleMachineDto>

    /** mySiteCheckins: my schedule (slots) and my own check-ins (default the last 7 days). */
    @GET("api/v1/tenant/site-checkins/mine")
    suspend fun mySiteCheckins(
        @Query("day_from") dayFrom: String? = null,
        @Query("day_to") dayTo: String? = null,
    ): com.asseta.core.model.owner.MySiteCheckinsDto

    // --- go-live setup checklist ------------------------------------------------------------------------------------

    /** getSetupChecklist (tenant.setup.read). */
    @GET("api/v1/tenant/setup-checklist")
    suspend fun setupChecklist(): com.asseta.core.model.owner.SetupChecklistDto

    /** markSetupStepNotNeeded (tenant.setup.manage); 422 SETUP_STEP_REQUIRED for a step that cannot be skipped. */
    @POST("api/v1/tenant/setup-checklist/steps/{key}/not-needed")
    suspend fun markSetupStepNotNeeded(
        @Path("key") key: String,
        @Body body: com.asseta.core.model.owner.SetupNotNeededIn,
    ): com.asseta.core.model.owner.SetupChecklistDto

    /** undoSetupStepNotNeeded (tenant.setup.manage). */
    @DELETE("api/v1/tenant/setup-checklist/steps/{key}/not-needed")
    suspend fun undoSetupStepNotNeeded(@Path("key") key: String): com.asseta.core.model.owner.SetupChecklistDto

    /** confirmSetupControls (tenant.setup.manage): the default controls are fine. */
    @POST("api/v1/tenant/setup-checklist/confirm-controls")
    suspend fun confirmSetupControls(@Body body: com.asseta.core.model.owner.SetupConfirmControlsIn): com.asseta.core.model.owner.SetupChecklistDto
}
