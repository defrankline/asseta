package com.asseta.core.sync

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import kotlinx.serialization.json.putJsonObject
import mockwebserver3.Dispatcher
import mockwebserver3.MockResponse
import mockwebserver3.RecordedRequest
import java.security.MessageDigest
import java.time.Instant
import java.util.UUID

/**
 * In-memory emulation of the backend sync semantics (backend/src/asseta/modules/sync): idempotent op store
 * (DUPLICATE replays the stored outcome), DEFERRED for unmet dependencies, QUARANTINED while read-only,
 * resumable SHA-256-verified blob sessions and DEVICE_REVOKED. Field finance (Gate 5): expense categories, cash
 * custody and the EXPENSE_CAPTURE snapshot in bootstrap/changes; EXPENSE receipts by blob upload id (DEFERRED
 * `ATTACHMENT_PENDING` while the upload is open, REJECTED `RECEIPT_NOT_FOUND` when unknown). Knobs inject failures.
 */
class FakeSyncServer(private val now: () -> Instant) : Dispatcher() {
    data class StoredOp(val payload: JsonObject, var status: String, var result: JsonObject)
    class BlobSession(val id: String, val sha: String, val size: Int, val chunkSize: Int) {
        val chunks = sortedMapOf<Int, ByteArray>()
        var attachmentId: String? = null
    }

    val jobId = "11111111-1111-4111-8111-111111111111"
    val machineId = "22222222-2222-4222-8222-222222222222"
    val tenantVersionId = "33333333-3333-4333-8333-333333333333"
    val contractId = "55555555-5555-4555-8555-555555555555"
    val customerId = "66666666-6666-4666-8666-666666666666"
    val categoryId = "77777777-7777-4777-8777-777777777777"
    val staffId = "88888888-8888-4888-8888-888888888888"

    @Volatile var revoked = false
    @Volatile var readOnly = false
    @Volatile var snapshotValidHours = 24L
    @Volatile var openingMode = "AUTOMATIC"
    @Volatile var closingMode = "MANUAL"
    var chunkSize = 4
    var cursor = 10L
    var failChunkOnce: Int? = null
    var checksumMismatchOnce = false
    /** Errors (HTTP status, error code) returned by the next `POST /sync/blobs` calls, one per call. */
    val startBlobErrors = ArrayDeque<Pair<Int, String>>()
    var failNextPushAfterApply = false
    val deferOnce = mutableSetOf<String>()
    /** Optional per-op override: returns (status, result) or null for the default behaviour. */
    var handler: (op: JsonObject) -> Pair<String, JsonObject>? = { null }
    var changesJobs: List<JsonObject> = emptyList()

    /** Jobs of the next bootstrap (null: the default approved job); e.g. another user's own assignments. */
    @Volatile var bootstrapJobs: List<JsonObject>? = null

    /** `Authorization` header of every push, in order (whose token sent which batch). */
    val pushAuthorizations = mutableListOf<String?>()
    /** Advertised protocol capabilities (null: an older server that sends none). */
    @Volatile var capabilities: List<String>? = listOf("SUPERVISOR_INBOX_V1", "OP_METER_RESET_REQUEST", "OP_JOB_REQUEST")

    /** Supervisor inbox lists sent with the next bootstrap/changes (`my_expenses` -> rows); empty: not sent. */
    var inbox: Map<String, List<JsonObject>> = emptyMap()

    /** Meter reset requests received (payload by server id), resolved like the server's MeterResetOp. */
    val resets = linkedMapOf<String, JsonObject>()
    var changesCategories: List<JsonObject> = emptyList()
    var changesCustomers: List<JsonObject> = emptyList()
    @Volatile var custodyOutstanding = "500000.0000"
    @Volatile var custodyCurrency = "TZS"
    @Volatile var sendCustody = true
    @Volatile var sendExpensePolicy = true
    var expensePolicy: JsonObject = buildJsonObject {
        put("receipt_required_above", "100.00"); put("gps_required", true); put("gps_max_accuracy_m", 50.0)
        put("auto_approve_limit", "500.00")
    }
    var deferReceiptOnce = false
    /** Business records by client id (the server returns the existing record for a known client id). */
    val financeByClient = linkedMapOf<String, JsonObject>()

    val stored = linkedMapOf<String, StoredOp>()
    val applied = mutableListOf<String>()
    val pushedBatches = mutableListOf<List<String>>()
    val chunkPuts = mutableListOf<Pair<String, Int>>()
    val blobs = mutableMapOf<String, BlobSession>()
    private val attachments = mutableMapOf<String, String>() // sha -> attachment id
    val requests = mutableListOf<String>()
    val deviceHeaders = mutableListOf<String?>()

    override fun dispatch(request: RecordedRequest): MockResponse = synchronized(this) {
        val path = request.url.encodedPath
        requests += "${request.method} $path${request.url.query?.let { "?$it" } ?: ""}"
        if (path.startsWith("/api/v1/sync/")) deviceHeaders += request.headers["X-Device-Id"]
        if (revoked) return error(403, "DEVICE_REVOKED", "This device was revoked", issue = "WIPE_LOCAL_DATA")
        val body = request.body?.toByteArray() ?: ByteArray(0)
        when {
            request.method == "POST" && path == "/api/v1/sync/devices" -> register(Json.parseToJsonElement(body.decodeToString()).jsonObject)
            path == "/api/v1/sync/bootstrap" -> ok(bootstrap())
            path == "/api/v1/sync/changes" -> ok(changes())
            path == "/api/v1/sync/push" -> pushAuthorizations.add(request.headers["Authorization"]).let { push(Json.parseToJsonElement(body.decodeToString()).jsonObject) }
            request.method == "POST" && path == "/api/v1/sync/blobs" -> startBlob(Json.parseToJsonElement(body.decodeToString()).jsonObject)
            request.method == "PUT" && path.contains("/chunks/") -> putChunk(path, body)
            request.method == "POST" && path.endsWith("/complete") -> complete(path)
            else -> error(404, "NOT_FOUND", "no route $path")
        }
    }

    private fun ok(json: JsonElement, code: Int = 200) = MockResponse(code = code, body = json.toString())

    fun error(code: Int, errorCode: String, message: String, issue: String? = null) = MockResponse(
        code = code,
        body = buildJsonObject {
            putJsonObject("error") {
                put("code", errorCode); put("message", message); put("correlation_id", "cid-1")
                putJsonArray("details") { if (issue != null) add(buildJsonObject { put("field", JsonNull); put("issue", issue) }) }
            }
        }.toString(),
    )

    /** Mirrors the server contract: device_id, platform and app_version are all required (422 otherwise). */
    private fun register(body: JsonObject): MockResponse =
        if (listOf("device_id", "platform", "app_version").all { body[it] is JsonPrimitive }) ok(deviceSession(), 201)
        else error(422, "VALIDATION_FAILED", "Request validation failed")

    private fun deviceSession() = buildJsonObject {
        put("id", "44444444-4444-4444-8444-444444444444"); put("device_id", "dev"); put("platform", "ANDROID")
        put("app_version", "0.1.0"); put("status", "ACTIVE"); put("registered_at", now().toString())
        put("last_sync_at", JsonNull); put("offline_grant_until", now().plusSeconds(72 * 3600).toString())
        put("last_clock_offset_s", JsonNull); put("revoked_at", JsonNull); put("revoke_reason", JsonNull)
    }

    fun job(status: String, version: Long, id: String = jobId) = buildJsonObject {
        put("id", id); put("job_number", "J-0001"); put("contract_id", "55555555-5555-4555-8555-555555555555")
        put("machine_id", machineId); put("job_site_id", JsonNull); put("supervisor_id", JsonNull); put("status", status)
        put("version", version); put("planned_start", "2026-10-21T06:00:00Z"); put("hourly_rate", "120.00")
        put("standby_treatment", "EXCLUDED"); put("currency", "TZS")
    }

    fun category(name: String, active: Boolean, revision: Long, id: String = categoryId) = buildJsonObject {
        put("id", id); put("code", name.uppercase().take(8)); put("name", name); put("is_active", active)
        put("sync_revision", revision); put("version", 1)
    }

    fun customer(active: Boolean, name: String = "Road Builders Ltd") = buildJsonObject {
        put("id", customerId); put("code", "C-01"); put("name", name); put("contact_name", "Ann"); put("contact_phone", JsonNull)
        put("contact_email", JsonNull); put("tax_id", JsonNull); put("payment_terms_days", 30); put("is_active", active)
    }

    private fun contract() = buildJsonObject {
        put("id", contractId); put("contract_number", "CT-01"); put("customer_id", customerId); put("status", "ACTIVE")
    }

    private fun custody() = buildJsonArray {
        if (sendCustody) add(buildJsonObject {
            put("staff_member_id", staffId); put("currency", custodyCurrency); put("outstanding", custodyOutstanding)
            put("claimed_unverified_handovers", "0.0000"); put("pending_spending", "0.0000"); put("as_of", now().toString())
        })
    }

    private fun data(jobs: List<JsonObject>, categories: List<JsonObject>, customers: List<JsonObject>) = buildJsonObject {
        put("jobs", JsonArray(jobs))
        putJsonArray("machines") {
            add(buildJsonObject {
                put("id", machineId); put("asset_code", "EX-01"); put("name", "Excavator 01")
                put("meter_decimal_places", 1); put("status", "ACTIVE"); put("version", 1)
            })
        }
        putJsonArray("sites") {}; put("customers", JsonArray(customers)); putJsonArray("staff") {}
        put("contracts", JsonArray(if (customers.isEmpty()) emptyList() else listOf(contract())))
        put("expense_categories", JsonArray(categories)); put("cash_custody", custody())
        inbox.forEach { (key, rows) -> put(key, JsonArray(rows)) }
    }

    private fun snapshots() = buildJsonArray {
        add(buildJsonObject {
            put("policy_type", "METER_CAPTURE"); put("scope_key", "tenant")
            putJsonArray("version_ids") { add(JsonPrimitive(tenantVersionId)) }
            put("version_stamp", "v1")
            putJsonObject("values") {
                put("opening_mode", openingMode); put("closing_mode", closingMode); put("manual_photo_required", false)
                put("min_ocr_confidence", 0.85); put("max_recapture_attempts", 2); put("manual_correction_requires_review", true)
                put("gps_enforcement", "SOFT"); put("gps_max_accuracy_m", 50.0); put("gps_max_age_seconds", 120)
            }
            put("valid_until", now().plusSeconds(snapshotValidHours * 3600).toString())
        })
        if (sendExpensePolicy) add(buildJsonObject {
            put("policy_type", "EXPENSE_CAPTURE"); put("scope_key", "tenant")
            putJsonArray("version_ids") { add(JsonPrimitive(tenantVersionId)) }
            put("version_stamp", "e1"); put("values", expensePolicy)
            put("valid_until", now().plusSeconds(snapshotValidHours * 3600).toString())
        })
    }

    private fun bootstrap() = buildJsonObject {
        put("protocol_version", 1); put("server_time", now().toString()); put("cursor", cursor)
        capabilities?.let { c -> put("capabilities", JsonArray(c.map { JsonPrimitive(it) })) }
        put("device_session", deviceSession()); put("data", data(bootstrapJobs ?: listOf(job("APPROVED", 1)), listOf(category("Fuel & oil", true, 5)), listOf(customer(true))))
        put("policy_snapshots", snapshots())
    }

    private fun changes() = buildJsonObject {
        put("protocol_version", 1); put("server_time", now().toString()); put("cursor", cursor); put("has_more", false)
        capabilities?.let { c -> put("capabilities", JsonArray(c.map { JsonPrimitive(it) })) }
        put("data", data(changesJobs, changesCategories, changesCustomers)); put("policy_snapshots", snapshots())
    }

    private fun push(body: JsonObject): MockResponse {
        val ops = body["operations"]!!.jsonArray.map { it.jsonObject }
        require(body["device_now"] != null)
        pushedBatches += ops.map { it.str("id") }
        val results = ops.map { one(it) }
        if (failNextPushAfterApply) { // committed server-side, response lost (gateway error)
            failNextPushAfterApply = false
            return error(503, "UNAVAILABLE", "lost response")
        }
        return ok(buildJsonObject {
            put("protocol_version", 1); put("server_time", now().toString()); put("clock_offset_s", 0.0)
            put("clock_skew_alert", false); put("results", JsonArray(results))
        })
    }

    private fun one(op: JsonObject): JsonObject {
        val id = op.str("id")
        val payload = op["payload"]!!.jsonObject
        stored[id]?.let { existing ->
            if (existing.payload != payload) return result(id, "REJECTED", error = err("OPERATION_ID_REUSED"))
            if (existing.status != "QUARANTINED" || readOnly) {
                return result(id, "DUPLICATE", existing.result, existing.result["error"] as? JsonObject)
            }
        }
        val unmet = op["depends_on"]?.jsonArray.orEmpty().map { it.jsonPrimitive.content }.filter { stored[it]?.status != "ACKED" }
        if (unmet.isNotEmpty() || deferOnce.remove(id)) return result(id, "DEFERRED", error = err("DEPENDENCY_PENDING"))
        if (receiptsPending(op)) return result(id, "DEFERRED", error = err("ATTACHMENT_PENDING")) // not stored
        if (readOnly) {
            val r = buildJsonObject { put("error", err("SUBSCRIPTION_READ_ONLY")) }
            stored[id] = StoredOp(payload, "QUARANTINED", r)
            return result(id, "QUARANTINED", r, err("SUBSCRIPTION_READ_ONLY"))
        }
        val (status, r) = handler(op) ?: default(op)
        stored[id] = StoredOp(payload, status, r)
        if (status == "ACKED") applied += id
        return result(id, status, r, r["error"] as? JsonObject)
    }

    private fun receiptsPending(op: JsonObject): Boolean {
        if (op.str("op_type") != "EXPENSE") return false
        if (deferReceiptOnce) { deferReceiptOnce = false; return true }
        return uploadIds(op["payload"]!!.jsonObject).any { blobs[it] != null && blobs[it]!!.attachmentId == null }
    }

    private fun uploadIds(payload: JsonObject) = payload["receipt_upload_ids"]?.jsonArray.orEmpty().map { it.jsonPrimitive.content }

    /** Mirrors ExpenseService.submit / CashCustodyService: client-id dedupe, receipt resolution and rules. */
    private fun finance(op: JsonObject): Pair<String, JsonObject> {
        val payload = op["payload"]!!.jsonObject
        val clientId = payload.str("client_id")
        financeByClient[clientId]?.let { return "ACKED" to buildJsonObject { put("entity", it) } }
        val receipts = uploadIds(payload).map { blobs[it]?.attachmentId ?: return "REJECTED" to buildJsonObject { put("error", err("RECEIPT_NOT_FOUND")) } }
        val entity = buildJsonObject {
            put("id", UUID.randomUUID().toString()); put("client_id", clientId)
            payload["amount"]?.let { put("amount", it) }; payload["currency"]?.let { put("currency", it) }
            if (op.str("op_type") == "EXPENSE") {
                val amount = payload.str("amount").toBigDecimal()
                if (amount > expensePolicy.str("receipt_required_above").toBigDecimal() && receipts.isEmpty()) {
                    return "REJECTED" to buildJsonObject { put("error", err("RECEIPT_REQUIRED")) }
                }
                val auto = amount <= expensePolicy.str("auto_approve_limit").toBigDecimal()
                put("status", if (auto) "APPROVED" else "PENDING_APPROVAL")
                put("receipt_attachment_ids", JsonArray(receipts.map { JsonPrimitive(it) }))
            }
        }
        financeByClient[clientId] = entity
        return "ACKED" to buildJsonObject { put("entity", entity) }
    }

    private fun default(op: JsonObject): Pair<String, JsonObject> {
        val payload = op["payload"]!!.jsonObject
        if (op.str("op_type") in setOf("EXPENSE", "CASH_COLLECTION", "CASH_HANDOVER", "FUEL_EVENT")) return finance(op)
        if (op.str("op_type") == "METER_RESET_REQUEST") {
            val evidence = payload["evidence_upload_id"]?.jsonPrimitive?.content?.let { blobs[it]?.attachmentId }
                ?: return "REJECTED" to buildJsonObject { put("error", err("ATTACHMENT_NOT_FOUND")) }
            val id = UUID.randomUUID().toString()
            resets[id] = payload
            return "ACKED" to buildJsonObject {
                putJsonObject("entity") { put("id", id); put("status", "PENDING"); put("evidence_attachment_id", evidence) }
            }
        }
        if (op.str("op_type") == "METER_CAPTURE" && payload.str("capture_mode") == "AUTOMATIC" &&
            payload["photo_attachment_id"] == null
        ) {
            return "REJECTED" to buildJsonObject { put("error", err("PHOTO_MISSING")) }
        }
        return "ACKED" to buildJsonObject { putJsonObject("entity") { put("id", op.str("id")); put("version", 7) } }
    }

    private fun result(id: String, status: String, result: JsonObject = JsonObject(emptyMap()), error: JsonObject? = null) =
        buildJsonObject { put("id", id); put("status", status); put("result", result); put("error", error ?: JsonNull) }

    fun err(code: String) = buildJsonObject { put("code", code); put("message", code.lowercase()) }

    private fun startBlob(body: JsonObject): MockResponse {
        startBlobErrors.removeFirstOrNull()?.let { (status, code) -> return error(status, code, code.lowercase()) }
        val sha = body.str("sha256")
        val size = body["size_bytes"]!!.jsonPrimitive.content.toInt()
        val session = BlobSession(UUID.randomUUID().toString(), sha, size, chunkSize)
        attachments[sha]?.let { session.attachmentId = it }
        blobs[session.id] = session
        return ok(blobDto(session), 201)
    }

    private fun putChunk(path: String, bytes: ByteArray): MockResponse {
        val parts = path.split("/")
        val session = blobs[parts[parts.size - 3]] ?: return error(404, "NOT_FOUND", "no session")
        val index = parts.last().toInt()
        chunkPuts += session.id to index
        if (failChunkOnce == index) { failChunkOnce = null; return error(503, "UNAVAILABLE", "store down") }
        session.chunks.putIfAbsent(index, bytes)
        return ok(blobDto(session))
    }

    private fun complete(path: String): MockResponse {
        val session = blobs[path.split("/").let { it[it.size - 2] }] ?: return error(404, "NOT_FOUND", "no session")
        if (session.attachmentId != null) return ok(blobDto(session))
        val total = (session.size + session.chunkSize - 1) / session.chunkSize
        if (session.chunks.keys.toList() != (0 until total).toList()) return error(409, "UPLOAD_INCOMPLETE", "incomplete")
        val data = session.chunks.values.fold(ByteArray(0)) { acc, b -> acc + b }
        if (checksumMismatchOnce || sha(data) != session.sha) {
            checksumMismatchOnce = false
            session.chunks.clear()
            return error(400, "CHECKSUM_MISMATCH", "Checksum mismatch; upload restarted")
        }
        session.attachmentId = UUID.randomUUID().toString().also { attachments[session.sha] = it }
        return ok(blobDto(session))
    }

    private fun blobDto(s: BlobSession) = buildJsonObject {
        put("id", s.id); put("chunk_size", s.chunkSize); put("total_chunks", (s.size + s.chunkSize - 1) / s.chunkSize)
        putJsonArray("received_chunks") { s.chunks.keys.forEach { add(JsonPrimitive(it)) } }
        put("status", if (s.attachmentId != null) "COMPLETE" else "OPEN")
        put("attachment_id", s.attachmentId?.let { JsonPrimitive(it) } ?: JsonNull)
        put("expires_at", now().plusSeconds(3600).toString())
    }

    private fun JsonObject.str(key: String) = this[key]!!.jsonPrimitive.content

    private fun sha(b: ByteArray) = MessageDigest.getInstance("SHA-256").digest(b).joinToString("") { "%02x".format(it) }
}
