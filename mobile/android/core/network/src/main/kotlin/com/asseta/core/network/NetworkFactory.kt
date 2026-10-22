package com.asseta.core.network

import kotlinx.serialization.json.Json
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit

object NetworkFactory {
    /**
     * Lenient on unknown fields so additive server changes never break deployed apps. Defaults are always encoded
     * (a defaulted field such as `DeviceRegisterIn.platform` is still required by the server); nulls are omitted.
     */
    val json: Json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        encodeDefaults = true
    }

    fun okHttpClient(
        tokens: AccessTokenProvider,
        tenant: TenantIdProvider,
        builder: OkHttpClient.Builder = OkHttpClient.Builder(),
        device: DeviceIdProvider? = null,
    ): OkHttpClient = builder
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .addInterceptor(CorrelationIdInterceptor())
        .addInterceptor(IdempotencyKeyInterceptor())
        .addInterceptor(TenantInterceptor(tenant))
        .apply { if (device != null) addInterceptor(DeviceIdInterceptor(device)) }
        .addInterceptor(AuthInterceptor(tokens))
        .addInterceptor(ErrorEnvelopeInterceptor(json))
        .build()

    fun api(baseUrl: String, client: OkHttpClient, allowCleartext: Boolean): AssetaApi =
        retrofit(baseUrl, client, allowCleartext).create(AssetaApi::class.java)

    fun syncApi(baseUrl: String, client: OkHttpClient, allowCleartext: Boolean): SyncApi =
        retrofit(baseUrl, client, allowCleartext).create(SyncApi::class.java)

    fun tenantApi(baseUrl: String, client: OkHttpClient, allowCleartext: Boolean): TenantApi =
        retrofit(baseUrl, client, allowCleartext).create(TenantApi::class.java)

    private fun retrofit(baseUrl: String, client: OkHttpClient, allowCleartext: Boolean): Retrofit {
        require(baseUrl.isNotBlank()) { "API base URL is not configured (gradle property asseta.<buildType>.apiBaseUrl)" }
        val url = baseUrl.toHttpUrl()
        require(allowCleartext || url.isHttps) { "Release builds require an https API base URL" }
        return Retrofit.Builder()
            .baseUrl(url)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
    }

    /** Uses the build-type endpoint from BuildConfig. */
    fun defaultApi(client: OkHttpClient): AssetaApi = api(BuildConfig.API_BASE_URL, client, BuildConfig.ALLOW_CLEARTEXT)

    fun defaultTenantApi(client: OkHttpClient): TenantApi = tenantApi(BuildConfig.API_BASE_URL, client, BuildConfig.ALLOW_CLEARTEXT)

    /** The build-type API base URL (also the origin of the `/api/v1/ws` WebSocket). */
    val defaultBaseUrl: String get() = BuildConfig.API_BASE_URL

    /** Whether this build may talk to a cleartext (http/ws) endpoint (debug emulator only). */
    val defaultAllowCleartext: Boolean get() = BuildConfig.ALLOW_CLEARTEXT

    fun defaultSyncApi(client: OkHttpClient): SyncApi = syncApi(BuildConfig.API_BASE_URL, client, BuildConfig.ALLOW_CLEARTEXT)
}
