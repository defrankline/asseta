package com.asseta.core.sync

import com.asseta.core.domain.customers.CustomerValues
import com.asseta.core.network.NetworkFactory
import com.asseta.core.sync.data.CustomerResult
import com.asseta.core.sync.data.FieldCustomers
import com.asseta.core.sync.engine.SyncReport
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/** Supervisor customers: online only, the server's refusals in its words, and saved customers reach the pickers. */
@RunWith(RobolectricTestRunner::class)
class FieldCustomersTest : SyncTestBase() {
    private val newId = "c1000000-0000-4000-8000-000000000001"

    private fun customers(online: Boolean = true) = FieldCustomers(
        api = {
            val client = NetworkFactory.okHttpClient({ "token" }, { null }, device = { DEVICE })
            NetworkFactory.tenantApi(if (online) server.url("/").toString() else "http://127.0.0.1:1/", client, allowCleartext = true)
        },
        db = { db }, json = json,
    )

    private fun customer(id: String = newId, name: String = "Kilimo Ltd", version: Int = 1, active: Boolean = true, terms: Int = 30) =
        """{"id":"$id","code":"KIL","name":"$name","kind":"REGISTERED","tax_id":null,"contact_name":"Asha","contact_phone":"0700",""" +
            """"contact_email":null,"payment_terms_days":$terms,"is_active":$active,"deactivated_at":null,"deactivation_reason":null,"version":$version}"""

    private val values = CustomerValues("KIL", "Kilimo Ltd", null, "Asha", "0700", null, 30)
    private val sent = mutableListOf<Pair<String, String>>()

    @Test
    fun aSavedCustomerReachesThePickersAndTheListRefreshesThem() = runBlocking {
        assertTrue(engine().sync(tenant) is SyncReport.Success)
        fake.tenantRoute = { method, path, query, body ->
            sent += "$method $path${query?.let { "?$it" } ?: ""}" to body
            when {
                method == "POST" && path == "/api/v1/tenant/customers" -> fake.json(customer(), 201)
                method == "PUT" -> fake.json(customer(name = "Kilimo Group", version = 2))
                method == "GET" && path == "/api/v1/tenant/customers" ->
                    fake.json("""{"items":[${customer(name = "Kilimo Group", version = 2)},${customer(id = "c1000000-0000-4000-8000-000000000002", name = "Old", active = false)}],"total":2,"page":1,"page_size":50}""")
                else -> null
            }
        }
        val saved = customers().save(tenant, null, values, version = 7) as CustomerResult.Done
        assertEquals(newId, saved.value.id)
        val create = Json.parseToJsonElement(sent.single().second).jsonObject
        assertFalse("a new customer carries no version", create.containsKey("version"))
        assertEquals("30", create["payment_terms_days"]!!.jsonPrimitive.content)
        assertEquals(listOf("Kilimo Ltd"), financeRepository.observeCustomers(tenant).first().filter { it.id == newId }.map { it.name })

        customers().save(tenant, newId, values.copy(name = "Kilimo Group"), version = 1)
        assertEquals("PUT /api/v1/tenant/customers/$newId", sent.last().first)
        assertEquals("1", Json.parseToJsonElement(sent.last().second).jsonObject["version"]!!.jsonPrimitive.content)

        val listed = customers().list(tenant, " kil ") as CustomerResult.Done
        assertEquals(listOf("Kilimo Group"), listed.value.map { it.name }) // inactive ones are left out
        assertTrue(sent.last().first, sent.last().first.contains("q=kil"))
        assertEquals(listOf("Kilimo Group"), financeRepository.observeCustomers(tenant).first().filter { it.id == newId }.map { it.name })
    }

    @Test
    fun refusalsKeepTheServersWordsAndAStaleVersionIsMarked() = runBlocking {
        fake.tenantRoute = { method, _, _, _ ->
            when (method) {
                "POST" -> fake.error(403, "CUSTOMER_TERMS_NOT_PERMITTED", "Payment terms are set by the office; you can add customers and edit their details")
                "PUT" -> fake.error(409, "STALE_VERSION", "Customer was modified by someone else; reload and retry")
                else -> null
            }
        }
        val terms = customers().save(tenant, null, values.copy(paymentTermsDays = 60), null) as CustomerResult.Refused
        assertEquals("Payment terms are set by the office; you can add customers and edit their details", terms.message)
        assertFalse(terms.stale)
        val stale = customers().save(tenant, newId, values, 1) as CustomerResult.Refused
        assertTrue(stale.stale)
    }

    @Test
    fun offlineNothingIsSentOrQueued() = runBlocking {
        assertEquals(CustomerResult.Offline, customers(online = false).save(tenant, null, values, null))
        assertEquals(CustomerResult.Offline, customers(online = false).list(tenant, ""))
        assertTrue(db.clientOperationDao().observeUnsynced(tenant, USER_A.subject).first().isEmpty())
    }
}
