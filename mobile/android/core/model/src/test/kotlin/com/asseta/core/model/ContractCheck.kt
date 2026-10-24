package com.asseta.core.model

import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.descriptors.StructureKind
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import java.io.File

/**
 * Checks a Kotlin DTO against its schema in contracts/openapi.json: every Kotlin property exists in the contract, a
 * property Kotlin requires is required by the contract, every contract-required property is mapped, and array
 * properties agree on their item kind (a list of strings must not stand in for a list of objects, or vice versa).
 */
object ContractCheck {
    private val json = Json { ignoreUnknownKeys = true }

    val schemas: JsonObject by lazy {
        val dir = System.getProperty("asseta.contracts.dir") ?: error("asseta.contracts.dir not set")
        json.parseToJsonElement(File(dir, "openapi.json").readText()).jsonObject["components"]!!.jsonObject["schemas"]!!.jsonObject
    }

    /**
     * [extra]: device-only properties of a sync payload that the push dispatcher consumes before validating against
     * [schemaName] (e.g. `evidence_upload_ids`); [subset]: the DTO deliberately maps only part of a large response;
     * [request]: a body the app sends, which may always fill a property the contract makes optional.
     */
    fun check(schemaName: String, descriptor: SerialDescriptor, extra: Set<String> = emptySet(), subset: Boolean = false, request: Boolean = false) {
        val schema = schemas[schemaName]?.jsonObject ?: error("schema $schemaName missing from contract")
        val properties = schema["properties"]!!.jsonObject.keys
        val required = schema["required"]?.jsonArray?.map { it.jsonPrimitive.content }?.toSet().orEmpty()
        val names = (0 until descriptor.elementsCount).associate { descriptor.getElementName(it) to descriptor.isElementOptional(it) }
            .filterKeys { it !in extra }
        names.keys.forEach { assertTrue("$schemaName has no property '$it'", it in properties) }
        if (!request) names.filterValues { !it }.keys.forEach { assertTrue("$schemaName.$it is mandatory in Kotlin but optional in the contract", it in required) }
        if (!subset) required.forEach { assertTrue("$schemaName.$it required by the contract but not mapped", it in names) }
        (0 until descriptor.elementsCount).forEach { i ->
            val name = descriptor.getElementName(i)
            if (name in extra) return@forEach
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
}
