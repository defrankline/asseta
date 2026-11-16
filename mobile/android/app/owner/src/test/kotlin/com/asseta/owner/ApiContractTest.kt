package com.asseta.owner

import com.asseta.core.network.SyncApi
import com.asseta.core.network.TenantApi
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import java.io.File

/**
 * Every endpoint the apps call exists in contracts/openapi.json (method + path). ADR-008 §8 removed the job, contract,
 * hire-invoice, revenue, non-revenue, unbilled-work, site check-in and daily machine sheet endpoints: none is called.
 */
class ApiContractTest {
    private val paths by lazy {
        val dir = System.getProperty("asseta.contracts.dir") ?: error("asseta.contracts.dir not set")
        val spec = Json.parseToJsonElement(File(dir, "openapi.json").readText()).jsonObject
        spec["paths"]!!.jsonObject.flatMap { (path, ops) -> ops.jsonObject.keys.map { it.uppercase() to normalize(path) } }.toSet()
    }

    private fun normalize(path: String) = path.trim('/').replace(Regex("\\{[^}]+}"), "{}")

    private fun endpoints(api: Class<*>): List<Pair<String, String>> = api.declaredMethods.mapNotNull { m ->
        m.getAnnotation(GET::class.java)?.let { "GET" to it.value }
            ?: m.getAnnotation(POST::class.java)?.let { "POST" to it.value }
            ?: m.getAnnotation(PUT::class.java)?.let { "PUT" to it.value }
            ?: m.getAnnotation(PATCH::class.java)?.let { "PATCH" to it.value }
            ?: m.getAnnotation(DELETE::class.java)?.let { "DELETE" to it.value }
    }.map { (method, path) -> method to normalize(path.substringBefore('?')) }

    @Test
    fun `every called endpoint is in the contract`() {
        val called = endpoints(TenantApi::class.java) + endpoints(SyncApi::class.java)
        assertTrue(called.size > 100)
        val missing = called.filter { it !in paths }
        assertTrue("not in contracts/openapi.json: $missing", missing.isEmpty())
    }

    @Test
    fun `no removed ADR-008 endpoint is called`() {
        val removed = listOf(
            "api/v1/tenant/jobs", "api/v1/tenant/contracts", "api/v1/tenant/field/contracts", "api/v1/tenant/hire-invoices",
            "api/v1/tenant/revenue-differences", "api/v1/tenant/revenue-reasons", "api/v1/tenant/non-revenue", "api/v1/tenant/unbilled-work",
            "api/v1/tenant/site-checkins", "api/v1/tenant/daily-machine-sheet",
        )
        val called = endpoints(TenantApi::class.java).map { it.second }
        val stale = called.filter { path -> removed.any { path.startsWith(it) } }
        assertTrue("removed endpoints still called: $stale", stale.isEmpty())
    }
}
