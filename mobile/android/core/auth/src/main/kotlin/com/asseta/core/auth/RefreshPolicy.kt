package com.asseta.core.auth

import net.openid.appauth.AuthorizationException

/** What a token refresh (or the lack of one) means for the session. */
enum class RefreshOutcome {
    /** Fresh tokens (or the current ones were still valid). */
    OK,

    /** The sign-in server refused the refresh token: the session is over. */
    SESSION_ENDED,

    /** No answer worth trusting (offline, timeout, DNS, captive portal, 5xx): keep the session, try again later. */
    TRY_LATER,
}

/**
 * Only an authoritative refusal ends a session. Supervisors work offline for days, so a refresh that fails for any
 * other reason keeps the stored tokens.
 */
object RefreshPolicy {
    /** OAuth error codes a failing sign-in server returns with HTTP 5xx: trouble on its side, not a refusal. */
    private val SERVER_TROUBLE = setOf("server_error", "temporarily_unavailable", "unknown_error")

    /**
     * Classifies an AppAuth refresh result. AppAuth reports [AuthorizationException.TYPE_OAUTH_TOKEN_ERROR] only when the
     * token endpoint answered with an OAuth error body (HTTP 400/401: `invalid_grant` for an expired, revoked or
     * rotated-out refresh token, `invalid_client`, ...): that ends the session. Network errors, unreadable bodies (a
     * proxy or captive-portal page) and server-trouble codes are [RefreshOutcome.TRY_LATER].
     */
    fun classify(errorType: Int?, errorCode: String?): RefreshOutcome = when {
        errorType == null -> RefreshOutcome.OK
        errorType == AuthorizationException.TYPE_OAUTH_TOKEN_ERROR && !errorCode.isNullOrBlank() && errorCode !in SERVER_TROUBLE ->
            RefreshOutcome.SESSION_ENDED
        else -> RefreshOutcome.TRY_LATER
    }

    fun classify(error: AuthorizationException?): RefreshOutcome = classify(error?.type, error?.error)
}
