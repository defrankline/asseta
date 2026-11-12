package com.asseta.core.model.owner

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/*
 * Company closure (contracts/openapi.json `CompanyDeletionStatusDto`, `CompanyDeletionRequestDto`). Starting a closure
 * is web-only; the Owner app shows the request and can cancel it. Status stays text so a new state never breaks an app.
 */

/** `CompanyDeletionStatusDto`: the active (else latest) closure request, or none. */
@Serializable
data class CompanyClosureStatusDto(
    @SerialName("tenant_id") val tenantId: String? = null,
    @SerialName("company_name") val companyName: String,
    @SerialName("waiting_days") val waitingDays: Int,
    val request: CompanyClosureRequestDto? = null,
)

/** `CompanyDeletionRequestDto` (the fields the app shows): status REQUESTED | CANCELLED | IN_PROGRESS | COMPLETED. */
@Serializable
data class CompanyClosureRequestDto(
    val id: String,
    val status: String,
    val reason: String = "",
    @SerialName("requested_by_name") val requestedByName: String? = null,
    @SerialName("requested_at") val requestedAt: String,
    @SerialName("scheduled_for") val scheduledFor: String,
    @SerialName("cancelled_by_name") val cancelledByName: String? = null,
    @SerialName("cancelled_at") val cancelledAt: String? = null,
    @SerialName("cancel_reason") val cancelReason: String? = null,
)

/** `DeletionReasonIn`: why the closure is cancelled (3 to 1000 characters). */
@Serializable
data class ClosureCancelIn(val reason: String)
