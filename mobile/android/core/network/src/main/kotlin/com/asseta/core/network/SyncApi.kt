package com.asseta.core.network

import com.asseta.core.model.sync.BlobSessionDto
import com.asseta.core.model.sync.BlobStartIn
import com.asseta.core.model.sync.BootstrapDto
import com.asseta.core.model.sync.ChangesDto
import com.asseta.core.model.sync.DeviceRegisterIn
import com.asseta.core.model.sync.DeviceSessionDto
import com.asseta.core.model.sync.PushIn
import com.asseta.core.model.sync.PushResultDto
import okhttp3.RequestBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/** Offline sync protocol v1 (`/api/v1/sync`); operationIds from contracts/openapi.json. `X-Device-Id` is added by [DeviceIdInterceptor].
 * The tenant is explicit per call so a background sync never follows a later tenant switch in the UI. */
interface SyncApi {
    /** registerDevice */
    @POST("api/v1/sync/devices")
    suspend fun registerDevice(@Header(AssetaHeaders.TENANT_ID) tenantId: String, @Body body: DeviceRegisterIn): DeviceSessionDto

    /** syncBootstrap */
    @GET("api/v1/sync/bootstrap")
    suspend fun bootstrap(@Header(AssetaHeaders.TENANT_ID) tenantId: String): BootstrapDto

    /** syncChanges */
    @GET("api/v1/sync/changes")
    suspend fun changes(@Header(AssetaHeaders.TENANT_ID) tenantId: String, @Query("cursor") cursor: Long): ChangesDto

    /** syncPush */
    @POST("api/v1/sync/push")
    suspend fun push(@Header(AssetaHeaders.TENANT_ID) tenantId: String, @Body body: PushIn): PushResultDto

    /** startBlobUpload */
    @POST("api/v1/sync/blobs")
    suspend fun startBlob(@Header(AssetaHeaders.TENANT_ID) tenantId: String, @Body body: BlobStartIn): BlobSessionDto

    /** putBlobChunk: raw chunk bytes as the request body. */
    @PUT("api/v1/sync/blobs/{sessionId}/chunks/{index}")
    suspend fun putChunk(@Header(AssetaHeaders.TENANT_ID) tenantId: String, @Path("sessionId") sessionId: String, @Path("index") index: Int, @Body chunk: RequestBody): BlobSessionDto

    /** completeBlobUpload */
    @POST("api/v1/sync/blobs/{sessionId}/complete")
    suspend fun completeBlob(@Header(AssetaHeaders.TENANT_ID) tenantId: String, @Path("sessionId") sessionId: String): BlobSessionDto
}
