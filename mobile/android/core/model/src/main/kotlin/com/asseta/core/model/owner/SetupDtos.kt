package com.asseta.core.model.owner

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/*
 * Go-live setup checklist (contracts/openapi.json `SetupChecklistDto`). Step keys and statuses stay text so a new
 * step or status from the server never breaks an older app.
 */

/** `SetupChecklistDto`: the tenant's go-live steps, computed live from its records. */
@Serializable
data class SetupChecklistDto(
    val steps: List<SetupStepDto> = emptyList(),
    @SerialName("steps_done") val stepsDone: Int,
    @SerialName("steps_total") val stepsTotal: Int,
    val percent: Int,
    val complete: Boolean,
    val dismissed: Boolean,
    @SerialName("dismissed_by") val dismissedBy: String? = null,
    @SerialName("dismissed_by_name") val dismissedByName: String? = null,
    @SerialName("dismissed_at") val dismissedAt: String? = null,
    @SerialName("controls_confirmed_by") val controlsConfirmedBy: String? = null,
    @SerialName("controls_confirmed_by_name") val controlsConfirmedByName: String? = null,
    @SerialName("controls_confirmed_at") val controlsConfirmedAt: String? = null,
    @SerialName("as_of") val asOf: String,
)

/** `SetupStepDto`: status DONE | TODO | NOT_NEEDED | NOT_APPLICABLE; [link] is the web route of the first part to do. */
@Serializable
data class SetupStepDto(
    val key: String,
    val order: Int,
    val title: String,
    val description: String,
    val status: String,
    @SerialName("done_count") val doneCount: Int? = null,
    @SerialName("total_count") val totalCount: Int? = null,
    val link: String,
    @SerialName("required_permission") val requiredPermission: String,
    @SerialName("can_mark_not_needed") val canMarkNotNeeded: Boolean,
    @SerialName("not_needed") val notNeeded: SetupNotNeededDto? = null,
    val checks: List<SetupCheckDto> = emptyList(),
)

/** `SetupCheckDto`: one part of a step (an optional part never holds the step back). */
@Serializable
data class SetupCheckDto(
    val key: String,
    val label: String,
    val done: Boolean,
    val optional: Boolean = false,
    @SerialName("done_count") val doneCount: Int? = null,
    @SerialName("total_count") val totalCount: Int? = null,
    val link: String,
    @SerialName("required_permission") val requiredPermission: String,
)

/** `NotNeededDto`: why and by whom a step was marked as not needed. */
@Serializable
data class SetupNotNeededDto(
    val reason: String? = null,
    @SerialName("marked_by") val markedBy: String,
    @SerialName("marked_by_name") val markedByName: String? = null,
    @SerialName("marked_at") val markedAt: String,
)

/** `NotNeededIn` (reason 3–500 characters). */
@Serializable
data class SetupNotNeededIn(val reason: String)

/** `ConfirmControlsIn`. */
@Serializable
data class SetupConfirmControlsIn(val note: String? = null)
