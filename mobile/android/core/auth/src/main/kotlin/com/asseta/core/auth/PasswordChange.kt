package com.asseta.core.auth

import androidx.core.net.toUri
import net.openid.appauth.AuthorizationException
import net.openid.appauth.AuthorizationRequest
import net.openid.appauth.AuthorizationResponse
import net.openid.appauth.AuthorizationServiceConfiguration
import net.openid.appauth.ResponseTypeValues

/** Outcome of the Keycloak "Change password" action, as shown to the user. */
sealed interface PasswordChangeResult {
    data object Changed : PasswordChangeResult
    /** The user backed out; nothing is shown. */
    data object Cancelled : PasswordChangeResult
    data class Failed(val reason: String) : PasswordChangeResult
}

/**
 * Keycloak application-initiated action `UPDATE_PASSWORD`: the normal sign-in request (same client, PKCE, redirect,
 * scopes) plus `kc_action`. Keycloak shows its own password page (re-authenticating if needed) and redirects back with
 * a code and `kc_action_status`. The app never sees the password.
 */
object PasswordChange {
    const val ACTION_PARAM = "kc_action"
    const val UPDATE_PASSWORD = "UPDATE_PASSWORD"
    const val STATUS_PARAM = "kc_action_status"
    const val FAILED_MESSAGE = "Your password was not changed. Please try again."

    /** Builds the sign-in authorization request; [kcAction] adds a Keycloak application-initiated action. */
    fun authorizationRequest(
        serviceConfig: AuthorizationServiceConfiguration,
        config: AuthConfig,
        kcAction: String? = null,
    ): AuthorizationRequest = AuthorizationRequest.Builder(
        serviceConfig, config.clientId, ResponseTypeValues.CODE, config.redirectUri.toUri(),
    ).setScopes(config.scopes)
        .apply { if (kcAction != null) setAdditionalParameters(mapOf(ACTION_PARAM to kcAction)) }
        .build()

    /** Maps Keycloak's `kc_action_status` (success | cancelled | error) to the user-facing result. */
    fun resultFor(status: String?): PasswordChangeResult = when (status) {
        "success" -> PasswordChangeResult.Changed
        "cancelled" -> PasswordChangeResult.Cancelled
        else -> PasswordChangeResult.Failed(FAILED_MESSAGE)
    }

    /** Result for a redirect without a usable response (closed browser tab or an `error=` redirect). */
    fun resultFor(response: AuthorizationResponse?, error: AuthorizationException?): PasswordChangeResult = when {
        response != null -> resultFor(response.additionalParameters[STATUS_PARAM])
        error == null || error == AuthorizationException.GeneralErrors.USER_CANCELED_AUTH_FLOW ->
            PasswordChangeResult.Cancelled
        else -> PasswordChangeResult.Failed(FAILED_MESSAGE)
    }
}
