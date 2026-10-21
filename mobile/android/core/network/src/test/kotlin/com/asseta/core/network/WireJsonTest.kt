package com.asseta.core.network

import com.asseta.core.model.sync.DeviceRegisterIn
import com.asseta.core.model.sync.GpsIn
import com.asseta.core.model.sync.OperationIn
import com.asseta.core.model.sync.PushIn
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Request bodies as the server sees them (found by the live E2E: a defaulted `platform` was silently dropped). */
class WireJsonTest {
    private val json = NetworkFactory.json

    @Test
    fun defaultedFieldsAreSentAndNullsOmitted() {
        val register = json.encodeToJsonElement(DeviceRegisterIn.serializer(), DeviceRegisterIn("dev-12345", appVersion = "1.0")).jsonObject
        assertEquals("ANDROID", register["platform"]!!.jsonPrimitive.content)
        assertEquals(setOf("device_id", "platform", "app_version"), register.keys)

        val push = json.encodeToJsonElement(
            PushIn.serializer(),
            PushIn("2026-10-21T08:00:00Z", listOf(OperationIn("op-1", "METER_CAPTURE", "2026-10-21T08:00:00Z", payload = JsonObject(emptyMap())))),
        ).jsonObject
        val op = push["operations"]!!.jsonArray.single().jsonObject
        assertTrue(op["depends_on"]!!.jsonArray.isEmpty())
        assertFalse(json.encodeToString(GpsIn.serializer(), GpsIn("NO_FIX")).contains("null"))
    }
}
