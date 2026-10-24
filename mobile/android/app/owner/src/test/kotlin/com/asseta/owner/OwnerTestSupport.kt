package com.asseta.owner

import com.asseta.core.domain.owner.SnapshotPolicy
import com.asseta.core.network.NetworkFactory
import com.asseta.owner.data.CachedSnapshot
import com.asseta.owner.data.OwnerData
import com.asseta.owner.data.OwnerRepository
import com.asseta.owner.data.SessionEvents
import com.asseta.owner.data.SnapshotStore
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer

const val TENANT = "a3c1d1f2-1111-4222-8333-944455556666"
const val ID1 = "11111111-1111-4111-8111-111111111111"
const val ID2 = "22222222-2222-4222-8222-222222222222"

class MemoryStore(private val policy: SnapshotPolicy = SnapshotPolicy(), private val clock: () -> Long) : SnapshotStore {
    val rows = mutableMapOf<Pair<String, String>, CachedSnapshot>()
    override suspend fun read(tenantId: String, key: String) = rows[tenantId to key]?.takeUnless { policy.isExpired(it.fetchedAtMs, clock()) }
    override suspend fun write(tenantId: String, key: String, payloadJson: String, fetchedAtMs: Long) { rows[tenantId to key] = CachedSnapshot(payloadJson, fetchedAtMs) }
    override suspend fun purgeExpired(nowMs: Long) { rows.entries.removeIf { policy.isExpired(it.value.fetchedAtMs, nowMs) } }
    override suspend fun wipeTenant(tenantId: String) { rows.keys.removeIf { it.first == tenantId } }
    override suspend fun keepOnlyTenants(tenantIds: List<String>) { rows.keys.removeIf { it.first !in tenantIds } }
    override suspend fun wipeAll() = rows.clear()
}

class RecordingEvents : SessionEvents {
    val revoked = mutableListOf<String>()
    var ended = 0
    override fun tenantRevoked(tenantId: String) { revoked += tenantId }
    override fun sessionEnded() { ended++ }
}

/** Real Retrofit + OkHttp (with the production interceptors) against MockWebServer. */
class OwnerHarness {
    var now = 1_800_000_000_000L
    val server = MockWebServer().apply { start() }
    val store = MemoryStore { now }
    val events = RecordingEvents()
    val api = NetworkFactory.tenantApi(server.url("/").toString(), NetworkFactory.okHttpClient({ "token" }, { TENANT }), allowCleartext = true)
    val repo = OwnerRepository(api, store, NetworkFactory.json, SnapshotPolicy(), events) { now }
    val data = OwnerData(repo, TENANT) { now }

    fun ok(body: String) = server.enqueue(MockResponse.Builder().code(200).body(body).build())

    fun error(code: Int, errorCode: String, message: String = "refused") = server.enqueue(
        MockResponse.Builder().code(code).body("""{"error":{"code":"$errorCode","message":"$message","correlation_id":"cid-$code"}}""").build(),
    )

    /** Simulates losing the network: the next calls fail to connect. */
    fun goOffline() = server.close()

    fun close() {
        runCatching { server.close() }
    }
}

object Samples {
    fun alert(id: String = ID1, status: String = "OPEN") = """{"id":"$id","alert_type":"TRACKER_OFFLINE","severity":"WARNING","status":"$status",
        "title":"Tracker offline","event_time":"2026-10-22T08:00:00Z","created_at":"2026-10-22T08:00:01Z","evidence":{},"machine_id":null,
        "tracker_id":null,"acknowledged_at":null,"resolved_at":null,"resolution_note":null,"policy_version":null}"""

    fun page(vararg items: String) = """{"items":[${items.joinToString(",")}],"total":${items.size},"page":1,"page_size":50}"""

    fun approval(id: String = ID1, status: String = "PENDING") = """{"id":"$id","subject_type":"EXPENSE","subject_id":"$ID2","amount":"150000.0000",
        "currency":"TZS","reason":"Fuel above limit","status":"$status","requested_at":"2026-10-22T08:00:00Z","requested_by":null,
        "decided_at":null,"decided_by":null,"decision_note":null,"policy_version":"v1"}"""

    fun machine(connectivity: String = "LIVE", live: Boolean = true) = """{"machine_id":"$ID1","asset_code":"EX-01","name":"Excavator",
        "machine_status":"ACTIVE","connectivity":"$connectivity","is_live":$live,"observed_engine":"ON","observed_motion":"MOVING",
        "reported_work_status":"WORKING","location_compliance":"COMPLIANT","open_alerts":1,"policy_version":"p","latitude":-6.8,
        "longitude":39.28,"last_seen_age_seconds":30,"tracker_id":null}"""

    const val JOB_SUMMARY = """{"job":{"id":"$ID1","job_number":"J-1001","status":"COMPLETED","machine_id":"$ID2","contract_id":"$ID2","currency":"TZS",
        "hourly_rate":"95000.0000","minimum_hours":"0.0000","mobilization_fee":"0.0000","discount_percent":"0.0000","tax_rate_percent":"15.0000",
        "rate_source":"CONTRACT","standby_treatment":"EXCLUDED","planned_start":"2026-10-21T06:00:00Z","version":3},
        "nonbillable_hours":"0.0000","billing_ready":false,"open_exceptions":2,"blocking_exceptions":1,"policy_version":"p"}"""

    fun expense(id: String = ID1, status: String = "PENDING_APPROVAL", currency: String = "TZS", amount: String = "150000.0000", supplier: String? = "Tyre shop") =
        """{"id":"$id","amount":"$amount","currency":"$currency","description":"Tyre repair","status":"$status","incurred_at":"2026-10-21T09:00:00Z",
        "submitted_at":"2026-10-21T09:05:00Z","paid_from":"CASH_CUSTODY","supplier":${supplier?.let { "\"$it\"" } ?: "null"},"job_id":"$ID1",
        "decision_note":null,"receipt_required":true}"""

    fun fuel(id: String = ID1, supplier: String? = "Puma") = """{"id":"$id","event_type":"PURCHASE","litres":"40.500","unit_price":"3200.0000",
        "attributed_cost":"129600.0000","currency":"TZS","job_id":"$ID1","supplier":${supplier?.let { "\"$it\"" } ?: "null"},
        "occurred_at":"2026-10-21T07:00:00Z","source":"MOBILE"}"""

    fun reset(id: String = ID1, status: String = "PENDING") = """{"id":"$id","machine_id":"$ID2","old_reading":"1200.00","new_reading":"0.00",
        "effective_at":"2026-10-21T07:00:00Z","reason":"Meter replaced after damage","evidence_attachment_id":null,"status":"$status",
        "requested_by":null,"decided_at":null}"""

    const val OVERVIEW = """{"tenant_id":"$TENANT","as_of":"2026-10-22T08:00:00Z","timezone":"Africa/Dar_es_Salaam","fleet":null,"work":
        {"jobs_by_status":{"IN_PROGRESS":2},"pending_approvals":1,"latest_source_at":"2026-10-22T07:00:00Z"},"money":null,"risk":null}"""

    fun notification(id: String, read: Boolean = false) = """{"id":"$id","type":"APPROVAL_REQUESTED","category":"ACTION","severity":"INFO",
        "priority":"NORMAL","title":"Expense approval requested","body":"TZS 150000","created_at":"2026-10-22T08:00:00Z",
        "read_at":${if (read) "\"2026-10-22T09:00:00Z\"" else "null"},"target":{"entity":"approval","id":"$ID2","path":"/tenant/approvals"},
        "tenant_id":"$TENANT","data":{}}"""

    fun routing(category: String, severity: String, push: Boolean, mandatoryPush: Boolean = false) = """{"category":"$category",
        "severity":"$severity","push":$push,"email":true,"source":"USER","mandatory_channels":[${if (mandatoryPush) "\"PUSH\"" else ""}],"in_app":true}"""
}
