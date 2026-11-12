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

/** Supplies a currently valid access token (refreshing if needed), or null when signed out. Called off the main thread. */
fun interface AccessTokenProvider {
    fun accessToken(): String?
}

/** Supplies the tenant the user selected, or null for tenant-independent calls such as `/me`. */
fun interface TenantIdProvider {
    fun tenantId(): String?
}

/** Supplies the stable device identity sent as `X-Device-Id` on every `/api/v1/sync` call. */
fun interface DeviceIdProvider {
    fun deviceId(): String
}
