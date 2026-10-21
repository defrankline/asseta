package com.asseta.core.database

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

/** Server-owned job cached for offline work; upserted only when the server `version` is not older. */
@Entity(tableName = "job", indices = [Index(value = ["tenant_id", "status"])])
data class JobEntity(
    @PrimaryKey @ColumnInfo(name = "id") val id: String,
    @ColumnInfo(name = "tenant_id") val tenantId: String,
    @ColumnInfo(name = "job_number") val jobNumber: String,
    @ColumnInfo(name = "machine_id") val machineId: String,
    @ColumnInfo(name = "contract_id") val contractId: String,
    @ColumnInfo(name = "job_site_id") val jobSiteId: String?,
    @ColumnInfo(name = "status") val status: String,
    @ColumnInfo(name = "version") val version: Long,
    @ColumnInfo(name = "planned_start") val plannedStart: String,
    @ColumnInfo(name = "planned_end") val plannedEnd: String?,
    @ColumnInfo(name = "standby_treatment") val standbyTreatment: String?,
    /** Contract currency (v3, nullable): the device's hint for the tenant currency of field-finance forms. */
    @ColumnInfo(name = "currency") val currency: String? = null,
)

@Entity(tableName = "machine", indices = [Index(value = ["tenant_id"])])
data class MachineEntity(
    @PrimaryKey @ColumnInfo(name = "id") val id: String,
    @ColumnInfo(name = "tenant_id") val tenantId: String,
    @ColumnInfo(name = "asset_code") val assetCode: String,
    @ColumnInfo(name = "name") val name: String,
    @ColumnInfo(name = "meter_decimal_places") val meterDecimalPlaces: Int,
    @ColumnInfo(name = "status") val status: String,
    @ColumnInfo(name = "version") val version: Long,
)

/** Read-only reference data (sites, customers, contracts, own staff record) kept as the server JSON. */
@Entity(tableName = "reference_record", primaryKeys = ["kind", "id"], indices = [Index(value = ["tenant_id"])])
data class ReferenceRecordEntity(
    @ColumnInfo(name = "kind") val kind: String,
    @ColumnInfo(name = "id") val id: String,
    @ColumnInfo(name = "tenant_id") val tenantId: String,
    @ColumnInfo(name = "title") val title: String,
    @ColumnInfo(name = "json") val json: String,
)

/** Trusted capture-rule snapshot (`policy_snapshots`); the device enforces it offline until `valid_until`. */
@Entity(tableName = "policy_snapshot", primaryKeys = ["tenant_id", "policy_type", "scope_key"])
data class PolicySnapshotEntity(
    @ColumnInfo(name = "tenant_id") val tenantId: String,
    @ColumnInfo(name = "policy_type") val policyType: String,
    @ColumnInfo(name = "scope_key") val scopeKey: String,
    @ColumnInfo(name = "version_ids_json") val versionIdsJson: String,
    @ColumnInfo(name = "version_stamp") val versionStamp: String,
    @ColumnInfo(name = "values_json") val valuesJson: String,
    @ColumnInfo(name = "valid_until") val validUntil: Long,
    @ColumnInfo(name = "received_at") val receivedAt: Long,
)

/** Per-tenant sync bookkeeping: registration, cursor, offline grant, clock anchor and retry streak. */
@Entity(tableName = "sync_state")
data class SyncStateEntity(
    @PrimaryKey @ColumnInfo(name = "tenant_id") val tenantId: String,
    @ColumnInfo(name = "device_session_id") val deviceSessionId: String? = null,
    @ColumnInfo(name = "offline_grant_until") val offlineGrantUntil: Long? = null,
    @ColumnInfo(name = "cursor") val cursor: Long? = null,
    @ColumnInfo(name = "server_time") val serverTime: Long? = null,
    @ColumnInfo(name = "server_time_elapsed") val serverTimeElapsed: Long? = null,
    @ColumnInfo(name = "last_sync_at") val lastSyncAt: Long? = null,
    @ColumnInfo(name = "failure_streak") val failureStreak: Int = 0,
    @ColumnInfo(name = "last_error") val lastError: String? = null,
    @ColumnInfo(name = "clock_offset_s") val clockOffsetS: Double? = null,
    @ColumnInfo(name = "server_clock_alert") val serverClockAlert: Boolean = false,
    @ColumnInfo(name = "max_batch") val maxBatch: Int? = null,
)
