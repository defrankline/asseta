package com.asseta.core.network

import kotlinx.coroutines.test.runTest
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.util.UUID

class InterceptorsTest {
    private val server = MockWebServer()
    private var token: String? = "access-123"
    private var tenant: String? = "a3c1d1f2-1111-4222-8333-944455556666"
    private lateinit var client: OkHttpClient

    @Before
    fun setUp() {
        server.start()
        client = NetworkFactory.okHttpClient({ token }, { tenant })
    }

    @After
    fun tearDown() = server.close()

    private fun call(request: Request) = client.newCall(request).execute().use { it.code }

    private fun get() = Request.Builder().url(server.url("/api/v1/me")).build()

    private fun post(builder: Request.Builder.() -> Unit = {}) = Request.Builder().url(server.url("/api/v1/x"))
        .post("{}".toRequestBody("application/json".toMediaType())).apply(builder).build()

    @Test
    fun `adds bearer tenant and uuid correlation id`() {
        server.enqueue(MockResponse(code = 200, body = "{}"))
        call(get())
        val recorded = server.takeRequest()
        assertEquals("Bearer access-123", recorded.headers["Authorization"])
        assertEquals(tenant, recorded.headers["X-Tenant-ID"])
        UUID.fromString(recorded.headers["X-Correlation-ID"])
        assertNull("GET must not carry an idempotency key", recorded.headers["Idempotency-Key"])
    }

    @Test
    fun `correlation id is unique per request`() {
        repeat(2) { server.enqueue(MockResponse(code = 200)) }
        call(get()); call(get())
        assertNotEquals(server.takeRequest().headers["X-Correlation-ID"], server.takeRequest().headers["X-Correlation-ID"])
    }

    @Test
    fun `omits auth and tenant when signed out or no tenant selected`() {
        token = null; tenant = null
        server.enqueue(MockResponse(code = 200))
        call(get())
        val recorded = server.takeRequest()
        assertNull(recorded.headers["Authorization"])
        assertNull(recorded.headers["X-Tenant-ID"])
    }

    @Test
    fun `mutations get idempotency key and explicit key is preserved`() {
        repeat(2) { server.enqueue(MockResponse(code = 201)) }
        call(post())
        call(post { header("Idempotency-Key", "op-uuid-1") })
        UUID.fromString(server.takeRequest().headers["Idempotency-Key"])
        assertEquals("op-uuid-1", server.takeRequest().headers["Idempotency-Key"])
    }

    @Test
    fun `error envelope becomes typed exception`() {
        server.enqueue(MockResponse(code = 422, body = """{"error":{"code":"VALIDATION_FAILED","message":"bad",
            "correlation_id":"cid-1","details":[{"field":"amount","issue":"must be decimal string"}]}}"""))
        val e = assertThrows(ApiException::class.java) { call(post()) }
        assertEquals(422, e.httpStatus)
        assertEquals("VALIDATION_FAILED", e.code)
        assertEquals("cid-1", e.correlationId)
        assertEquals("amount", e.details.single().field)
        assertTrue(!e.isRetryable)
    }

    @Test
    fun `non envelope error keeps status and correlation id`() {
        server.enqueue(MockResponse(code = 502, body = "<html>bad gateway</html>"))
        val e = assertThrows(ApiException::class.java) { call(get()) }
        assertEquals("HTTP_502", e.code)
        assertTrue(e.isRetryable)
        assertEquals(server.takeRequest().headers["X-Correlation-ID"], e.correlationId)
    }

    @Test
    fun `retrofit me call parses and surfaces 401`() = runTest {
        val api = NetworkFactory.api(server.url("/").toString(), client, allowCleartext = true)
        server.enqueue(MockResponse(code = 200, body = """{"user_id":"0d9c5c1e-3d55-4a35-8f7e-2b1e4f0f9a11",
            "email":"a@b.c","display_name":"A","platform_permissions":[],"platform_menus":[],"tenants":[],"new_field":1}"""))
        assertEquals("A", api.me().displayName)
        server.enqueue(MockResponse(code = 401, body = """{"error":{"code":"NOT_AUTHENTICATED","message":"no","correlation_id":"c"}}"""))
        val e = runCatching { api.me() }.exceptionOrNull() as ApiException
        assertTrue(e.isUnauthenticated)
    }

    @Test
    fun `release requires https base url`() {
        assertThrows(IllegalArgumentException::class.java) { NetworkFactory.api("http://api.local/", client, false) }
        assertThrows(IllegalArgumentException::class.java) { NetworkFactory.api("", client, true) }
    }

    /** A provider whose refresh after a 401 hands out [refreshed] (null = the session is gone). */
    private fun refreshingClient(refreshed: () -> String?): Pair<OkHttpClient, MutableList<String>> {
        val seen = mutableListOf<String>()
        val provider = object : AccessTokenProvider {
            override fun accessToken() = "access-1"
            override fun refreshedAccessToken(rejected: String): String? {
                seen += rejected
                return refreshed()
            }
        }
        return NetworkFactory.okHttpClient(provider, { tenant }) to seen
    }

    @Test
    fun `401 refreshes once and retries with the new token and the same idempotency key`() {
        val (c, rejected) = refreshingClient { "access-2" }
        server.enqueue(MockResponse(code = 401, body = """{"error":{"code":"NOT_AUTHENTICATED","message":"no","correlation_id":"c"}}"""))
        server.enqueue(MockResponse(code = 201))
        assertEquals(201, c.newCall(post()).execute().use { it.code })
        val first = server.takeRequest()
        val retry = server.takeRequest()
        assertEquals("Bearer access-1", first.headers["Authorization"])
        assertEquals("Bearer access-2", retry.headers["Authorization"])
        assertEquals(first.headers["Idempotency-Key"], retry.headers["Idempotency-Key"])
        assertEquals(listOf("access-1"), rejected)
    }

    @Test
    fun `401 stands when the session is gone`() {
        val (c, _) = refreshingClient { null }
        server.enqueue(MockResponse(code = 401, body = """{"error":{"code":"NOT_AUTHENTICATED","message":"no","correlation_id":"c"}}"""))
        val e = assertThrows(ApiException::class.java) { c.newCall(get()).execute().close() }
        assertTrue(e.isUnauthenticated)
        assertEquals(1, server.requestCount)
    }

    @Test
    fun `a session without a token right now fails like a network error and sends nothing`() {
        val c = NetworkFactory.okHttpClient({ throw TokenUnavailableException("offline") }, { tenant })
        assertThrows(java.io.IOException::class.java) { c.newCall(get()).execute().close() }
        assertEquals(0, server.requestCount)
    }

    @Test
    fun `a refresh that cannot reach the sign-in server after a 401 is a network error`() {
        val (c, _) = refreshingClient { throw TokenUnavailableException("offline") }
        server.enqueue(MockResponse(code = 401, body = """{"error":{"code":"NOT_AUTHENTICATED","message":"no","correlation_id":"c"}}"""))
        val e = assertThrows(java.io.IOException::class.java) { c.newCall(get()).execute().close() }
        assertTrue(e is TokenUnavailableException)
    }
}
