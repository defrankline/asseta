package com.asseta.core.sync

import com.asseta.core.database.AttachmentEntity
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.finance.ExpensePolicyDecision
import com.asseta.core.domain.finance.FuelEventType
import com.asseta.core.domain.finance.PaidFrom
import com.asseta.core.model.ClientOperationStatus.ACKED
import com.asseta.core.model.ClientOperationStatus.FAILED
import com.asseta.core.model.ClientOperationStatus.PENDING
import com.asseta.core.model.ClientOperationStatus.QUARANTINED
import com.asseta.core.model.sync.BlobPurpose
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.sync.usecase.CashCollectionRequest
import com.asseta.core.sync.usecase.CashHandoverRequest
import com.asseta.core.sync.usecase.ExpenseRequest
import com.asseta.core.sync.usecase.FinanceResult
import com.asseta.core.sync.usecase.FuelEventRequest
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.math.BigDecimal
import java.time.Instant
import java.util.UUID

/** Field finance (Gate 5) through the real engine, outbox and blob uploader against [FakeSyncServer]. */
@RunWith(RobolectricTestRunner::class)
class FinanceSyncTest : SyncTestBase() {

    private fun success(report: SyncReport): SyncReport.Success {
        assertTrue("expected Success but was $report", report is SyncReport.Success)
        return report as SyncReport.Success
    }

    private fun fix(accuracy: Double? = 8.0) = GpsOutcome.Fix(-6.8, 39.28, accuracy, Instant.ofEpochMilli(clock.now), "fused")

    private fun expense(
        amount: String = "250.00",
        receipts: List<ByteArray> = listOf(photo),
        gps: GpsOutcome? = fix(),
        paidFrom: PaidFrom = PaidFrom.CASH_CUSTODY,
        clientId: String = UUID.randomUUID().toString(),
        jobId: String? = null,
        machineId: String? = fake.machineId,
    ) = ExpenseRequest(tenant, clientId, fake.categoryId, "Hydraulic oil", "Puma", amount, "TZS", paidFrom, machineId, jobId,
        receipts, gps, clock.now)

    private fun collection(amount: String = "250000", jobId: String? = null, clientId: String = UUID.randomUUID().toString()) =
        CashCollectionRequest(tenant, clientId, fake.customerId, jobId, amount, "TZS", "RCPT-1", "", clock.now)

    private fun handover(amount: String = "100000") =
        CashHandoverRequest(tenant, UUID.randomUUID().toString(), amount, "tzs", "", "To office", clock.now)

    private fun saved(r: FinanceResult): FinanceResult.Saved {
        assertTrue("expected Saved but was $r", r is FinanceResult.Saved)
        return r as FinanceResult.Saved
    }

    private fun payload(opId: String): JsonObject = json.parseToJsonElement(op(opId).payloadJson).jsonObject

    @Test
    fun bootstrapStoresCategoriesCustodyAndPolicyAndDeltasDeactivate() = runBlocking {
        success(engine().sync(tenant))
        assertEquals(listOf("Fuel & oil"), financeRepository.observeCategories(tenant).first().map { it.name })
        assertEquals(listOf("Road Builders Ltd"), financeRepository.observeCustomers(tenant).first().map { it.name })
        val custody = db.financeDataDao().custody(tenant).single()
        assertEquals("500000.0000", custody.outstanding)
        assertEquals("TZS", financeRepository.baseCurrency(tenant))
        val decision = financeRepository.expensePolicy(tenant) as ExpensePolicyDecision.Allowed
        assertEquals(BigDecimal("100.00"), decision.policy.receiptRequiredAbove)
        assertEquals(BigDecimal("500.00"), decision.policy.autoApproveLimit)

        fake.cursor = 20
        fake.changesCategories = listOf(fake.category("Fuel & oil", false, 9))
        fake.changesCustomers = listOf(fake.customer(false))
        fake.custodyOutstanding = "450000.0000"
        success(engine().sync(tenant))
        assertTrue(financeRepository.observeCategories(tenant).first().isEmpty())
        assertTrue(financeRepository.observeCustomers(tenant).first().isEmpty())
        assertEquals("450000.0000", db.financeDataDao().custody(tenant).single().outstanding)

        fake.changesCategories = listOf(fake.category("Fuel & oil", true, 5)) // lookback replay of an older revision
        success(engine().sync(tenant))
        assertTrue(financeRepository.observeCategories(tenant).first().isEmpty())
        assertTrue(finance.expense(expense()) is FinanceResult.Blocked)
        assertTrue(finance.cashCollection(collection()) is FinanceResult.Blocked)
        assertTrue(db.clientOperationDao().observeUnsynced(tenant).first().isEmpty())
    }

    @Test
    fun offlineExpenseWaitsForItsReceiptUploadThenAcksExactlyOnce() = runBlocking {
        success(engine().sync(tenant))
        val request = expense()
        val saved = saved(finance.expense(request))
        assertEquals(PENDING, status(saved.operationId))
        assertEquals(emptyList<Any>(), payload(saved.operationId)["receipt_upload_ids"]!!.jsonArray.toList())
        val attachment = db.evidenceDao().attachment(db.clientOperationDao().attachmentsOf(saved.operationId).single())!!
        assertEquals(BlobPurpose.EXPENSE_RECEIPT, attachment.purpose)
        assertEquals(FinanceResult.AlreadySaved, finance.expense(request)) // same form visit: exactly one record

        assertTrue(engine(online = false).sync(tenant) is SyncReport.Retry)
        assertEquals(PENDING, status(saved.operationId))
        fake.failChunkOnce = 1 // receipt upload interrupted: the expense must not be sent before it completes
        assertTrue(engine().sync(tenant) is SyncReport.Retry)
        assertTrue(fake.pushedBatches.none { saved.operationId in it })

        success(engine().sync(tenant))
        assertEquals(ACKED, status(saved.operationId))
        val session = fake.blobs.values.single { it.attachmentId != null }
        assertEquals(listOf(session.id), payload(saved.operationId)["receipt_upload_ids"]!!.jsonArray.map { it.jsonPrimitive.content })
        val entity = fake.financeByClient[request.clientId]!!
        assertEquals("[\"${session.attachmentId}\"]", entity["receipt_attachment_ids"].toString())
        assertEquals("250", entity["amount"]!!.jsonPrimitive.content) // decimal string, never a float
        assertEquals(1, fake.applied.count { it == saved.operationId })
        assertEquals(1, db.clientOperationDao().observeByOpTypes(tenant, listOf("EXPENSE")).first().size)
    }

    private fun receipt(n: Int) = ByteArray(10) { (it * 7 + n).toByte() } // distinct content: no server dedupe

    @Test
    fun expenseWithSeveralReceiptsWaitsForEveryUploadAndSendsAllUploadIds() = runBlocking {
        success(engine().sync(tenant))
        val request = expense(receipts = (1..3).map(::receipt))
        val saved = saved(finance.expense(request))
        val locals = db.clientOperationDao().attachmentsOf(saved.operationId)
        assertEquals(3, locals.size)
        assertTrue(locals.all { db.evidenceDao().attachment(it)!!.purpose == BlobPurpose.EXPENSE_RECEIPT })

        fake.failChunkOnce = 1 // first receipt interrupted: the expense must wait for all three
        assertTrue(engine().sync(tenant) is SyncReport.Retry)
        assertTrue(fake.pushedBatches.none { saved.operationId in it })
        assertEquals(PENDING, status(saved.operationId))

        val report = success(engine().sync(tenant))
        assertEquals(3, report.uploaded)
        assertEquals(ACKED, status(saved.operationId))
        val completed = fake.blobs.values.filter { it.attachmentId != null }
        assertEquals(3, completed.size)
        val sent = payload(saved.operationId)["receipt_upload_ids"]!!.jsonArray.map { it.jsonPrimitive.content }
        assertEquals(completed.map { it.id }.toSet(), sent.toSet())
        assertEquals(3, sent.distinct().size)
        val entity = fake.financeByClient[request.clientId]!!
        assertEquals(completed.map { it.attachmentId }.toSet(), entity["receipt_attachment_ids"]!!.jsonArray.map { it.jsonPrimitive.content }.toSet())
        assertEquals(1, fake.applied.count { it == saved.operationId })
    }

    @Test
    fun atMostTenReceiptsPerExpense() = runBlocking {
        success(engine().sync(tenant))
        val tooMany = finance.expense(expense(receipts = (1..11).map(::receipt))) as FinanceResult.Invalid
        assertEquals(listOf("At most 10 receipt photos per expense."), tooMany.messages)
        assertTrue(db.clientOperationDao().observeUnsynced(tenant).first().isEmpty())
        assertTrue(db.evidenceDao().pendingAttachments(tenant, 20).isEmpty())

        val ten = saved(finance.expense(expense(receipts = (1..10).map(::receipt))))
        assertEquals(10, db.clientOperationDao().attachmentsOf(ten.operationId).size)
        success(engine().sync(tenant))
        assertEquals(ACKED, status(ten.operationId))
        assertEquals(10, payload(ten.operationId)["receipt_upload_ids"]!!.jsonArray.size)
    }

    @Test
    fun refusedReceiptUploadIsRetriedLaterWhileTheOtherReceiptsContinue() = runBlocking {
        success(engine().sync(tenant))
        val saved = saved(finance.expense(expense(receipts = listOf(receipt(1), receipt(2)))))
        val (first, second) = db.clientOperationDao().attachmentsOf(saved.operationId)
        fake.startBlobErrors += 422 to "VALIDATION_ERROR"
        success(engine().sync(tenant)) // a refusal for one file does not fail the sync
        val refused = db.evidenceDao().attachment(first)!!
        assertEquals(AttachmentEntity.PENDING, refused.status)
        assertEquals(clock.now + 30 * 60_000, refused.nextAttemptAt)
        assertTrue(refused.lastError!!.startsWith("VALIDATION_ERROR"))
        assertEquals(AttachmentEntity.COMPLETE, db.evidenceDao().attachment(second)!!.status) // not held up
        assertEquals(1, payload(saved.operationId)["receipt_upload_ids"]!!.jsonArray.size)
        assertEquals(PENDING, status(saved.operationId))

        val starts = fake.requests.count { it == "POST /api/v1/sync/blobs" }
        success(engine().sync(tenant)) // not due yet
        assertEquals(starts, fake.requests.count { it == "POST /api/v1/sync/blobs" })
        clock.advance(30 * 60_000)
        success(engine().sync(tenant))
        assertEquals(ACKED, status(saved.operationId))
        assertEquals(2, payload(saved.operationId)["receipt_upload_ids"]!!.jsonArray.size)
    }

    @Test
    fun lostResponseIsReplayedAsDuplicateWithOneCollection() = runBlocking {
        success(engine().sync(tenant))
        val saved = saved(finance.cashCollection(collection()))
        fake.failNextPushAfterApply = true
        assertTrue(engine().sync(tenant) is SyncReport.Retry)
        assertEquals(PENDING, status(saved.operationId))
        success(engine().sync(tenant))
        assertEquals(ACKED, status(saved.operationId))
        assertEquals(2, fake.pushedBatches.count { saved.operationId in it })
        assertEquals(1, fake.applied.count { it == saved.operationId })
        assertEquals(1, fake.financeByClient.size)
    }

    @Test
    fun receiptStillPendingServerSideIsDeferredThenAcked() = runBlocking {
        success(engine().sync(tenant))
        val saved = saved(finance.expense(expense()))
        fake.deferReceiptOnce = true
        success(engine().sync(tenant))
        assertEquals(PENDING, status(saved.operationId))
        assertEquals("ATTACHMENT_PENDING", op(saved.operationId).errorCode)
        success(engine().sync(tenant))
        assertEquals(ACKED, status(saved.operationId))
        assertNull(op(saved.operationId).errorCode)
    }

    @Test
    fun unknownReceiptIsRejectedNotResentAndNotCountedAsCash() = runBlocking {
        success(engine().sync(tenant))
        val saved = saved(finance.expense(expense()))
        fake.deferOnce += saved.operationId
        success(engine().sync(tenant)) // receipt uploaded, expense deferred
        fake.blobs.clear() // the server no longer knows the upload (purged)
        success(engine().sync(tenant))
        assertEquals(FAILED, status(saved.operationId))
        assertEquals("RECEIPT_NOT_FOUND", op(saved.operationId).errorCode)
        val pushes = fake.pushedBatches.count { saved.operationId in it }
        success(engine().sync(tenant))
        assertEquals(pushes, fake.pushedBatches.count { saved.operationId in it })
        val view = financeRepository.observeCashView(tenant).first()
        assertTrue(view.records.single().isRefused)
        assertEquals(0, view.lines.single().pendingCashExpenses.signum())
    }

    @Test
    fun cashOpsAreQuarantinedWhileReadOnlyThenApplied() = runBlocking {
        success(engine().sync(tenant))
        val c = saved(finance.cashCollection(collection())).operationId
        val h = saved(finance.cashHandover(handover())).operationId
        fake.readOnly = true
        success(engine().sync(tenant))
        assertEquals(listOf(QUARANTINED, QUARANTINED), listOf(status(c), status(h)))
        assertEquals("SUBSCRIPTION_READ_ONLY", op(c).errorCode)
        val held = financeRepository.observeCashView(tenant).first().lines.single()
        assertEquals(BigDecimal("250000"), held.pendingCollections) // held, still not verified
        success(engine().sync(tenant))
        assertEquals(QUARANTINED, status(c))
        fake.readOnly = false
        success(engine().sync(tenant))
        assertEquals(listOf(ACKED, ACKED), listOf(status(c), status(h)))
        assertTrue(fake.applied.containsAll(listOf(c, h)))
        assertTrue(!financeRepository.observeCashView(tenant).first().lines.single().hasPending)
    }

    @Test
    fun myCashSeparatesSyncedCustodyFromUnsyncedMovements() = runBlocking {
        success(engine().sync(tenant))
        saved(finance.cashCollection(collection("250000")))
        saved(finance.cashHandover(handover("100000")))
        saved(finance.expense(expense("300")))
        saved(finance.expense(expense("50", receipts = emptyList(), paidFrom = PaidFrom.COMPANY)))
        val fuel = saved(
            finance.fuelEvent(
                FuelEventRequest(tenant, UUID.randomUUID().toString(), FuelEventType.PURCHASE, "40.5", "3000", "TZS",
                    fake.machineId, null, "1234.5", "Puma", "", clock.now),
            ),
        )
        val view = financeRepository.observeCashView(tenant).first()
        val line = view.lines.single()
        assertEquals(BigDecimal("500000.0000"), line.synced!!.outstanding)
        assertEquals(BigDecimal("250000"), line.pendingCollections)
        assertEquals(BigDecimal("100000"), line.pendingHandovers)
        assertEquals(BigDecimal("300"), line.pendingCashExpenses) // company-paid expense is not custody
        assertEquals(0, line.estimatedInHand.compareTo(BigDecimal("649700")))
        assertEquals(5, view.records.size)
        assertEquals("40.5", payload(fuel.operationId)["litres"]!!.jsonPrimitive.content)

        fake.custodyOutstanding = "750000.0000"
        success(engine().sync(tenant))
        val after = financeRepository.observeCashView(tenant).first()
        assertTrue(after.records.all { it.status == ACKED })
        assertTrue(!after.lines.single().hasPending)
        assertEquals(BigDecimal("750000.0000"), after.lines.single().synced!!.outstanding)
    }

    @Test
    fun expenseCapturePolicyIsEnforcedOfflineBeforeQueueing() = runBlocking {
        assertTrue(finance.expense(expense()) is FinanceResult.Blocked) // no rules downloaded yet
        success(engine().sync(tenant))
        val noReceipt = finance.expense(expense(receipts = emptyList())) as FinanceResult.Invalid
        assertTrue(noReceipt.messages.single().contains("above 100 TZS"))
        assertTrue((finance.expense(expense(gps = GpsOutcome.Timeout)) as FinanceResult.Invalid).messages.single().contains("GPS fix"))
        assertTrue((finance.expense(expense(gps = fix(80.0))) as FinanceResult.Invalid).messages.single().contains("±80 m"))
        assertTrue(finance.expense(expense(gps = null)) is FinanceResult.Invalid)
        assertTrue(finance.expense(expense(amount = "1,250.50")) is FinanceResult.Invalid)
        assertTrue(db.clientOperationDao().observeUnsynced(tenant).first().isEmpty())

        val small = saved(finance.expense(expense(amount = "80", receipts = emptyList(), jobId = fake.jobId, machineId = null)))
        assertTrue(db.clientOperationDao().attachmentsOf(small.operationId).isEmpty()) // no receipt: nothing to wait for
        assertEquals(fake.machineId, payload(small.operationId)["machine_id"]!!.jsonPrimitive.content) // from the job

        val issue = finance.fuelEvent(
            FuelEventRequest(tenant, UUID.randomUUID().toString(), FuelEventType.ISSUE, "10", "2900", "TZS", null, null, "", "", "", clock.now),
        ) as FinanceResult.Invalid
        assertEquals(listOf("Choose the machine or job the fuel went to."), issue.messages)
        val withJob = saved(finance.cashCollection(collection(jobId = fake.jobId)))
        assertTrue(payload(withJob.operationId)["note"]!!.jsonPrimitive.content.startsWith("Job J-0001"))

        clock.advance(25 * 3_600_000L) // snapshot valid 24 h
        val expired = finance.expense(expense()) as FinanceResult.Blocked
        assertTrue(expired.message.startsWith("Connect to refresh rules"))
    }
}
