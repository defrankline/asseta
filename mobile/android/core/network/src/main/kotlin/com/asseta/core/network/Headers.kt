package com.asseta.core.network

object AssetaHeaders {
    const val AUTHORIZATION = "Authorization"
    const val TENANT_ID = "X-Tenant-ID"
    const val CORRELATION_ID = "X-Correlation-ID"
    const val IDEMPOTENCY_KEY = "Idempotency-Key"
    const val DEVICE_ID = "X-Device-Id"

    /** Local marker (never sent): the call must go without `X-Tenant-ID` (e.g. account deletion). */
    const val NO_TENANT = "X-Asseta-No-Tenant"

    /** Retrofit `@Headers` value for [NO_TENANT]. */
    const val NO_TENANT_HEADER = "$NO_TENANT: 1"
}

/**
 * Supplies bearer tokens. Called off the main thread (OkHttp threads).
 *
 * Only the sign-in server's refusal ends a session: a provider returns null only when there is no session (signed out,
 * or the token endpoint refused the refresh token). When a session exists but no token can be had right now (offline,
 * timeout, sign-in server unreachable or failing) it throws [TokenUnavailableException], so the call fails like any
 * network failure and the session is kept for a later retry.
 */
fun interface AccessTokenProvider {
    /** A currently valid access token (refreshing first if it is about to expire), or null when signed out. */
    fun accessToken(): String?

    /**
     * Called after the API refused [rejected] with 401: a different, freshly refreshed token, or null when the session
     * is gone (the call then fails with that 401). Default: no retry.
     */
    fun refreshedAccessToken(rejected: String): String? = null
}

/** A session exists but no access token could be had right now (offline, timeout, sign-in server down): try later. */
class TokenUnavailableException(message: String, cause: Throwable? = null) : java.io.IOException(message, cause)

/** Supplies the tenant the user selected, or null for tenant-independent calls such as `/me`. */
fun interface TenantIdProvider {
    fun tenantId(): String?
}

/** Supplies the stable device identity sent as `X-Device-Id` on every `/api/v1/sync` call. */
fun interface DeviceIdProvider {
    fun deviceId(): String
}
