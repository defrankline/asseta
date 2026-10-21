package com.asseta.core.network

import kotlinx.serialization.json.Json
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit

object NetworkFactory {
    /** Lenient on unknown fields so additive server changes never break deployed apps. */
    val json: Json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
    }

    fun okHttpClient(
        tokens: AccessTokenProvider,
        tenant: TenantIdProvider,
        builder: OkHttpClient.Builder = OkHttpClient.Builder(),
    ): OkHttpClient = builder
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .addInterceptor(CorrelationIdInterceptor())
        .addInterceptor(IdempotencyKeyInterceptor())
        .addInterceptor(TenantInterceptor(tenant))
        .addInterceptor(AuthInterceptor(tokens))
        .addInterceptor(ErrorEnvelopeInterceptor(json))
        .build()

    fun api(baseUrl: String, client: OkHttpClient, allowCleartext: Boolean): AssetaApi {
        require(baseUrl.isNotBlank()) { "API base URL is not configured (gradle property asseta.<buildType>.apiBaseUrl)" }
        val url = baseUrl.toHttpUrl()
        require(allowCleartext || url.isHttps) { "Release builds require an https API base URL" }
        return Retrofit.Builder()
            .baseUrl(url)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(AssetaApi::class.java)
    }

    /** Uses the build-type endpoint from BuildConfig. */
    fun defaultApi(client: OkHttpClient): AssetaApi = api(BuildConfig.API_BASE_URL, client, BuildConfig.ALLOW_CLEARTEXT)
}
