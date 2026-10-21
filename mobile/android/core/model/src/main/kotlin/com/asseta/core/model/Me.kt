package com.asseta.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import java.util.UUID

/**
 * Response of `GET /api/v1/me`. Permissions/menus are server-computed (Keycloak + Asseta RBAC);
 * clients use them only to hide UI, never to authorize.
 */
@Serializable
data class MeResponse(
    @SerialName("user_id") val userId: SerializableUuid,
    val email: String,
    @SerialName("display_name") val displayName: String,
    @SerialName("platform_permissions") val platformPermissions: List<String> = emptyList(),
    @SerialName("platform_menus") val platformMenus: List<String> = emptyList(),
    val tenants: List<TenantAccess> = emptyList(),
)

@Serializable
data class TenantAccess(
    @SerialName("tenant_id") val tenantId: SerializableUuid,
    val name: String,
    /** Server-owned tenant status string (e.g. ACTIVE, SUSPENDED); kept open so new states do not crash old apps. */
    val status: String,
    /** Server-computed effective access (subscription/membership); the app only reflects it in UI. */
    @SerialName("access_state") val accessState: TenantAccessState = TenantAccessState.UNKNOWN,
    val permissions: List<String> = emptyList(),
    val menus: List<String> = emptyList(),
)

/** Typed id helper so tenant ids are not confused with other UUIDs in signatures. */
@JvmInline
value class TenantId(val value: UUID) {
    override fun toString(): String = value.toString()
}
