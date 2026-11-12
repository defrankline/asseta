package com.asseta.core.network

import com.asseta.core.model.AccountDeletionRequest
import com.asseta.core.model.owner.ClosureCancelIn
import kotlinx.coroutines.test.runTest
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/** Account deletion (no tenant header), the USER_INACTIVE sign-out signal and the Owner closure endpoints. */
class AccountDeletionApiTest {
    private val server = MockWebServer()
    private val tenant = "a3c1d1f2-1111-4222-8333-944455556666"
    private var inactive = 0

    @Before
    fun setUp() {
        server.start()
        NetworkFactory.userInactiveListener = { inactive++ }
    }

    @After
    fun tearDown() {
        NetworkFactory.userInactiveListener = null
        server.close()
    }

    private val client get() = NetworkFactory.okHttpClient({ "t" }, { tenant })
    private val api get() = NetworkFactory.api(server.url("/").toString(), client, allowCleartext = true)
    private val tenantApi get() = NetworkFactory.tenantApi(server.url("/").toString(), client, allowCleartext = true)

    @Test
    fun `account deletion is sent without a tenant, with confirm true and an idempotency key`() = runTest {
        server.enqueue(
            MockResponse.Builder().body(
                """{"user_id":"$tenant","display_name":"Former user a3c1d1f2","deleted_at":"2026-11-12T08:00:00Z","companies":["Acme"]}""",
            ).build(),
        )
        val result = api.deleteMyAccount(AccountDeletionRequest(reason = "Leaving"))
        assertEquals("Former user a3c1d1f2", result.displayName)
        assertEquals(listOf("Acme"), result.companies)
        val request = server.takeRequest()
        assertEquals("/api/v1/me/account-deletion", request.url.encodedPath)
        assertNull(request.headers[AssetaHeaders.TENANT_ID])
        assertNull(request.headers[AssetaHeaders.NO_TENANT])
        assertNotNull(request.headers[AssetaHeaders.IDEMPOTENCY_KEY])
        val body = request.body!!.utf8()
        assertTrue(body, body.contains("\"confirm\":true"))
        assertTrue(body, body.contains("\"reason\":\"Leaving\""))
    }

    @Test
    fun `last owner refusal is a typed error carrying the server message`() = runTest {
        server.enqueue(
            MockResponse.Builder().code(422).body(
                """{"error":{"code":"LAST_OWNER","message":"You are the last owner of Acme Hire","correlation_id":"c1"}}""",
            ).build(),
        )
        try {
            api.deleteMyAccount(AccountDeletionRequest())
            fail("expected ApiException")
        } catch (e: ApiException) {
            assertEquals("LAST_OWNER", e.code)
            assertEquals("You are the last owner of Acme Hire", e.message)
            assertFalse(e.isUserInactive)
        }
        assertEquals(0, inactive)
    }

    @Test
    fun `403 USER_INACTIVE from any call tells the sign-out listener`() = runTest {
        server.enqueue(
            MockResponse.Builder().code(403).body("""{"error":{"code":"USER_INACTIVE","message":"User is deactivated","correlation_id":"c2"}}""").build(),
        )
        server.enqueue(
            MockResponse.Builder().code(403).body("""{"error":{"code":"FORBIDDEN","message":"No","correlation_id":"c3"}}""").build(),
        )
        try {
            api.me(); fail("expected ApiException")
        } catch (e: ApiException) {
            assertTrue(e.isUserInactive)
        }
        assertEquals(1, inactive)
        try {
            tenantApi.companyClosure(); fail("expected ApiException")
        } catch (e: ApiException) {
            assertFalse(e.isUserInactive)
        }
        assertEquals(1, inactive)
    }

    @Test
    fun `closure status and cancel use the tenant header`() = runTest {
        server.enqueue(
            MockResponse.Builder().body(
                """{"tenant_id":"$tenant","company_name":"Acme Hire","waiting_days":30,"request":{"id":"r1","tenant_id":"$tenant",
                "tenant_name":"Acme Hire","status":"REQUESTED","reason":"Selling","requested_by":null,"requested_by_name":"Asha",
                "requested_at":"2026-11-12T08:00:00Z","waiting_days":30,"scheduled_for":"2026-12-12T08:00:00Z","policy_version":"1",
                "attempts":0,"steps_done":[]}}""",
            ).build(),
        )
        val status = tenantApi.companyClosure()
        assertEquals("REQUESTED", status.request!!.status)
        assertEquals("Asha", status.request!!.requestedByName)
        assertEquals(tenant, server.takeRequest().headers[AssetaHeaders.TENANT_ID])

        server.enqueue(
            MockResponse.Builder().body(
                """{"id":"r1","status":"CANCELLED","reason":"Selling","requested_at":"2026-11-12T08:00:00Z",
                "scheduled_for":"2026-12-12T08:00:00Z","cancelled_by_name":"Asha","cancel_reason":"Changed our mind"}""",
            ).build(),
        )
        assertEquals("CANCELLED", tenantApi.cancelCompanyClosure(ClosureCancelIn("Changed our mind")).status)
        val cancel = server.takeRequest()
        assertEquals("/api/v1/tenant/company/deletion-request/cancel", cancel.url.encodedPath)
        assertEquals(tenant, cancel.headers[AssetaHeaders.TENANT_ID])
        assertEquals("""{"reason":"Changed our mind"}""", cancel.body!!.utf8())
    }
}
