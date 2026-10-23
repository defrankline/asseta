package com.asseta.core.ui.session

import com.asseta.core.auth.PasswordChangeResult
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

/** "Change password" (Keycloak `UPDATE_PASSWORD` action): in progress, or a result waiting to be acknowledged. */
sealed interface PasswordChangeState {
    data object Idle : PasswordChangeState
    data object InProgress : PasswordChangeState
    data object Changed : PasswordChangeState
    data class Failed(val message: String) : PasswordChangeState
}

/** Shared wording of the "Change password" account action (identical on iOS). */
object PasswordChangeText {
    const val ACTION = "Change password"
    const val FOOTER = "Opens the secure Asseta sign-in page."
    const val OFFLINE = "Connect to the internet to change your password."
    const val CHANGED = "Password changed."
    const val FAILED_TITLE = "Couldn't change password"
}

internal object SessionRules {
    /** A cancel shows nothing; the user stays signed in whatever the outcome. */
    fun passwordChangeState(result: PasswordChangeResult): PasswordChangeState = when (result) {
        PasswordChangeResult.Changed -> PasswordChangeState.Changed
        PasswordChangeResult.Cancelled -> PasswordChangeState.Idle
        is PasswordChangeResult.Failed -> PasswordChangeState.Failed(result.reason)
    }

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
