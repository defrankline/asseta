package com.asseta.core.sync

import com.asseta.core.domain.accountability.FieldAccess
import com.asseta.core.model.ClientOperationStatus.ACKED
import com.asseta.core.model.ClientOperationStatus.CONFLICT
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.sync.AccountabilityOps
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.network.NetworkFactory
import com.asseta.core.sync.data.FieldAccountabilityData
import com.asseta.core.sync.data.FieldOps
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.sync.usecase.AccountabilityCapture
import com.asseta.core.sync.usecase.FinanceResult
import com.asseta.core.sync.usecase.RetentionRequest
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.util.UUID

/** "Ask to keep cash" through the outbox (CASH_RETENTION_REQUEST, DEC-030 G3) and the capability switch (G1). */
@RunWith(RobolectricTestRunner::class)
class RetentionSyncTest : SyncTestBase() {
    private lateinit var accountability: AccountabilityCapture
    private val retentionId = UUID.randomUUID().toString()

    @Before
    fun setUp() {
        val outbox = FieldOutbox({ db }, json, clock, { account })
        accountability = AccountabilityCapture({ db }, repository, financeRepository, outbox, files, json)
        fake.capabilities = listOf(SyncCapabilities.SUPERVISOR_INBOX_V1, SyncCapabilities.OP_CASH_RETENTION_REQUEST)
    }

    private fun synced() = runBlocking { assertTrue(engine().sync(tenant) is SyncReport.Success) }

    private fun request(clientId: String = UUID.randomUUID().toString(), amount: String = "20000") =
        RetentionRequest(tenant, clientId, amount, "tzs", "  Fuel for tomorrow ", null, staffMemberId = null)

    private fun data(online: Boolean) = FieldAccountabilityData(
        api = {
            val client = NetworkFactory.okHttpClient({ "token" }, { null }, device = { DEVICE })
            NetworkFactory.tenantApi(if (online) server.url("/").toString() else "http://127.0.0.1:1/", client, allowCleartext = true)
        },
        db = { db }, json = json, account = { account },
    )

    @Test
    fun retentionIsQueuedOnceByClientIdAndAcked() = runBlocking {
        synced()
        val clientId = UUID.randomUUID().toString()
        val first = accountability.retention(request(clientId))
        assertTrue("expected Saved but was $first", first is FinanceResult.Saved)
        assertEquals(FinanceResult.AlreadySaved, accountability.retention(request(clientId)))
        val opId = (first as FinanceResult.Saved).operationId
        val op = op(opId)
        assertEquals(AccountabilityOps.CASH_RETENTION_REQUEST, op.opType)
        assertEquals(FieldOps.CASH_RETENTION, op.entityType)
        val payload = json.parseToJsonElement(op.payloadJson).jsonObject
        assertEquals(clientId, payload["client_id"]!!.jsonPrimitive.content)
        assertEquals("TZS", payload["currency"]!!.jsonPrimitive.content)
        assertEquals("Fuel for tomorrow", payload["reason"]!!.jsonPrimitive.content)
        assertFalse(payload.containsKey("staff_member_id") && payload["staff_member_id"]!!.toString() != "null")

        fake.handler = { o ->
            if (o["op_type"]!!.jsonPrimitive.content == AccountabilityOps.CASH_RETENTION_REQUEST) {
                "ACKED" to buildJsonObject { putJsonObject("entity") { put("id", retentionId); put("status", "PENDING") } }
            } else {
                null
            }
        }
        synced()
        assertEquals(ACKED, status(opId))
        // The status screen reads the server id from the acked result, then GET /cash/retentions/{id} (offline here).
        val status = data(online = false).retentionStatus(tenant, clientId)
        assertEquals(retentionId, status.retentionId)
        assertTrue(status.offline)
        assertNull(status.server)
    }

    @Test
    fun retentionConflictKeepsTheCodeForPlainWords() = runBlocking {
        synced()
        val saved = accountability.retention(request()) as FinanceResult.Saved
        fake.handler = { o ->
            if (o["op_type"]!!.jsonPrimitive.content == AccountabilityOps.CASH_RETENTION_REQUEST) {
                "CONFLICT" to buildJsonObject { put("error", fake.err("RETENTION_NOT_ALLOWED")) }
            } else {
                null
            }
        }
        engine().sync(tenant)
        val op = op(saved.operationId)
        assertEquals(CONFLICT, op.status)
        assertEquals("RETENTION_NOT_ALLOWED", op.errorCode)
        val status = data(online = false).retentionStatus(tenant, op.entityId)
        assertNull(status.retentionId) // never reached the server: nothing to read
    }

    @Test
    fun retentionRulesAndCapability() = runBlocking {
        synced()
        assertTrue(accountability.retention(request(amount = "0")) is FinanceResult.Invalid)
        fake.capabilities = listOf(SyncCapabilities.SUPERVISOR_INBOX_V1)
        synced()
        assertTrue(accountability.retention(request()) is FinanceResult.Blocked)
    }

    @Test
    fun customerHoursSwitchedOffHidesItsEntries() = runBlocking {
        fake.capabilities = listOf(SyncCapabilities.SUPERVISOR_INBOX_V1, SyncCapabilities.OP_HOURS_PURCHASE, SyncCapabilities.OP_CASH_RETENTION_REQUEST)
        synced()
        val data = data(online = false)
        val perms = setOf(FieldAccess.HOURS_PURCHASE, FieldAccess.COLLECTION_RECORD)
        assertTrue(data.access(tenant, perms).retentionOffline)
        data.setDisabledCapabilities(tenant, listOf(TenantAccess.CUSTOMER_HOURS))
        val access = data.access(tenant, perms)
        assertEquals(setOf(TenantAccess.CUSTOMER_HOURS), access.disabled)
        assertFalse(access.sellHours)
    }
}
