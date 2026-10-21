package com.asseta.core.network

import com.asseta.core.model.MeResponse
import retrofit2.http.GET

/** Versioned Asseta REST API (`/api/v1`). Only Gate 0 endpoints are declared here. */
interface AssetaApi {
    @GET("api/v1/me")
    suspend fun me(): MeResponse
}
