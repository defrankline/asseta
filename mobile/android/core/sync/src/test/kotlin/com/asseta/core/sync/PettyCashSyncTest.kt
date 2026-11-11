package com.asseta.core.sync

import com.asseta.core.domain.accountability.RemittanceMethod
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.finance.AdvanceChoice
import com.asseta.core.domain.finance.FundChoice
import com.asseta.core.domain.finance.PaidFrom
import com.asseta.core.domain.finance.PettyCashMessages
import com.asseta.core.model.ClientOperationStatus.ACKED
import com.asseta.core.model.ClientOperationStatus.CONFLICT
import com.asseta.core.model.sync.BlobPurpose
import com.asseta.core.model.sync.PettyCashOps
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.data.PettyCashRepository
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.sync.usecase.ExpenseRequest
import com.asseta.core.sync.usecase.FinanceResult
import com.asseta.core.sync.usecase.PettyCashCapture
import com.asseta.core.sync.usecase.PettyCashCountRequest
import com.asseta.core.sync.usecase.PettyCashEntities
import com.asseta.core.sync.usecase.PettyCashReturnRequest
import com.asseta.core.sync.usecase.PettyCashTopUpRequest
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
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
import java.math.BigDecimal
import java.time.Instant
import java.util.UUID

/** DEC-033 petty cash on the phone: the replaced snapshot, the offline operations and an expense paid from a fund. */
@RunWith(RobolectricTestRunner::class)
class PettyCashSyncTest : SyncTestBase() {
    private lateinit var petty: PettyCashCapture
    private lateinit var pettyRepo: PettyCashRepository
    private val fundId = "f0000000-0000-4000-8000-000000000001"
    private val movementId = "a0000000-0000-4000-8000-000000000002"
    private val changeId = "c0000000-0000-4000-8000-000000000003"

    @Before
    fun setUp() {
        val outbox = FieldOutbox({ db }, json, clock, { account })
        petty = PettyCashCapture({ db }, outbox, files, json)
        pettyRepo = PettyCashRepository({ db }, repository, json)
        fake.capabilities = listOf(SyncCapabilities.SUPERVISOR_INBOX_V1, SyncCapabilities.OP_PETTY_CASH)
        fake.inbox = snapshot()
    }

    private fun synced() = runBlocking { assertTrue(engine().sync(tenant) is SyncReport.Success) }

    private fun fund(id: String = fundId, available: String = "40000") = buildJsonObject {
        put("id", id); put("code", "PC-1"); put("name", "Site box"); put("holder_staff_id", fake.staffId); put("currency", "TZS")
        put("approved_limit", "100000"); put("is_active", true)
        putJsonObject("balance") {
            put("fund_id", id); put("fund_code", "PC-1"); put("fund_name", "Site box"); put("currency", "TZS"); put("holder_staff_id", fake.staffId)
            put("is_active", true); put("approved_limit", "100000"); put("balance", "60000"); put("available_to_spend", available)
            put("below_low_balance", false); put("pending_spending", "20000"); put("awaiting_acknowledgement", "0"); put("returns_claimed", "0")
            put("as_of", "2026-10-21T08:00:00Z")
        }
    }

    private fun movement() = buildJsonObject {
        put("id", movementId); put("number", "PC-0001"); put("fund_id", fundId); put("kind", "TOP_UP"); put("status", "ISSUED")
        put("amount", "30000"); put("currency", "TZS"); put("created_at", "2026-10-20T08:00:00Z"); put("issued_at", "2026-10-20T09:00:00Z")
    }

    private fun change() = buildJsonObject {
        put("id", changeId); put("fund_id", fundId); put("from_staff_id", UUID.randomUUID().toString()); put("to_staff_id", fake.staffId)
        put("status", "PENDING"); put("requested_at", "2026-10-20T08:00:00Z"); put("count_id", UUID.randomUUID().toString())
    }

    private fun snapshot(funds: List<JsonObject> = listOf(fund())) = mapOf(
        "petty_cash_funds" to funds,
        "petty_cash_awaiting" to listOf(movement()),
        "petty_cash_holder_changes" to listOf(change()),
    )

    private fun payload(opId: String): JsonObject = json.parseToJsonElement(op(opId).payloadJson).jsonObject

    private fun saved(r: FinanceResult): FinanceResult.Saved {
        assertTrue("expected Saved but was $r", r is FinanceResult.Saved)
        return r as FinanceResult.Saved
    }

    @Test
    fun snapshotIsReplacedOnEveryPullAndClearedWithoutTheCapability() = runBlocking {
        synced()
        var view = pettyRepo.observe(tenant).first()
        assertEquals(listOf(fundId), view.funds.map { it.id })
        assertEquals("40000", view.funds.single().balance!!.availableToSpend)
        assertEquals(2, view.waitingCount)

        fake.inbox = snapshot(funds = emptyList()) - "petty_cash_awaiting"
        synced()
        view = pettyRepo.observe(tenant).first()
        assertTrue(view.funds.isEmpty())
        assertTrue(view.awaiting.isEmpty())

        fake.inbox = snapshot()
        fake.capabilities = listOf(SyncCapabilities.SUPERVISOR_INBOX_V1)
        synced()
        view = pettyRepo.observe(tenant).first()
        assertTrue(view.funds.isEmpty() && view.holderChanges.isEmpty())
    }

    @Test
    fun acknowledgementIsQueuedOnceAndLeavesTheWaitingList() = runBlocking {
        synced()
        assertTrue(petty.acknowledge(tenant, movementId, true, "-1", "") is FinanceResult.Invalid)
        assertTrue(petty.acknowledge(tenant, movementId, false, "", " ") is FinanceResult.Invalid) // a dispute needs a reason
        val s = saved(petty.acknowledge(tenant, movementId, true, "29000", " short by 1000 "))
        assertEquals(FinanceResult.AlreadySaved, petty.acknowledge(tenant, movementId, true, "29000", ""))
        assertTrue(petty.answered(tenant, PettyCashEntities.ACK, movementId))
        val p = payload(s.operationId)
        assertEquals(PettyCashOps.ACKNOWLEDGEMENT, op(s.operationId).opType)
        assertEquals(movementId, p["movement_id"]!!.jsonPrimitive.content)
        assertEquals("29000", p["amount_received"]!!.jsonPrimitive.content)
        assertEquals("short by 1000", p["note"]!!.jsonPrimitive.content)
        val view = pettyRepo.observe(tenant).first()
        assertTrue(view.awaiting.isEmpty())
        assertEquals(PettyCashOps.ACKNOWLEDGEMENT, view.records.single().opType)

        fake.handler = { o -> if (o["op_type"]!!.jsonPrimitive.content == PettyCashOps.ACKNOWLEDGEMENT) "ACKED" to buildJsonObject {} else null }
        synced()
        assertEquals(ACKED, status(s.operationId))
    }

    @Test
    fun disputeCarriesNoAmountAndARefusedAnswerComesBack() = runBlocking {
        synced()
        val s = saved(petty.acknowledge(tenant, movementId, false, "30000", "Envelope was empty"))
        assertFalse(payload(s.operationId).containsKey("amount_received"))
        fake.handler = { o ->
            if (o["op_type"]!!.jsonPrimitive.content == PettyCashOps.ACKNOWLEDGEMENT) "CONFLICT" to buildJsonObject { put("error", fake.err("PETTY_CASH_ALREADY_ACKNOWLEDGED")) } else null
        }
        engine().sync(tenant)
        assertEquals(CONFLICT, status(s.operationId))
        assertEquals(listOf(movementId), pettyRepo.observe(tenant).first().awaiting.map { it.id })
    }

    @Test
    fun topUpReturnCountHolderChangeAndAdvancePayloads() = runBlocking {
        synced()
        val clientId = UUID.randomUUID().toString()
        // Above what brings the fund to its limit (100000 - 60000): the reason is required.
        assertTrue(petty.topUp(PettyCashTopUpRequest(tenant, clientId, fundId, "50000", "", "", BigDecimal("40000"))) is FinanceResult.Invalid)
        val top = saved(petty.topUp(PettyCashTopUpRequest(tenant, clientId, fundId, "", "", "", BigDecimal("40000"))))
        val tp = payload(top.operationId)
        assertEquals(clientId, tp["client_id"]!!.jsonPrimitive.content)
        assertEquals(fundId, tp["fund_id"]!!.jsonPrimitive.content)
        assertFalse(tp.containsKey("amount")) // the server's imprest suggestion

        val ret = PettyCashReturnRequest(tenant, UUID.randomUUID().toString(), fundId, "40000", RemittanceMethod.BANK_DEPOSIT, null, "SLIP-9", "",
            emptyList(), evidenceRequired = true, createdAtMs = clock.now)
        assertEquals(listOf(PettyCashMessages.EVIDENCE), (petty.returnFund(ret) as FinanceResult.Invalid).messages)
        val r = saved(petty.returnFund(ret.copy(evidenceJpegs = listOf(photo))))
        val rp = payload(r.operationId)
        assertEquals("BANK_DEPOSIT", rp["method"]!!.jsonPrimitive.content)
        assertEquals("SLIP-9", rp["reference"]!!.jsonPrimitive.content)
        assertTrue(rp["evidence_upload_ids"]!!.jsonArray.isEmpty())
        val attachment = db.evidenceDao().attachment(db.clientOperationDao().attachmentsOf(r.operationId).single())!!
        assertEquals(BlobPurpose.PETTY_CASH_EVIDENCE, attachment.purpose)

        val witness = UUID.randomUUID().toString()
        val c = saved(petty.count(PettyCashCountRequest(tenant, UUID.randomUUID().toString(), fundId, "39500", witness, "", emptyList(), clock.now)))
        assertEquals("39500", payload(c.operationId)["counted_amount"]!!.jsonPrimitive.content)
        assertEquals(witness, payload(c.operationId)["witness_user_id"]!!.jsonPrimitive.content)

        assertTrue(petty.holderChange(tenant, changeId, false, "no") is FinanceResult.Invalid)
        val h = saved(petty.holderChange(tenant, changeId, true, ""))
        assertEquals(true.toString(), payload(h.operationId)["accept"]!!.jsonPrimitive.content)

        val advanceId = UUID.randomUUID().toString()
        val a = saved(petty.clearAdvance(tenant, advanceId, "1500", ""))
        assertEquals("1500", payload(a.operationId)["change_returned"]!!.jsonPrimitive.content)

        fake.handler = { o -> if (o["op_type"]!!.jsonPrimitive.content in PettyCashOps.ALL) "ACKED" to buildJsonObject {} else null }
        synced()
        listOf(top, c, h, a, r).forEach { assertEquals(ACKED, status(it.operationId)) }
        // The return photo uploaded first and is named by its upload id.
        val session = fake.blobs.values.single { it.attachmentId != null }
        assertEquals(listOf(session.id), payload(r.operationId)["evidence_upload_ids"]!!.jsonArray.map { it.jsonPrimitive.content })
    }

    private fun witness(id: String, name: String) = buildJsonObject { put("user_id", id); put("name", name) }

    @Test
    fun witnessListIsStoredReplacedAndCleared() = runBlocking {
        val asha = "e0000000-0000-4000-8000-000000000001"
        val juma = "e0000000-0000-4000-8000-000000000002"
        fake.capabilities = listOf(SyncCapabilities.SUPERVISOR_INBOX_V1, SyncCapabilities.OP_PETTY_CASH, SyncCapabilities.SYNC_PETTY_CASH_WITNESSES)
        fake.inbox = snapshot() + ("petty_cash_witnesses" to listOf(witness(juma, "Juma"), witness(asha, "asha")))
        synced()
        assertTrue(pettyRepo.witnessesOffline(tenant))
        assertEquals(listOf("asha", "Juma"), pettyRepo.observeWitnesses(tenant).first().map { it.name })

        fake.inbox = snapshot() + ("petty_cash_witnesses" to listOf(witness(juma, "Juma Ali")))
        synced()
        assertEquals(listOf(juma to "Juma Ali"), pettyRepo.observeWitnesses(tenant).first().map { it.userId to it.name })

        fake.inbox = snapshot()
        synced()
        assertTrue(pettyRepo.observeWitnesses(tenant).first().isEmpty())

        fake.inbox = snapshot() + ("petty_cash_witnesses" to listOf(witness(asha, "Asha")))
        synced()
        fake.capabilities = listOf(SyncCapabilities.SUPERVISOR_INBOX_V1)
        synced()
        assertTrue(pettyRepo.observeWitnesses(tenant).first().isEmpty())
        assertFalse(pettyRepo.witnessesOffline(tenant))
    }

    @Test
    fun witnessPickedOfflineIsSentAndADroppedWitnessIsShownAfterSync() = runBlocking {
        val asha = "e0000000-0000-4000-8000-000000000001"
        fake.capabilities = listOf(SyncCapabilities.SUPERVISOR_INBOX_V1, SyncCapabilities.OP_PETTY_CASH, SyncCapabilities.SYNC_PETTY_CASH_WITNESSES)
        fake.inbox = snapshot() + ("petty_cash_witnesses" to listOf(witness(asha, "Asha")))
        synced()
        // Offline: the witness comes from the stored list.
        val picked = pettyRepo.observeWitnesses(tenant).first().single()
        assertTrue(engine(online = false).sync(tenant) is SyncReport.Retry)
        val withWitness = saved(petty.count(PettyCashCountRequest(tenant, UUID.randomUUID().toString(), fundId, "100", picked.userId, "", emptyList(), clock.now)))
        val alone = saved(petty.count(PettyCashCountRequest(tenant, UUID.randomUUID().toString(), fundId, "100", null, "", emptyList(), clock.now)))
        assertEquals(asha, payload(withWitness.operationId)["witness_user_id"]!!.jsonPrimitive.content)
        assertNull(payload(alone.operationId)["witness_user_id"])

        // The witness lost the permission meanwhile: the server keeps the count without the witness (a self-count).
        fake.handler = { o ->
            if (o["op_type"]!!.jsonPrimitive.content == PettyCashOps.COUNT) {
                "ACKED" to buildJsonObject { putJsonObject("entity") { put("witness_user_id", null as String?); put("self_count", true) } }
            } else null
        }
        synced()
        val records = pettyRepo.observe(tenant).first().records.associateBy { it.operationId }
        assertTrue(records.getValue(withWitness.operationId).witnessDropped)
        assertFalse(records.getValue(withWitness.operationId).selfCount)
        assertTrue(records.getValue(alone.operationId).selfCount)
        assertFalse(records.getValue(alone.operationId).witnessDropped)
    }

    @Test
    fun theHolderGivesAnAdvanceOfflineOnceAndItShowsAfterThePull() = runBlocking {
        fake.capabilities = listOf(SyncCapabilities.SUPERVISOR_INBOX_V1, SyncCapabilities.OP_PETTY_CASH, SyncCapabilities.OP_PETTY_CASH_ADVANCE)
        synced()
        val colleague = UUID.randomUUID().toString()
        val policy = com.asseta.core.domain.finance.PettyCashPolicy(advancesEnabled = true)
        fun request(clientId: String, recipient: String? = colleague, amount: String = "45000") =
            com.asseta.core.sync.usecase.PettyCashGiveAdvanceRequest(tenant, clientId, fundId, fake.staffId, recipient, amount, " Spare parts ",
                BigDecimal("40000"), "TZS", policy)
        assertTrue(engine(online = false).sync(tenant) is SyncReport.Retry) // offline from here
        assertEquals(listOf(PettyCashMessages.RECIPIENT), (petty.giveAdvance(request(UUID.randomUUID().toString(), recipient = fake.staffId)) as FinanceResult.Invalid).messages)
        val clientId = UUID.randomUUID().toString()
        val s = saved(petty.giveAdvance(request(clientId))) // above available: allowed offline by the policy
        assertEquals(FinanceResult.AlreadySaved, petty.giveAdvance(request(clientId)))
        val p = payload(s.operationId)
        assertEquals(PettyCashOps.ADVANCE, op(s.operationId).opType)
        assertEquals(clientId, p["client_id"]!!.jsonPrimitive.content)
        assertEquals(colleague, p["recipient_staff_id"]!!.jsonPrimitive.content)
        assertEquals("45000", p["amount"]!!.jsonPrimitive.content)
        assertEquals("Spare parts", p["purpose"]!!.jsonPrimitive.content)
        assertEquals(PettyCashOps.ADVANCE, pettyRepo.observe(tenant).first().records.single().opType)
        val strict = request(UUID.randomUUID().toString()).copy(policy = policy.copy(overspendAllowedOffline = false))
        assertTrue(petty.giveAdvance(strict) is FinanceResult.Invalid)

        val advanceId = UUID.randomUUID().toString()
        fake.handler = { o -> if (o["op_type"]!!.jsonPrimitive.content == PettyCashOps.ADVANCE) "ACKED" to buildJsonObject {} else null }
        fake.inbox = snapshot() + ("petty_cash_advances" to listOf(buildJsonObject {
            put("id", advanceId); put("number", "PC-0009"); put("fund_id", fundId); put("recipient_staff_id", colleague); put("recipient_staff_name", "Juma")
            put("amount", "45000"); put("currency", "TZS"); put("purpose", "Spare parts"); put("status", "OUTSTANDING")
            put("issued_at", "2026-10-21T08:00:00Z"); put("due_at", "2026-10-28T08:00:00Z"); put("remaining", "45000")
        }))
        synced()
        assertEquals(ACKED, status(s.operationId))
        val view = pettyRepo.observe(tenant, fake.staffId).first()
        assertEquals(listOf(advanceId), PettyCashRepository.clearable(view, fake.staffId).map { it.id })
    }

    @Test
    fun givingAnAdvanceNeedsItsCapability() = runBlocking {
        synced() // OP_PETTY_CASH without OP_PETTY_CASH_ADVANCE
        val r = com.asseta.core.sync.usecase.PettyCashGiveAdvanceRequest(tenant, UUID.randomUUID().toString(), fundId, fake.staffId,
            UUID.randomUUID().toString(), "100", "Spare parts", BigDecimal("40000"), "TZS", com.asseta.core.domain.finance.PettyCashPolicy(advancesEnabled = true))
        assertTrue(petty.giveAdvance(r) is FinanceResult.Blocked)
    }

    @Test
    fun operationsNeedTheCapability() = runBlocking {
        fake.capabilities = listOf(SyncCapabilities.SUPERVISOR_INBOX_V1)
        synced()
        assertTrue(petty.acknowledge(tenant, movementId, true, "1", "") is FinanceResult.Blocked)
    }

    @Test
    fun expensePaidFromAFundNamesTheFundAndChecksIt() = runBlocking {
        synced()
        fun expense(fund: FundChoice?, advance: AdvanceChoice? = null, currency: String = "TZS") = ExpenseRequest(
            tenant, UUID.randomUUID().toString(), fake.categoryId, "Rope", "", "50000", currency, PaidFrom.PETTY_CASH, fake.machineId, null,
            listOf(photo), GpsOutcome.Fix(-6.8, 39.28, 8.0, Instant.ofEpochMilli(clock.now), "fused"), clock.now, fund, advance,
        )
        val held = FundChoice(fundId, "TZS", BigDecimal("40000"), held = true)
        assertEquals(listOf(PettyCashMessages.FUND_REQUIRED), (finance.expense(expense(null)) as FinanceResult.Invalid).messages)
        assertEquals(listOf(PettyCashMessages.currency("TZS")), (finance.expense(expense(held, currency = "USD")) as FinanceResult.Invalid).messages)
        val other = FundChoice("f9", "TZS", null, held = false)
        assertEquals(listOf(PettyCashMessages.ADVANCE_REQUIRED), (finance.expense(expense(other)) as FinanceResult.Invalid).messages)
        // Above what is available: still saved offline (the server keeps it for approval and flags it).
        val s = saved(finance.expense(expense(held, AdvanceChoice("adv", "other-fund", BigDecimal.ONE))))
        val p = payload(s.operationId)
        assertEquals("PETTY_CASH", p["paid_from"]!!.jsonPrimitive.content)
        assertEquals(fundId, p["petty_cash_fund_id"]!!.jsonPrimitive.content)
        assertNull(p["petty_cash_advance_id"]) // an advance of another fund is never sent
    }
}
