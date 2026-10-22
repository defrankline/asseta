package com.asseta.owner.data

import com.asseta.core.domain.owner.DataSource
import com.asseta.core.domain.owner.FailureKind
import com.asseta.core.domain.owner.FallbackDecision
import com.asseta.core.domain.owner.OfflineFallback
import com.asseta.core.domain.owner.OwnerErrors
import com.asseta.core.domain.owner.SnapshotPolicy
import com.asseta.core.network.ApiException
import com.asseta.core.network.TenantApi
import com.asseta.core.ui.session.UiError
import kotlinx.coroutines.CancellationException
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import java.io.IOException

/** Callbacks for failures that change the session, raised by any screen's load. */
interface SessionEvents {
    /** 403 tenant access refused: the tenant's cache was wiped; re-read `/me`. */
    fun tenantRevoked(tenantId: String)
    /** 401: the session ended. */
    fun sessionEnded()
}

/**
 * Owner data access: every read goes to the server first and stores the response as a bounded offline snapshot;
 * only a *network* failure falls back to the (unexpired) snapshot, which screens show as stale. Server refusals are
 * never masked by cached data. Mutations are online-only and never queued.
 */
class OwnerRepository(
    val api: TenantApi,
    private val store: SnapshotStore,
    private val json: Json,
    private val policy: SnapshotPolicy,
    private val events: SessionEvents,
    private val clock: () -> Long = System::currentTimeMillis,
) {
    suspend fun <T> load(tenantId: String, key: String, serializer: KSerializer<T>, fetch: suspend TenantApi.() -> T): Load<T> {
        val failure = try {
            val data = api.fetch()
            val now = clock()
            runCatching { store.write(tenantId, key, json.encodeToString(serializer, data), now) }
            return Load.Ok(Snapshot(data, now, DataSource.LIVE))
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            e
        }
        val kind = classify(failure)
        val cached = runCatching { store.read(tenantId, key) }.getOrNull()
        return when (OfflineFallback.decide(kind, cached?.fetchedAtMs, clock(), policy)) {
            FallbackDecision.UseCache -> runCatching { json.decodeFromString(serializer, cached!!.payloadJson) }
                .map { Load.Ok(Snapshot(it, cached!!.fetchedAtMs, DataSource.CACHE)) as Load<T> }
                .getOrElse { Load.Failed(uiError(failure), kind) }
            FallbackDecision.ShowError -> Load.Failed(uiError(failure), kind)
            FallbackDecision.WipeTenant -> {
                runCatching { store.wipeTenant(tenantId) }
                events.tenantRevoked(tenantId)
                Load.Failed(uiError(failure), kind)
            }
            FallbackDecision.EndSession -> {
                events.sessionEnded()
                Load.Failed(uiError(failure), kind)
            }
        }
    }

    /** Online-only call (never cached, never queued). Refusals carry the server code and friendly wording. */
    suspend fun <T> act(block: suspend TenantApi.() -> T): ActionResult<T> = try {
        ActionResult.Done(api.block())
    } catch (e: CancellationException) {
        throw e
    } catch (e: Throwable) {
        val api = e as? ApiException
        if (classify(e) == FailureKind.UNAUTHENTICATED) events.sessionEnded()
        // A tenant refusal (403) makes the screen reload, and that load wipes the tenant's snapshots.
        val reload = api?.code?.let { OwnerErrors.needsReload(it) || it in OfflineFallback.TENANT_REVOKED_CODES } == true
        ActionResult.Refused(uiError(e), api?.code, reload)
    }

    suspend fun purgeExpired() = runCatching { store.purgeExpired(clock()) }

    private fun classify(e: Throwable): FailureKind {
        val api = e as? ApiException
        return when {
            api != null -> OfflineFallback.classify(api.httpStatus, api.code)
            e is IOException -> OfflineFallback.classify(null, null)
            else -> FailureKind.SERVER
        }
    }

    private fun uiError(e: Throwable): UiError = when (e) {
        is ApiException -> UiError(OwnerErrors.message(e.code, e.message), e.correlationId)
        is IOException -> UiError("Cannot reach Asseta. Check your connection and try again.")
        else -> UiError("Unexpected response from the server. Please try again.")
    }
}
