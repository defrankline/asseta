package com.asseta.core.ui.session

import com.asseta.core.model.MeResponse
import com.asseta.core.model.TenantAccess
import com.asseta.core.network.ApiException

/** User-presentable failure; [reference] is the server correlation id for support. */
data class UiError(val message: String, val reference: String? = null)

sealed interface SessionState {
    data class SignedOut(val error: UiError? = null, val busy: Boolean = false) : SessionState
    data object LoadingProfile : SessionState
    data class ProfileError(val error: UiError) : SessionState
    data class Ready(val me: MeResponse, val selectedTenantId: String?) : SessionState {
        val selectedTenant: TenantAccess? get() = me.tenants.firstOrNull { it.tenantId.toString() == selectedTenantId }
    }
}

internal object SessionRules {
    /**
     * Keeps a previously chosen tenant only if the server still lists it as enterable; a single enterable
     * tenant is auto-selected. UI convenience only: the server re-checks access on every request.
     */
    fun resolveSelection(me: MeResponse, previous: String?): String? {
        val enterable = me.tenants.filter { it.accessState.canEnter }
        return enterable.firstOrNull { it.tenantId.toString() == previous }?.tenantId?.toString()
            ?: enterable.singleOrNull()?.tenantId?.toString()
    }

    fun toUiError(t: Throwable): UiError = when (t) {
        is ApiException -> UiError(t.message, t.correlationId)
        is java.io.IOException -> UiError("Cannot reach Asseta. Check your connection and try again.")
        else -> UiError(t.message ?: "Unexpected error")
    }
}
