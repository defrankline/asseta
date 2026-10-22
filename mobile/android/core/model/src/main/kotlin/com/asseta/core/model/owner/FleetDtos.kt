package com.asseta.core.model.owner

import com.asseta.core.model.SerializableUuid
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * `MachineMapDto` (getFleetMap / getMachineStatus): the server's status dimensions are kept as open strings
 * (connectivity, observed engine/motion, reported work status, compliance) so new server values never crash the app;
 * the UI maps known values and shows unknown ones verbatim. Coordinates are the last known position, never "live"
 * unless the server says [isLive].
 */
@Serializable
data class MachineMapDto(
    @SerialName("machine_id") val machineId: SerializableUuid,
    @SerialName("asset_code") val assetCode: String,
    val name: String,
    @SerialName("machine_status") val machineStatus: String,
    val connectivity: String,
    @SerialName("is_live") val isLive: Boolean,
    @SerialName("observed_engine") val observedEngine: String,
    @SerialName("observed_motion") val observedMotion: String,
    @SerialName("reported_work_status") val reportedWorkStatus: String,
    @SerialName("location_compliance") val locationCompliance: String,
    @SerialName("open_alerts") val openAlerts: Int,
    @SerialName("policy_version") val policyVersion: String,
    val latitude: Double? = null,
    val longitude: Double? = null,
    @SerialName("accuracy_m") val accuracyM: Double? = null,
    @SerialName("position_time") val positionTime: String? = null,
    @SerialName("position_quality") val positionQuality: String? = null,
    @SerialName("position_source") val positionSource: String? = null,
    @SerialName("last_message_at") val lastMessageAt: String? = null,
    @SerialName("last_seen_age_seconds") val lastSeenAgeSeconds: Long? = null,
    val operator: String? = null,
    val supervisor: String? = null,
    @SerialName("tracker_id") val trackerId: SerializableUuid? = null,
    @SerialName("tracker_state") val trackerState: String? = null,
) {
    val hasPosition: Boolean get() = latitude != null && longitude != null
}

/** `HistoryDto` (getMachineHistory): bounded track for a time range (server caps the range at 31 days). */
@Serializable
data class HistoryDto(
    @SerialName("machine_id") val machineId: SerializableUuid,
    val points: List<TrackPointDto> = emptyList(),
    val stops: List<StopDto> = emptyList(),
    @SerialName("site_visits") val siteVisits: List<SiteVisitDto> = emptyList(),
    @SerialName("distance_km") val distanceKm: Double,
    val truncated: Boolean,
    @SerialName("policy_version") val policyVersion: String,
)

@Serializable
data class TrackPointDto(
    @SerialName("event_time") val eventTime: String,
    @SerialName("received_at") val receivedAt: String,
    val latitude: Double,
    val longitude: Double,
    val quality: String,
    @SerialName("is_late") val isLate: Boolean,
    @SerialName("accuracy_m") val accuracyM: Double? = null,
    @SerialName("heading_deg") val headingDeg: Double? = null,
    @SerialName("speed_kmh") val speedKmh: Double? = null,
    val ignition: Boolean? = null,
)

@Serializable
data class StopDto(
    val start: String,
    val end: String,
    val latitude: Double,
    val longitude: Double,
    @SerialName("duration_seconds") val durationSeconds: Long,
)

@Serializable
data class SiteVisitDto(
    @SerialName("geofence_id") val geofenceId: SerializableUuid,
    @SerialName("geofence_name") val geofenceName: String,
    @SerialName("entered_at") val enteredAt: String? = null,
    @SerialName("exited_at") val exitedAt: String? = null,
    @SerialName("duration_seconds") val durationSeconds: Long,
)

/** `MachineDto` (getMachine): static register data shown on the machine drilldown. */
@Serializable
data class MachineDto(
    val id: SerializableUuid,
    @SerialName("asset_code") val assetCode: String,
    val name: String,
    val status: String,
    val ownership: String,
    @SerialName("meter_decimal_places") val meterDecimalPlaces: Int,
    val version: Long,
    @SerialName("created_at") val createdAt: String,
    val manufacturer: String? = null,
    val model: String? = null,
    @SerialName("serial_number") val serialNumber: String? = null,
    @SerialName("year_of_manufacture") val yearOfManufacture: Int? = null,
    @SerialName("category_id") val categoryId: SerializableUuid? = null,
    @SerialName("operating_area_id") val operatingAreaId: SerializableUuid? = null,
    @SerialName("capacity_value") val capacityValue: String? = null,
    @SerialName("capacity_unit") val capacityUnit: String? = null,
    @SerialName("deactivated_at") val deactivatedAt: String? = null,
    @SerialName("deactivation_reason") val deactivationReason: String? = null,
)
