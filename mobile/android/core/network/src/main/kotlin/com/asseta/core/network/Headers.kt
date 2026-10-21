package com.asseta.core.network

object AssetaHeaders {
    const val AUTHORIZATION = "Authorization"
    const val TENANT_ID = "X-Tenant-ID"
    const val CORRELATION_ID = "X-Correlation-ID"
    const val IDEMPOTENCY_KEY = "Idempotency-Key"
}

/** Supplies a currently valid access token (refreshing if needed), or null when signed out. Called off the main thread. */
fun interface AccessTokenProvider {
    fun accessToken(): String?
}

/** Supplies the tenant the user selected, or null for tenant-independent calls such as `/me`. */
fun interface TenantIdProvider {
    fun tenantId(): String?
}
