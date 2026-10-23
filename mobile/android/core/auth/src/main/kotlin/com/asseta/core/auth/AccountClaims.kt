package com.asseta.core.auth

import com.asseta.core.model.SyncAccount
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.util.Base64

/**
 * Reads who is signed in from a token's claims (`sub`, plus `email`/`preferred_username`/`name` as a readable label).
 * Only identifies the owner of local data on this phone; authorization stays on the server.
 */
object AccountClaims {
    fun fromJwt(token: String?): SyncAccount? {
        val parts = token?.split('.') ?: return null
        if (parts.size != 3) return null
        val claims = runCatching {
            val payload = String(Base64.getUrlDecoder().decode(parts[1].trimEnd('=')), Charsets.UTF_8)
            Json.parseToJsonElement(payload).jsonObject
        }.getOrNull() ?: return null
        val subject = claims.text("sub") ?: return null
        return SyncAccount(subject, claims.text("email") ?: claims.text("preferred_username") ?: claims.text("name"))
    }

    private fun JsonObject.text(key: String): String? =
        runCatching { this[key]?.jsonPrimitive?.contentOrNull }.getOrNull()?.takeIf { it.isNotBlank() }
}
