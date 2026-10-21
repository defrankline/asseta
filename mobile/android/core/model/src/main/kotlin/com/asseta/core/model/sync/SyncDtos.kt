package com.asseta.core.model.sync

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/** `/api/v1/sync` protocol v1 DTOs (contracts/openapi.json: registerDevice ... completeBlobUpload). */

@Serializable
data class DeviceRegisterIn(
    @SerialName("device_id") val deviceId: String,
    val platform: String = "ANDROID",
    @SerialName("app_version") val appVersion: String,
)

@Serializable
data class DeviceSessionDto(
    val id: String,
    @SerialName("device_id") val deviceId: String,
    val platform: String,
    @SerialName("app_version") val appVersion: String,
    val status: String,
    @SerialName("registered_at") val registeredAt: String,
    @SerialName("last_sync_at") val lastSyncAt: String? = null,
    @SerialName("offline_grant_until") val offlineGrantUntil: String,
    @SerialName("last_clock_offset_s") val lastClockOffsetS: Double? = null,
    @SerialName("revoked_at") val revokedAt: String? = null,
    @SerialName("revoke_reason") val revokeReason: String? = null,
)

@Serializable
data class PolicySnapshotDto(
    @SerialName("policy_type") val policyType: String,
    @SerialName("scope_key") val scopeKey: String,
    @SerialName("version_ids") val versionIds: List<String>,
    @SerialName("version_stamp") val versionStamp: String,
    val values: JsonObject,
    @SerialName("valid_until") val validUntil: String,
)

@Serializable
data class SyncData(
    val jobs: List<JobDto> = emptyList(),
    val machines: List<MachineDto> = emptyList(),
    val sites: List<JobSiteDto> = emptyList(),
    val customers: List<CustomerDto> = emptyList(),
    val contracts: List<ContractDto> = emptyList(),
    val staff: List<StaffDto> = emptyList(),
)

@Serializable
data class BootstrapDto(
    @SerialName("protocol_version") val protocolVersion: Int = 1,
    @SerialName("server_time") val serverTime: String,
    val cursor: Long,
    @SerialName("device_session") val deviceSession: DeviceSessionDto,
    val data: SyncData,
    @SerialName("policy_snapshots") val policySnapshots: List<PolicySnapshotDto>,
)

@Serializable
data class ChangesDto(
    @SerialName("protocol_version") val protocolVersion: Int = 1,
    @SerialName("server_time") val serverTime: String,
    val cursor: Long,
    @SerialName("has_more") val hasMore: Boolean,
    val data: SyncData,
    @SerialName("policy_snapshots") val policySnapshots: List<PolicySnapshotDto>,
)

@Serializable
data class OperationIn(
    val id: String,
    @SerialName("op_type") val opType: String,
    @SerialName("created_at_device") val createdAtDevice: String,
    @SerialName("depends_on") val dependsOn: List<String> = emptyList(),
    val payload: JsonObject,
)

@Serializable
data class PushIn(
    @SerialName("device_now") val deviceNow: String,
    val operations: List<OperationIn>,
)

@Serializable
data class OperationResultDto(
    val id: String,
    val status: String,
    val result: JsonObject = JsonObject(emptyMap()),
    val error: JsonObject? = null,
)

@Serializable
data class PushResultDto(
    @SerialName("protocol_version") val protocolVersion: Int = 1,
    @SerialName("server_time") val serverTime: String,
    @SerialName("clock_offset_s") val clockOffsetS: Double,
    @SerialName("clock_skew_alert") val clockSkewAlert: Boolean,
    val results: List<OperationResultDto>,
)

@Serializable
data class BlobStartIn(
    val sha256: String,
    @SerialName("size_bytes") val sizeBytes: Long,
    val purpose: String,
)

@Serializable
data class BlobSessionDto(
    val id: String,
    @SerialName("chunk_size") val chunkSize: Int,
    @SerialName("total_chunks") val totalChunks: Int,
    @SerialName("received_chunks") val receivedChunks: List<Int>,
    val status: String,
    @SerialName("attachment_id") val attachmentId: String? = null,
    @SerialName("expires_at") val expiresAt: String,
)

object OpTypes {
    const val METER_CAPTURE = "METER_CAPTURE"
    const val JOB_ACTIVITY = "JOB_ACTIVITY"
    const val JOB_ACKNOWLEDGEMENT = "JOB_ACKNOWLEDGEMENT"
    const val JOB_TRANSITION = "JOB_TRANSITION"
}

object BlobPurpose {
    const val METER_PHOTO = "METER_PHOTO"
    const val SIGNATURE = "SIGNATURE"
}

object SyncErrorCodes {
    const val DEVICE_REVOKED = "DEVICE_REVOKED"
    const val WIPE_LOCAL_DATA = "WIPE_LOCAL_DATA"
    const val CHECKSUM_MISMATCH = "CHECKSUM_MISMATCH"
    const val UPLOAD_EXPIRED = "UPLOAD_EXPIRED"
    const val UPLOAD_INCOMPLETE = "UPLOAD_INCOMPLETE"
    const val BATCH_TOO_LARGE = "BATCH_TOO_LARGE"
    const val DEVICE_NOT_REGISTERED = "DEVICE_NOT_REGISTERED"
}
