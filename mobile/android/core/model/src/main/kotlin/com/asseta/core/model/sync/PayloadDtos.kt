package com.asseta.core.model.sync

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Outbox operation payloads. Shapes follow contracts/openapi.json `MeterCaptureIn` and `GpsIn`.
 * Readings are decimal strings (never binary floats). Timestamps are ISO-8601 UTC device time.
 */
@Serializable
data class GpsIn(
    val status: String,
    val latitude: Double? = null,
    val longitude: Double? = null,
    @SerialName("accuracy_m") val accuracyM: Double? = null,
    @SerialName("captured_at") val capturedAt: String? = null,
    val provider: String? = null,
)

@Serializable
data class MeterCaptureIn(
    val id: String,
    /** Always DAILY (the only kind since ADR-008). */
    val kind: String,
    @SerialName("capture_mode") val captureMode: String,
    val reading: String,
    @SerialName("ocr_raw_text") val ocrRawText: String? = null,
    @SerialName("ocr_value") val ocrValue: String? = null,
    @SerialName("ocr_confidence") val ocrConfidence: Double? = null,
    @SerialName("ocr_engine") val ocrEngine: String? = null,
    @SerialName("photo_attachment_id") val photoAttachmentId: String? = null,
    val gps: GpsIn,
    @SerialName("device_id") val deviceId: String,
    @SerialName("captured_at") val capturedAt: String,
    @SerialName("policy_version_ids") val policyVersionIds: List<String> = emptyList(),
    /** The machine read (the server requires it). */
    @SerialName("machine_id") val machineId: String? = null,
    /** The phone geocoder's area label of the reading's location ("Mbezi Beach, Kinondoni, Dar es Salaam"); max 200. */
    @SerialName("place_name") val placeName: String? = null,
)
