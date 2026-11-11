package com.asseta.core.sync.data

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.ReferenceRecordEntity
import com.asseta.core.domain.customers.CustomerValues
import com.asseta.core.model.sync.CustomerWriteIn
import com.asseta.core.model.sync.FieldCustomerDto
import com.asseta.core.network.ApiException
import com.asseta.core.network.TenantApi
import kotlinx.coroutines.CancellationException
import kotlinx.serialization.json.Json
import java.io.IOException

/** An online customer read or save, as the screens need it. */
sealed interface CustomerResult<out T> {
    data class Done<T>(val value: T) : CustomerResult<T>

    /** No connection: nothing was sent (and nothing is queued). */
    data object Offline : CustomerResult<Nothing>

    /** The server refused it: [message] is its own words; [stale] when someone else changed the customer meanwhile. */
    data class Refused(val message: String, val code: String?, val stale: Boolean = false) : CustomerResult<Nothing>
}

/**
 * Customers from the Supervisor app (`tenant.customer.details`), online only: list, read, add and edit details. Sync
 * delivers only the customers on my jobs' contracts, so every customer read or saved here is also written into the
 * phone's synced customer list, where the hours sale and cash collection pickers find it.
 */
class FieldCustomers(
    private val api: () -> TenantApi,
    private val db: () -> AssetaDatabase,
    private val json: Json,
) {
    suspend fun list(tenantId: String, query: String): CustomerResult<List<FieldCustomerDto>> = call {
        api().fieldCustomers(q = query.trim().ifEmpty { null }).items.filter { it.isActive }
    }.also { if (it is CustomerResult.Done) remember(tenantId, it.value) }

    suspend fun get(tenantId: String, id: String): CustomerResult<FieldCustomerDto> =
        call { api().fieldCustomer(id) }.also { if (it is CustomerResult.Done) remember(tenantId, listOf(it.value)) }

    /** Add ([id] null) or edit (with the [version] last read). */
    suspend fun save(tenantId: String, id: String?, values: CustomerValues, version: Int?): CustomerResult<FieldCustomerDto> {
        val body = CustomerWriteIn(
            values.code, values.name, values.taxId, values.contactName, values.phone, values.email, values.paymentTermsDays,
            version = version.takeIf { id != null },
        )
        return call { if (id == null) api().createCustomer(body) else api().updateCustomer(id, body) }
            .also { if (it is CustomerResult.Done) remember(tenantId, listOf(it.value)) }
    }

    /** The pickers' customers: the synced reference rows (active ones only; an inactive one leaves the pickers). */
    private suspend fun remember(tenantId: String, customers: List<FieldCustomerDto>) {
        if (customers.isEmpty()) return
        runCatching {
            db().fieldDataDao().upsertReferences(customers.map {
                ReferenceRecordEntity(ServerDataWriter.KIND_CUSTOMER, it.id, tenantId, it.name, json.encodeToString(com.asseta.core.model.sync.CustomerDto.serializer(), it.synced()))
            })
        }
    }

    private suspend fun <T> call(block: suspend () -> T): CustomerResult<T> = try {
        CustomerResult.Done(block())
    } catch (e: CancellationException) {
        throw e
    } catch (e: ApiException) {
        CustomerResult.Refused(e.message, e.code, stale = e.code == STALE_VERSION)
    } catch (e: IOException) {
        CustomerResult.Offline
    } catch (e: Exception) {
        CustomerResult.Refused(e.message ?: "Unexpected response from the server. Please try again.", null)
    }

    companion object {
        const val STALE_VERSION = "STALE_VERSION"
    }
}
