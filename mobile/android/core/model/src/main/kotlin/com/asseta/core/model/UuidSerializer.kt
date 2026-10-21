package com.asseta.core.model

import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerializationException
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import java.util.UUID

/** Serializes [UUID] as its canonical lowercase string form, matching the API contract. */
object UuidSerializer : KSerializer<UUID> {
    override val descriptor: SerialDescriptor = PrimitiveSerialDescriptor("com.asseta.UUID", PrimitiveKind.STRING)

    override fun serialize(encoder: Encoder, value: UUID) = encoder.encodeString(value.toString())

    override fun deserialize(decoder: Decoder): UUID {
        val raw = decoder.decodeString()
        return Uuids.parse(raw) ?: throw SerializationException("Invalid UUID: '$raw'")
    }
}

/** UUID helpers. Domain records and offline operations always use device/server generated UUIDs. */
object Uuids {
    private val CANONICAL = Regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

    fun random(): UUID = UUID.randomUUID()

    /** Strict parse: only the canonical 8-4-4-4-12 form is accepted (java.util.UUID.fromString is lenient). */
    fun parse(raw: String): UUID? = if (CANONICAL.matches(raw)) UUID.fromString(raw) else null
}

typealias SerializableUuid = @kotlinx.serialization.Serializable(with = UuidSerializer::class) UUID
