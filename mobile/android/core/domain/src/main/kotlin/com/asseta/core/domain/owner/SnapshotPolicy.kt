package com.asseta.core.domain.owner

/**
 * Bounds of the Owner app's offline read-only cache: snapshots older than [maxAgeMs] are never shown and are purged;
 * each tenant keeps at most [maxEntriesPerTenant] snapshots (oldest evicted); payloads above [maxPayloadBytes] are
 * not cached at all. Cached data is always presented as stale.
 */
data class SnapshotPolicy(
    val maxAgeMs: Long = 7L * 24 * 3_600_000,
    val maxEntriesPerTenant: Int = 200,
    val maxPayloadBytes: Int = 512 * 1024,
) {
    init {
        require(maxAgeMs > 0 && maxEntriesPerTenant > 0 && maxPayloadBytes > 0)
    }

    fun isExpired(fetchedAtMs: Long, nowMs: Long): Boolean = nowMs - fetchedAtMs > maxAgeMs

    /** Purge threshold: everything fetched before this instant is deleted. */
    fun purgeBefore(nowMs: Long): Long = nowMs - maxAgeMs

    fun cacheable(payloadBytes: Int): Boolean = payloadBytes <= maxPayloadBytes
}

/** Why a request failed, as far as the offline fallback is concerned. */
enum class FailureKind {
    /** No connection / timeout / DNS: fall back to the cache. */
    NETWORK,
    /** 401: the session ended. */
    UNAUTHENTICATED,
    /** 403 on the tenant (membership revoked / tenant blocked): wipe that tenant's cache. */
    TENANT_REVOKED,
    /** Any other server answer (validation, 404, 5xx, permission on one screen). */
    SERVER,
}

sealed interface FallbackDecision {
    /** Show the cached snapshot, marked stale. */
    data object UseCache : FallbackDecision
    /** Show the error (with retry); no usable cache. */
    data object ShowError : FallbackDecision
    /** Delete this tenant's cached data and show the error. */
    data object WipeTenant : FallbackDecision
    /** The session ended: sign out (which wipes the whole cache). */
    data object EndSession : FallbackDecision
}

object OfflineFallback {
    /** Error codes meaning the user no longer may enter this tenant at all (vs. lacking one screen's permission). */
    val TENANT_REVOKED_CODES = setOf("TENANT_ACCESS_DENIED", "TENANT_ACCESS_BLOCKED", "MANDATE_REQUIRED", "MANDATE_ENDED")

    fun classify(httpStatus: Int?, code: String?): FailureKind = when {
        httpStatus == null -> FailureKind.NETWORK
        httpStatus == 401 -> FailureKind.UNAUTHENTICATED
        httpStatus == 403 && code in TENANT_REVOKED_CODES -> FailureKind.TENANT_REVOKED
        else -> FailureKind.SERVER
    }

    /** Only a network failure may fall back to (unexpired) cached data; server refusals are never masked. */
    fun decide(kind: FailureKind, cachedFetchedAtMs: Long?, nowMs: Long, policy: SnapshotPolicy): FallbackDecision = when (kind) {
        FailureKind.TENANT_REVOKED -> FallbackDecision.WipeTenant
        FailureKind.UNAUTHENTICATED -> FallbackDecision.EndSession
        FailureKind.SERVER -> FallbackDecision.ShowError
        FailureKind.NETWORK ->
            if (cachedFetchedAtMs != null && !policy.isExpired(cachedFetchedAtMs, nowMs)) FallbackDecision.UseCache else FallbackDecision.ShowError
    }
}
