package com.asseta.core.model

import kotlinx.serialization.Serializable
import kotlinx.serialization.SerialName

/** Mirrors the backend `ErrorEnvelope`: `{"error":{"code","message","correlation_id","details":[...]}}`. */
@Serializable
data class ErrorEnvelope(val error: ErrorBody)

@Serializable
data class ErrorBody(
    val code: String,
    val message: String,
    @SerialName("correlation_id") val correlationId: String,
    val details: List<ErrorDetail> = emptyList(),
)

@Serializable
data class ErrorDetail(val field: String? = null, val issue: String)
