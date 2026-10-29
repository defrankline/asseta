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
    @SerialName("platform_menus") val platformMenus: List<MenuEntry> = emptyList(),
    @SerialName("platform_menu_groups") val platformMenuGroups: List<MenuGroup> = emptyList(),
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
    val menus: List<MenuEntry> = emptyList(),
    @SerialName("menu_groups") val menuGroups: List<MenuGroup> = emptyList(),
    /** Tenant capabilities switched off by policy (e.g. `CUSTOMER_HOURS`); their entry points are hidden. */
    @SerialName("disabled_capabilities") val disabledCapabilities: List<String> = emptyList(),
    /** Go-live checklist figures for the dashboard banner; all null without `tenant.setup.read`. */
    @SerialName("setup_complete") val setupComplete: Boolean? = null,
    @SerialName("setup_percent") val setupPercent: Int? = null,
    @SerialName("setup_steps_done") val setupStepsDone: Int? = null,
    @SerialName("setup_steps_total") val setupStepsTotal: Int? = null,
    @SerialName("setup_dismissed") val setupDismissed: Boolean? = null,
) {
    companion object {
        /** The tenant's customer-hours capability (CUSTOMER_HOURS policy `enabled`). */
        const val CUSTOMER_HOURS = "CUSTOMER_HOURS"

        /** Engine-hour controls (ENGINE_HOURS policy `enabled`): daily readings, baselines, corrections, classifications. */
        const val ENGINE_HOURS = "ENGINE_HOURS"

        /** The DEC-030 cash custody additions (CASH_CUSTODY policy `enabled`); collections, floats and remittances stay. */
        const val CASH_CUSTODY = "CASH_CUSTODY"

        /** Revenue reconciliation (REVENUE_RECONCILIATION policy `enabled`, DEC-031; platform default off). */
        const val REVENUE_RECONCILIATION = "REVENUE_RECONCILIATION"

        /** DEC-031 Phase 5 oversight switches (OVERSIGHT policy; platform default off, listed in `/me` while off). */
        const val SCORECARD = "SCORECARD"
        const val UNBILLED_WORK = "UNBILLED_WORK"
        const val IDLE_MACHINES = "IDLE_MACHINES"
        const val SITE_CHECKIN = "SITE_CHECKIN"
    }
}

/** Server-driven menu entry (`MenuDto`): grouped navigation hints, never authorization. */
@Serializable
data class MenuEntry(
    val key: String,
    val label: String,
    val path: String,
    val order: Int,
    val group: String,
)

/** Navigation group (`MenuGroupDto`) that [MenuEntry.group] refers to. */
@Serializable
data class MenuGroup(val key: String, val label: String, val order: Int)

/** Typed id helper so tenant ids are not confused with other UUIDs in signatures. */
@JvmInline
value class TenantId(val value: UUID) {
    override fun toString(): String = value.toString()
}
