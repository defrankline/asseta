package com.asseta.core.model

import kotlinx.serialization.KSerializer
import kotlinx.serialization.Serializable
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder

/**
 * Effective tenant access computed by the server. Values the app does not know yet decode to [UNKNOWN],
 * which the UI treats like [BLOCKED] (fail closed) while the server stays authoritative either way.
 */
@Serializable(with = TenantAccessStateSerializer::class)
enum class TenantAccessState(val wire: String) {
    FULL("FULL"),
    READ_ONLY("READ_ONLY"),
    BLOCKED("BLOCKED"),
    UNKNOWN("UNKNOWN"),
    ;

    val canEnter: Boolean get() = this == FULL || this == READ_ONLY

    companion object {
        fun fromWire(raw: String): TenantAccessState = entries.firstOrNull { it.wire == raw && it != UNKNOWN } ?: UNKNOWN
    }
}

object TenantAccessStateSerializer : KSerializer<TenantAccessState> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("com.asseta.TenantAccessState", PrimitiveKind.STRING)

    override fun serialize(encoder: Encoder, value: TenantAccessState) = encoder.encodeString(value.wire)

    override fun deserialize(decoder: Decoder): TenantAccessState = TenantAccessState.fromWire(decoder.decodeString())
}
