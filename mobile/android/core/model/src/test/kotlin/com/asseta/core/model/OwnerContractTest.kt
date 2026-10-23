package com.asseta.core.model

import com.asseta.core.model.owner.AlertDto
import com.asseta.core.model.owner.AnomalyCaseDetailDto
import com.asseta.core.model.owner.AnomalyCaseDto
import com.asseta.core.model.owner.ApprovalRequestDto
import com.asseta.core.model.owner.HistoryDto
import com.asseta.core.model.owner.JobDto
import com.asseta.core.model.owner.JobSummaryDto
import com.asseta.core.model.owner.MachineMapDto
import com.asseta.core.model.owner.MeterCaptureDto
import com.asseta.core.model.owner.NotificationDto
import com.asseta.core.model.owner.NotificationRoutingDto
import com.asseta.core.model.owner.PageDto
import com.asseta.core.model.owner.PushDeviceDto
import com.asseta.core.model.owner.PushDeviceIn
import com.asseta.core.model.owner.TenantOverviewDto
import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerializationException
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.descriptors.StructureKind
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.math.BigDecimal

/** Owner DTOs against contracts/openapi.json (field names + required-ness) and against contract-shaped samples. */
class OwnerContractTest {
    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false }
    private val schemas: JsonObject by lazy {
        val dir = System.getProperty("asseta.contracts.dir") ?: error("asseta.contracts.dir not set")
        json.parseToJsonElement(File(dir, "openapi.json").readText()).jsonObject["components"]!!.jsonObject["schemas"]!!.jsonObject
    }

    private fun check(schemaName: String, descriptor: SerialDescriptor) {
        val schema = schemas[schemaName]?.jsonObject ?: error("schema $schemaName missing from contract")
        val properties = schema["properties"]!!.jsonObject.keys
        val required = schema["required"]?.jsonArray?.map { it.jsonPrimitive.content }?.toSet().orEmpty()
        val names = (0 until descriptor.elementsCount).associate { descriptor.getElementName(it) to descriptor.isElementOptional(it) }
        names.keys.forEach { assertTrue("$schemaName has no property '$it'", it in properties) }
        names.filterValues { !it }.keys.forEach { assertTrue("$schemaName.$it is mandatory in Kotlin but optional in the contract", it in required) }
        required.forEach { assertTrue("$schemaName.$it required by the contract but not mapped", it in names) }
        // Array item kinds must agree too: a list of strings must not stand in for a list of objects (or vice versa).
        (0 until descriptor.elementsCount).forEach { i ->
            val name = descriptor.getElementName(i)
            val items = arrayItems(schema["properties"]!!.jsonObject[name]!!.jsonObject) ?: return@forEach
            val element = descriptor.getElementDescriptor(i)
            assertEquals("$schemaName.$name is an array in the contract", StructureKind.LIST, element.kind)
            val target = items["\$ref"]?.jsonPrimitive?.content?.substringAfterLast('/')?.let { schemas[it]!!.jsonObject } ?: items
            val objectItems = target["type"]?.jsonPrimitive?.content == "object" || "properties" in target
            val kotlinItem = element.getElementDescriptor(0).kind
            assertEquals("$schemaName.$name item kind", objectItems, kotlinItem == StructureKind.CLASS)
        }
    }

    /** Item schema of an array property (also when wrapped in a nullable anyOf), or null if not an array. */
    private fun arrayItems(property: JsonObject): JsonObject? {
        if (property["type"]?.jsonPrimitive?.content == "array") return property["items"]?.jsonObject
        return property["anyOf"]?.jsonArray?.firstNotNullOfOrNull { arrayItems(it.jsonObject) }
    }

    @Test
    fun `owner DTOs match the contract schemas`() {
        mapOf<String, KSerializer<*>>(
            "TenantOverviewDto" to TenantOverviewDto.serializer(),
            "MachineMapDto" to MachineMapDto.serializer(),
            "HistoryDto" to HistoryDto.serializer(),
            "JobDto" to JobDto.serializer(),
            "JobSummaryDto" to JobSummaryDto.serializer(),
            "MeterCaptureDto" to MeterCaptureDto.serializer(),
            "AlertDto" to AlertDto.serializer(),
            "ApprovalRequestDto" to ApprovalRequestDto.serializer(),
            "AnomalyCaseDto" to AnomalyCaseDto.serializer(),
            "AnomalyCaseDetailDto" to AnomalyCaseDetailDto.serializer(),
            "NotificationDto" to NotificationDto.serializer(),
            "NotificationRoutingDto" to NotificationRoutingDto.serializer(),
            "PushDeviceDto" to PushDeviceDto.serializer(),
            "PushDeviceIn" to PushDeviceIn.serializer(),
            "MeDto" to MeResponse.serializer(),
            "TenantAccessDto" to TenantAccess.serializer(),
            "MenuDto" to MenuEntry.serializer(),
            "MenuGroupDto" to MenuGroup.serializer(),
        ).forEach { (name, serializer) -> check(name, serializer.descriptor) }
    }

    @Test
    fun `parses overview with partial sections and exact money`() {
        val body = """{"tenant_id":"a3c1d1f2-1111-4222-8333-944455556666","as_of":"2026-10-22T08:00:00Z","timezone":"Africa/Dar_es_Salaam",
            "fleet":{"machines":3,"connectivity":{"live":1,"offline":2},"engine_on_verified":1,"open_alerts":{"critical":1},
            "reported_work_state":{"WORKING":1},"latest_source_at":"2026-10-22T07:59:00Z"},
            "work":null,"risk":null,
            "money":{"month_start":"2026-10-01","latest_source_at":null,"currencies":[{"currency":"TZS","receivables_outstanding":"1092500.0000",
            "receivables_overdue":"0.0000","overdue_invoices":0,"verified_receipts_mtd":"500000.0000","approved_expenses_mtd":"150000.0000",
            "cash_with_supervisors":"50000.0000"}]}}"""
        val o = json.decodeFromString(TenantOverviewDto.serializer(), body)
        assertEquals(2, o.fleet!!.connectivity.offline)
        assertEquals(0, o.fleet!!.connectivity.stale)
        assertEquals(1, o.fleet!!.openAlerts.total)
        assertNull(o.work)
        assertEquals(0, BigDecimal("1092500").compareTo(o.money!!.currencies[0].receivablesOutstanding.value))
    }

    @Test
    fun `money as float is rejected`() {
        val body = """{"id":"a3c1d1f2-1111-4222-8333-944455556666","subject_type":"EXPENSE","subject_id":"a3c1d1f2-1111-4222-8333-944455556667",
            "amount":1250.5,"currency":"TZS","reason":"r","status":"PENDING","requested_at":"2026-10-22T08:00:00Z","policy_version":"v1"}"""
        assertThrows(SerializationException::class.java) { json.decodeFromString(ApprovalRequestDto.serializer(), body) }
    }

    @Test
    fun `parses fleet rows with unknown enum values and missing position`() {
        val body = """[{"machine_id":"a3c1d1f2-1111-4222-8333-944455556666","asset_code":"EX-01","name":"Excavator","machine_status":"ACTIVE",
            "connectivity":"SOMETHING_NEW","is_live":false,"observed_engine":"UNKNOWN","observed_motion":"UNKNOWN","reported_work_status":"IDLE",
            "location_compliance":"UNKNOWN","open_alerts":0,"policy_version":"p","latitude":null,"longitude":null,"tracker_id":null}]"""
        val rows = json.decodeFromString(kotlinx.serialization.builtins.ListSerializer(MachineMapDto.serializer()), body)
        assertEquals("SOMETHING_NEW", rows[0].connectivity)
        assertFalse(rows[0].hasPosition)
    }

    @Test
    fun `parses alert page and notification with target`() {
        val page = """{"items":[{"id":"a3c1d1f2-1111-4222-8333-944455556666","alert_type":"TRACKER_OFFLINE","severity":"WARNING","status":"OPEN",
            "title":"Tracker offline","event_time":"2026-10-22T08:00:00Z","created_at":"2026-10-22T08:00:01Z","evidence":{"minutes":42,"site":"A"},
            "machine_id":null,"tracker_id":null,"acknowledged_at":null,"resolved_at":null,"resolution_note":null,"policy_version":null}],
            "total":1,"page":1,"page_size":50}"""
        val alerts = json.decodeFromString(PageDto.serializer(AlertDto.serializer()), page)
        assertEquals("42", alerts.items[0].evidence["minutes"].toString())
        val n = json.decodeFromString(NotificationDto.serializer(), """{"id":"a3c1d1f2-1111-4222-8333-944455556666","type":"APPROVAL_REQUESTED",
            "category":"ACTION","severity":"INFO","priority":"NORMAL","title":"t","body":"b","created_at":"2026-10-22T08:00:00Z","read_at":null,
            "target":{"entity":"approval","id":"a3c1d1f2-1111-4222-8333-944455556667","path":"/tenant/approvals"},"tenant_id":null,"data":{}}""")
        assertEquals("approval", n.target!!.entity)
    }
}
