package com.asseta.owner

import com.asseta.core.domain.owner.DataSource
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.MutationGate
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.network.NetworkFactory
import com.asseta.core.model.owner.CashHandoverDto
import com.asseta.core.model.owner.ExceptionDto
import com.asseta.owner.ui.approvals.ApprovalsViewModel
import com.asseta.owner.ui.cash.CashViewModel
import com.asseta.owner.ui.cash.FloatText
import com.asseta.owner.ui.cash.HandoverText
import com.asseta.owner.ui.cash.HandoverViewModel
import com.asseta.owner.ui.common.ScreenState
import com.asseta.owner.ui.exceptions.ExceptionDetailViewModel
import com.asseta.owner.ui.exceptions.ExceptionReviewText
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import mockwebserver3.Dispatcher
import mockwebserver3.MockResponse
import mockwebserver3.RecordedRequest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.time.ZoneId
import java.util.Collections

/** Remote boss: confirm / dispute cash handovers, review meter exceptions and issue cash floats from the Owner app. */
@OptIn(ExperimentalCoroutinesApi::class)
class RemoteBossTest {
    private val h = OwnerHarness()

    /** Mutation requests seen by the server: path to (body, Idempotency-Key). */
    private val posts = Collections.synchronizedList(mutableListOf<Triple<String, String, String?>>())
    @Volatile private var handoverStatus = "CLAIMED"
    @Volatile private var exceptionStatus = "OPEN"
    @Volatile private var refuse: Pair<Int, String>? = null

    private fun handover() = """{"id":"$ID1","client_id":null,"staff_member_id":"$ID2","amount":"50000.0000","currency":"TZS",
        "handed_at":"2026-10-24T06:00:00Z","reference":null,"note":"Banked at CRDB Mpanda","status":"$handoverStatus","source":"MOBILE",
        "recorded_by":"$ID2","recorded_at":"2026-10-24T06:01:00Z","verified_by":null,"verified_at":null,"decision_note":null}"""

    private fun exception() = """{"id":"$ID1","job_id":"$ID2","machine_id":"$ID2","exception_type":"METER_DECREASE","severity":"CRITICAL",
        "blocking":true,"evidence":{"previous_reading":"1200.0"},"policy_version":"p","status":"$exceptionStatus","review_note":null,
        "reviewed_at":null,"created_at":"2026-10-22T08:00:00Z","meter_capture_id":null}"""

    private val summary = """[{"staff_member_id":"$ID2","staff_name":"Juma Katavi","currency":"TZS","period_from":"2026-10-24",
        "period_to":"2026-10-24","opening":"0","floats_issued":"100000","collections":"0","approved_spending":"0","verified_handovers":"0",
        "closing_outstanding":"100000","claimed_unverified_handovers":"50000","pending_spending":"0","unverified_collections":"0"}]"""

    private val jobSummary = """{"job":{"id":"$ID2","job_number":"J-1001","status":"IN_PROGRESS","machine_id":"$ID2","contract_id":"$ID2",
        "currency":"TZS","hourly_rate":"95000.0000","minimum_hours":"0.0000","mobilization_fee":"0.0000","discount_percent":"0.0000",
        "tax_rate_percent":"15.0000","rate_source":"CONTRACT","standby_treatment":"EXCLUDED","planned_start":"2026-10-21T06:00:00Z","version":3},
        "nonbillable_hours":"0.0000","billing_ready":false,"open_exceptions":1,"blocking_exceptions":1,"policy_version":"p"}"""

    @Before
    fun setUp() {
        Dispatchers.setMain(Dispatchers.Unconfined)
        h.server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.url.encodedPath
                fun ok(body: String, code: Int = 200) = MockResponse.Builder().code(code).body(body).build()
                if (request.method == "POST") {
                    posts += Triple(path, request.body!!.utf8(), request.headers["Idempotency-Key"])
                    refuse?.let { (code, error) ->
                        refuse = null
                        return ok("""{"error":{"code":"$error","message":"refused","correlation_id":"c"}}""", code)
                    }
                }
                return when {
                    path == "/api/v1/tenant/cash/handovers/$ID1/decision" -> {
                        handoverStatus = if (request.body!!.utf8().contains("\"verified\":true")) "VERIFIED" else "REJECTED"
                        ok(handover())
                    }
                    path == "/api/v1/tenant/cash/handovers" -> {
                        val wanted = request.url.queryParameter("status")
                        ok(if (wanted == null || wanted == handoverStatus) Samples.page(handover()) else Samples.page())
                    }
                    path == "/api/v1/tenant/cash/supervisor-summary" -> ok(summary)
                    path == "/api/v1/tenant/cash/floats" -> ok(
                        """{"id":"$ID1","staff_member_id":"$ID2","entry_type":"FLOAT_ISSUED","amount":"25000.0000","currency":"TZS",
                        "occurred_at":"2026-10-24T08:00:00Z","reference":null,"note":null}""",
                        201,
                    )
                    path == "/api/v1/tenant/exceptions/$ID1/review" -> {
                        exceptionStatus = Json.parseToJsonElement(request.body!!.utf8()).jsonObject["outcome"]!!.jsonPrimitive.content
                        ok(exception())
                    }
                    path == "/api/v1/tenant/exceptions" -> {
                        val wanted = request.url.queryParameter("status")
                        ok(if (wanted == null || wanted == exceptionStatus) Samples.page(exception()) else Samples.page())
                    }
                    path == "/api/v1/tenant/jobs/$ID2" -> ok(jobSummary)
                    path == "/api/v1/tenant/approvals" -> ok(Samples.page())
                    else -> ok("""{"error":{"code":"NOT_FOUND","message":"no","correlation_id":"c"}}""", 404)
                }
            }
        }
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
        h.close()
    }

    private fun <T> StateFlow<ScreenState<T>>.settled(): ScreenState<T> = runBlocking { withTimeout(5_000) { first { !it.loading } } }

    private fun <T> StateFlow<T>.await(predicate: (T) -> Boolean): T = runBlocking { withTimeout(5_000) { first(predicate) } }

    private fun post(i: Int): JsonObject = Json.parseToJsonElement(posts[i].second).jsonObject

    private val utc = ZoneId.of("UTC")

    @Test
    fun `claimed handovers are listed in approvals with the supervisor's name`() {
        val vm = ApprovalsViewModel(h.data, emptyFlow(), handovers = true)
        val list = vm.claimedHandovers!!.state.settled().data!!
        val item = list.items.single()
        assertEquals("Juma Katavi handed over TZS 50,000.00", HandoverText.headline(item, list.name(item)))
        assertEquals("Claimed 24 Oct 2026, 06:00", HandoverText.claimed(item, utc))
        assertEquals("A supervisor handed over TZS 50,000.00", HandoverText.headline(item, null))
        assertEquals("Cash handovers", HandoverText.SECTION)
        assertEquals("No cash handovers waiting.", HandoverText.EMPTY)
        assertNull(ApprovalsViewModel(h.data, emptyFlow()).claimedHandovers)
    }

    @Test
    fun `confirming sends verified true with an optional note`() {
        val vm = HandoverViewModel(h.data, ID1, emptyFlow())
        assertEquals("CLAIMED", vm.handover(vm.state.settled().data!!)!!.status)
        vm.decide(true, "  ")
        assertEquals("Handover confirmed.", vm.message.await { it != null })
        val body = post(0)
        assertEquals("/api/v1/tenant/cash/handovers/$ID1/decision", posts[0].first)
        assertEquals("true", body["verified"]!!.jsonPrimitive.content)
        assertNull(body["note"])
        assertNotNull(posts[0].third)
        assertEquals("VERIFIED", vm.handover(vm.state.await { it.data?.items?.single()?.status == "VERIFIED" }.data!!)!!.status)
    }

    @Test
    fun `disputing needs a reason and sends verified false`() {
        val vm = HandoverViewModel(h.data, ID1, emptyFlow())
        vm.state.settled()
        vm.decide(false, " ")
        assertTrue(posts.isEmpty())
        vm.decide(false, "Only TZS 40,000 arrived")
        assertEquals("Handover disputed.", vm.message.await { it != null })
        assertEquals("false", post(0)["verified"]!!.jsonPrimitive.content)
        assertEquals("Only TZS 40,000 arrived", post(0)["note"]!!.jsonPrimitive.content)
    }

    @Test
    fun `a handover decided elsewhere reads friendly`() {
        val vm = HandoverViewModel(h.data, ID1, emptyFlow())
        vm.state.settled()
        refuse = 409 to "HANDOVER_ALREADY_DECIDED"
        vm.decide(true, "")
        assertEquals("Someone already decided this handover. Reload to see it.", vm.error.await { it != null })
    }

    @Test
    fun `open exceptions are listed with their job number and reviewed with outcome and note`() {
        val approvals = ApprovalsViewModel(h.data, emptyFlow(), jobs = true, exceptions = true)
        val list = approvals.openExceptions!!.state.settled().data!!
        val e = list.items.single()
        assertEquals("Meter decrease on J-1001", ExceptionReviewText.headline(e, list.jobNumber(e)))
        assertEquals("Meter decrease", ExceptionReviewText.headline(e, null))
        assertEquals("Review · Meter decrease", ExceptionReviewText.dialogTitle(e))

        val vm = ExceptionDetailViewModel(h.data, ID1, emptyFlow())
        vm.state.settled()
        vm.review("EXPLAINED", "abc")
        assertTrue(posts.isEmpty())
        vm.review("EXPLAINED", "Meter was replaced, see reset")
        assertEquals("Exception reviewed.", vm.message.await { it != null })
        assertEquals("/api/v1/tenant/exceptions/$ID1/review", posts[0].first)
        assertEquals("EXPLAINED", post(0)["outcome"]!!.jsonPrimitive.content)
        assertEquals("Meter was replaced, see reset", post(0)["note"]!!.jsonPrimitive.content)
        assertNotNull(posts[0].third)
        assertEquals("EXPLAINED", vm.state.await { it.data?.items?.single()?.status == "EXPLAINED" }.data!!.items.single().status)
    }

    @Test
    fun `an exception reviewed elsewhere reads friendly`() {
        val vm = ExceptionDetailViewModel(h.data, ID1, emptyFlow())
        vm.state.settled()
        refuse = 409 to "ALREADY_REVIEWED"
        vm.review("CONFIRMED", "Photo shows a lower reading")
        assertEquals("Someone else has already reviewed this exception; reload the list.", vm.error.await { it != null })
    }

    @Test
    fun `review rules and wording mirror the web dialog`() {
        assertEquals(
            listOf("Explained — a legitimate reason was found", "Discrepancy confirmed — evidence stands as recorded"),
            ExceptionReviewText.OUTCOMES.map { it.second },
        )
        assertEquals(listOf("EXPLAINED", "CONFIRMED"), ExceptionReviewText.OUTCOMES.map { it.first })
        assertEquals("Record review", ExceptionReviewText.RECORD_REVIEW)
        assertEquals("Review note", ExceptionReviewText.NOTE)
        assertEquals("A review note is required", ExceptionReviewText.noteError("  "))
        assertEquals("At least 5 characters", ExceptionReviewText.noteError("abcd"))
        assertNull(ExceptionReviewText.noteError("abcde"))
        assertFalse(ExceptionReviewText.canReview(null, "long enough"))
        assertTrue(ExceptionReviewText.canReview("CONFIRMED", "long enough"))
    }

    @Test
    fun `issuing a float sends the supervisor, amount and currency`() {
        val vm = CashViewModel(h.data, emptyFlow(), handovers = true) { java.time.LocalDate.parse("2026-10-24") }
        vm.state.settled()
        assertEquals(1, vm.claimedHandovers!!.state.settled().data!!.items.size)
        vm.issueFloat(ID2, "TZS", "abc", "")
        assertTrue(posts.isEmpty())
        vm.issueFloat(ID2, "TZS", "25000", "For diesel")
        assertEquals("Float issued.", vm.message.await { it != null })
        assertEquals("/api/v1/tenant/cash/floats", posts[0].first)
        val body = post(0)
        assertEquals(ID2, body["staff_member_id"]!!.jsonPrimitive.content)
        assertEquals("25000", body["amount"]!!.jsonPrimitive.content)
        assertEquals("TZS", body["currency"]!!.jsonPrimitive.content)
        assertEquals("FLOAT_ISSUED", body["entry_type"]!!.jsonPrimitive.content)
        assertEquals("For diesel", body["note"]!!.jsonPrimitive.content)
        assertNotNull(posts[0].third)
    }

    @Test
    fun `float refusals read plainly and the wording matches iOS`() {
        val vm = CashViewModel(h.data, emptyFlow()) { java.time.LocalDate.parse("2026-10-24") }
        vm.state.settled()
        refuse = 403 to "NOT_CUSTODIAN"
        vm.issueFloat(ID2, "TZS", "1000", "")
        assertEquals("Only office cash staff may record custody for someone else.", vm.error.await { it != null })
        assertEquals("Amount (TZS)", FloatText.amountLabel("TZS"))
        assertEquals("Issue a cash float", FloatText.TITLE)
        assertNull(FloatText.amount("0"))
        assertEquals("1500.5", FloatText.amount("1500.5"))
    }

    @Test
    fun `each action is gated on its permission`() {
        listOf(
            OwnerAction.DECIDE_HANDOVER to "tenant.finance.verify",
            OwnerAction.REVIEW_EXCEPTION to "tenant.meter.review",
            OwnerAction.ISSUE_FLOAT to "tenant.finance.cash",
        ).forEach { (action, permission) ->
            assertEquals(MutationCheck.Blocked(MutationGate.NOT_PERMITTED), MutationGate.check(action, true, DataSource.LIVE, setOf("tenant.finance.read"), false))
            assertEquals(MutationCheck.Allowed, MutationGate.check(action, true, DataSource.LIVE, setOf(permission), false))
            assertEquals(MutationCheck.Blocked(MutationGate.OFFLINE), MutationGate.check(action, false, DataSource.LIVE, setOf(permission), false))
        }
    }

    @Test
    fun `dtos decode the contract shapes`() {
        val handover = NetworkFactory.json.decodeFromString(CashHandoverDto.serializer(), handover())
        assertEquals("Banked at CRDB Mpanda", handover.note)
        val exception = NetworkFactory.json.decodeFromString(ExceptionDto.serializer(), exception())
        assertTrue(exception.blocking)
    }
}
