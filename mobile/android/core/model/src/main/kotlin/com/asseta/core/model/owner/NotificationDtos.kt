package com.asseta.core.model.owner

import com.asseta.core.model.SerializableUuid
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

/** `NotificationDto` (inbox, WebSocket `notification` frames). [target] says what the notification is about. */
@Serializable
data class NotificationDto(
    val id: SerializableUuid,
    val type: String,
    val category: String,
    val severity: String,
    val priority: String,
    val title: String,
    val body: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("read_at") val readAt: String? = null,
    val target: NotificationTargetDto? = null,
    @SerialName("tenant_id") val tenantId: SerializableUuid? = null,
    val data: Map<String, JsonElement> = emptyMap(),
)

@Serializable
data class NotificationTargetDto(val entity: String, val id: String? = null, val path: String? = null)

@Serializable
data class NotificationUnreadCountDto(val count: Int)

@Serializable
data class NotificationMarkReadIn(val ids: List<String>)

@Serializable
data class NotificationMarkReadResultDto(val updated: Int, val unread: Int)

/**
 * `NotificationRoutingDto`: one row of the per-user category x severity matrix. [mandatoryChannels] cannot be turned
 * off (the server answers `422 MANDATORY_CHANNEL`).
 */
@Serializable
data class NotificationRoutingDto(
    val category: String,
    val severity: String,
    val push: Boolean,
    val email: Boolean,
    val source: String,
    @SerialName("mandatory_channels") val mandatoryChannels: List<String> = emptyList(),
    @SerialName("in_app") val inApp: Boolean? = null,
)

@Serializable
data class NotificationRoutingChangeIn(val category: String, val severity: String, val push: Boolean, val email: Boolean)

@Serializable
data class NotificationRoutingIn(
    val changes: List<NotificationRoutingChangeIn>,
    @SerialName("tenant_default") val tenantDefault: Boolean = false,
)

/** `PushDeviceIn` (registerPushDevice): platform ANDROID, app OWNER for this app. */
@Serializable
data class PushDeviceIn(
    val token: String,
    val platform: String,
    val app: String,
    @SerialName("app_version") val appVersion: String? = null,
    @SerialName("device_label") val deviceLabel: String? = null,
)

@Serializable
data class PushDeviceDto(
    val id: SerializableUuid,
    val platform: String,
    val app: String,
    val active: Boolean,
    @SerialName("token_hint") val tokenHint: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("last_registered_at") val lastRegisteredAt: String,
    @SerialName("app_version") val appVersion: String? = null,
    @SerialName("device_label") val deviceLabel: String? = null,
    @SerialName("tenant_id") val tenantId: SerializableUuid? = null,
    @SerialName("deactivated_at") val deactivatedAt: String? = null,
    @SerialName("deactivation_reason") val deactivationReason: String? = null,
)
