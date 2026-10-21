package com.asseta.core.network

import com.asseta.core.model.ErrorEnvelope
import kotlinx.serialization.json.Json
import okhttp3.Interceptor
import okhttp3.Response
import java.util.UUID

/** Adds `Authorization: Bearer` when a session exists. Never invents credentials. */
class AuthInterceptor(private val tokens: AccessTokenProvider) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = tokens.accessToken()
        val request = if (token.isNullOrBlank()) chain.request() else
            chain.request().newBuilder().header(AssetaHeaders.AUTHORIZATION, "Bearer $token").build()
        return chain.proceed(request)
    }
}

/** Adds `X-Tenant-ID` for the selected tenant unless the caller already set one explicitly. */
class TenantInterceptor(private val tenant: TenantIdProvider) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        val tenantId = tenant.tenantId()
        if (tenantId == null || original.header(AssetaHeaders.TENANT_ID) != null) return chain.proceed(original)
        return chain.proceed(original.newBuilder().header(AssetaHeaders.TENANT_ID, tenantId).build())
    }
}

/** A fresh UUID `X-Correlation-ID` per request (kept if the caller supplied one, e.g. to correlate a retry chain). */
class CorrelationIdInterceptor(private val newId: () -> String = { UUID.randomUUID().toString() }) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        if (original.header(AssetaHeaders.CORRELATION_ID) != null) return chain.proceed(original)
        return chain.proceed(original.newBuilder().header(AssetaHeaders.CORRELATION_ID, newId()).build())
    }
}

/**
 * Ensures every mutation carries an `Idempotency-Key`. Outbox callers must pass their operation UUID
 * explicitly so the key survives app restarts; a generated key only covers OkHttp-level retries of one call.
 */
class IdempotencyKeyInterceptor(private val newKey: () -> String = { UUID.randomUUID().toString() }) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        if (original.method !in MUTATING || original.header(AssetaHeaders.IDEMPOTENCY_KEY) != null) {
            return chain.proceed(original)
        }
        return chain.proceed(original.newBuilder().header(AssetaHeaders.IDEMPOTENCY_KEY, newKey()).build())
    }

    private companion object {
        val MUTATING = setOf("POST", "PUT", "PATCH", "DELETE")
    }
}

/** Converts non-2xx responses into [ApiException], parsing the standard error envelope when present. */
class ErrorEnvelopeInterceptor(private val json: Json) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val response = chain.proceed(chain.request())
        if (response.isSuccessful) return response
        throw response.use { toApiException(it, json) }
    }

    companion object {
        private const val MAX_ERROR_BYTES = 64L * 1024

        fun toApiException(response: Response, json: Json): ApiException {
            val headerCid = response.header(AssetaHeaders.CORRELATION_ID)
                ?: response.request.header(AssetaHeaders.CORRELATION_ID)
            val raw = runCatching { response.peekBody(MAX_ERROR_BYTES).string() }.getOrDefault("")
            val envelope = runCatching { json.decodeFromString(ErrorEnvelope.serializer(), raw) }.getOrNull()
            return if (envelope != null) {
                ApiException(response.code, envelope.error.code, envelope.error.message,
                    envelope.error.correlationId, envelope.error.details)
            } else {
                ApiException(response.code, "HTTP_${response.code}",
                    response.message.ifBlank { "Unexpected HTTP ${response.code}" }, headerCid)
            }
        }
    }
}
