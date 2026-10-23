package com.asseta.core.model

import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Test
import java.util.UUID

class ContractParsingTest {
    private val json = Json { ignoreUnknownKeys = true }

    @Test
    fun `parses error envelope with details`() {
        val body = """
            {"error":{"code":"VALIDATION_FAILED","message":"Request validation failed",
             "correlation_id":"6b1f2a6e-6f7e-4d43-9a4f-0c7f5f1b2a10",
             "details":[{"field":"email","issue":"invalid"},{"field":null,"issue":"missing body"}]}}
        """.trimIndent()
        val envelope = json.decodeFromString(ErrorEnvelope.serializer(), body)
        assertEquals("VALIDATION_FAILED", envelope.error.code)
        assertEquals("6b1f2a6e-6f7e-4d43-9a4f-0c7f5f1b2a10", envelope.error.correlationId)
        assertEquals(2, envelope.error.details.size)
        assertEquals("email", envelope.error.details[0].field)
        assertNull(envelope.error.details[1].field)
    }

    @Test
    fun `error envelope details default to empty`() {
        val body = """{"error":{"code":"NOT_FOUND","message":"x","correlation_id":"c"}}"""
        assertEquals(0, json.decodeFromString(ErrorEnvelope.serializer(), body).error.details.size)
    }

    @Test
    fun `parses me response`() {
        val body = """
            {"user_id":"0d9c5c1e-3d55-4a35-8f7e-2b1e4f0f9a11","email":"sup@example.com","display_name":"Sup",
             "platform_permissions":[],"platform_menus":[{"key":"platform.tenants","label":"Tenants","path":"/platform/tenants","order":10,"group":"Clients"}],
             "tenants":[{"tenant_id":"a3c1d1f2-1111-4222-8333-944455556666",
             "name":"Acme Hire","status":"ACTIVE","access_state":"READ_ONLY","permissions":["jobs.read"],"menus":[{"key":"tenant.jobs","label":"Jobs","path":"/tenant/jobs","order":20,"group":"Operations"}]},
             {"tenant_id":"b3c1d1f2-1111-4222-8333-944455556666","name":"Future","status":"X","access_state":"NEW_STATE"}]}
        """.trimIndent()
        val me = json.decodeFromString(MeResponse.serializer(), body)
        assertEquals(UUID.fromString("0d9c5c1e-3d55-4a35-8f7e-2b1e4f0f9a11"), me.userId)
        assertEquals(listOf("platform.tenants"), me.platformMenus.map { it.key })
        assertEquals("Operations", me.tenants.first().menus.single().group)
        val acme = me.tenants.first()
        assertEquals("Acme Hire", acme.name)
        assertEquals(listOf("jobs.read"), acme.permissions)
        assertEquals(TenantAccessState.READ_ONLY, acme.accessState)
        assertEquals(TenantAccessState.UNKNOWN, me.tenants[1].accessState)
        assertEquals(false, me.tenants[1].accessState.canEnter)
    }

    @Test
    fun `rejects non canonical uuid`() {
        val body = """{"user_id":"1-2-3-4-5","email":"e","display_name":"d"}"""
        assertThrows(SerializationException::class.java) { json.decodeFromString(MeResponse.serializer(), body) }
    }
}
