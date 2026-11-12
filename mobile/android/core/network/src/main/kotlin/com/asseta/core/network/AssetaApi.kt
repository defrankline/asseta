package com.asseta.core.network

import com.asseta.core.model.AccountDeletionRequest
import com.asseta.core.model.AccountDeletionResponse
import com.asseta.core.model.MeResponse
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Headers
import retrofit2.http.POST

/** Versioned Asseta REST API (`/api/v1`): the signed-in user's own endpoints (no tenant). */
interface AssetaApi {
    @GET("api/v1/me")
    suspend fun me(): MeResponse

    /** Deletes the signed-in user's account for good (no `X-Tenant-ID`); every token of it is refused afterwards. */
    @Headers(AssetaHeaders.NO_TENANT_HEADER)
    @POST("api/v1/me/account-deletion")
    suspend fun deleteMyAccount(@Body body: AccountDeletionRequest): AccountDeletionResponse
}
