package com.asseta.core.network

import com.asseta.core.model.owner.NotificationDto
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.flowOn
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.util.concurrent.TimeUnit

/** Frames of the `/api/v1/ws` gateway (protocol `asseta.v1`, docs/api.md) that clients act on. */
sealed interface RealtimeEvent {
    data class Connected(val unreadCount: Int?) : RealtimeEvent
    data class Notification(val notification: NotificationDto) : RealtimeEvent
    data class UnreadCount(val count: Int) : RealtimeEvent
    /** An entity changed server-side (`alert`, `approval`, `job`, `fleet.position`, `case`, ...): open screens reload. */
    data class EntityChanged(val entity: String, val id: String?, val action: String?) : RealtimeEvent
    /** Server asked for a fresh token (~60 s before expiry). */
    data object ReauthRequired : RealtimeEvent
    data object Ping : RealtimeEvent
    /** `auth_error` (then close 4401/4403): [code] is the stable error code. */
    data class AuthError(val code: String, val message: String) : RealtimeEvent
}

/** Pure message codec (JVM-tested). Unknown frames decode to null and are ignored. */
object RealtimeProtocol {
    const val SUBPROTOCOL = "asseta.v1"
    const val CLOSE_AUTH = 4401
    const val CLOSE_ACCESS = 4403
    const val CLOSE_IDLE = 4408

    /** Sub-protocol header value; the token never goes into the URL. */
    fun protocolHeader(token: String): String = "$SUBPROTOCOL, bearer.$token"

    fun subscribe(tenantId: String): String = buildJsonObject {
        put("type", "subscribe")
        putJsonObject("scope") { put("kind", "tenant"); put("tenantId", tenantId) }
    }.toString()

    fun auth(token: String, tenantId: String): String =
        buildJsonObject { put("type", "auth"); put("token", token); put("tenant_id", tenantId) }.toString()

    const val PONG = """{"type":"pong"}"""

    /** Close codes after which reconnecting cannot help until the session/tenant changes. */
    fun isFatalClose(code: Int): Boolean = code == CLOSE_ACCESS

    fun parse(text: String, json: Json): RealtimeEvent? = runCatching {
        val frame = json.parseToJsonElement(text).jsonObject
        val payload = frame["payload"] as? JsonObject
        when (frame["type"]?.jsonPrimitive?.contentOrNull) {
            "auth_ok" -> RealtimeEvent.Connected(payload?.get("unread_count")?.jsonPrimitive?.intOrNull)
            "notification" -> payload?.let { RealtimeEvent.Notification(json.decodeFromJsonElement<NotificationDto>(it)) }
            "unread_count" -> payload?.get("count")?.jsonPrimitive?.intOrNull?.let { RealtimeEvent.UnreadCount(it) }
            "entity.changed" -> payload?.get("entity")?.jsonPrimitive?.contentOrNull?.let {
                RealtimeEvent.EntityChanged(it, payload["id"]?.jsonPrimitive?.contentOrNull, payload["action"]?.jsonPrimitive?.contentOrNull)
            }
            "reauth_required" -> RealtimeEvent.ReauthRequired
            "ping" -> RealtimeEvent.Ping
            "auth_error" -> RealtimeEvent.AuthError(
                payload?.get("code")?.jsonPrimitive?.contentOrNull ?: "AUTH_ERROR",
                payload?.get("message")?.jsonPrimitive?.contentOrNull ?: "",
            )
            else -> null
        }
    }.getOrNull()
}

/** Raised when the socket ends; [code] is the WebSocket close code (null for a transport failure). */
class RealtimeClosed(val code: Int?, reason: String?) : Exception(reason ?: "WebSocket closed ($code)")

/**
 * One tenant-scoped WebSocket session. The returned flow emits frames until the socket ends, then fails with
 * [RealtimeClosed] (or completes when the collector cancels, which closes the socket). Heartbeat pings are answered
 * here; reconnection policy (backoff, foreground only) belongs to the caller. Uses its own plain OkHttp client: the
 * REST interceptors would treat the `101 Switching Protocols` upgrade as an error.
 */
class RealtimeSocket(
    baseUrl: String,
    allowCleartext: Boolean,
    private val tokens: AccessTokenProvider,
    private val json: Json = NetworkFactory.json,
    private val client: OkHttpClient = OkHttpClient.Builder().readTimeout(0, TimeUnit.MILLISECONDS).build(),
) {
    private val url = baseUrl.toHttpUrl().newBuilder().addPathSegments("api/v1/ws").build().also {
        require(allowCleartext || it.isHttps) { "Release builds require a secure WebSocket (wss) endpoint" }
    }

    fun connect(tenantId: String): Flow<RealtimeEvent> = callbackFlow {
        val token = tokens.accessToken() ?: throw RealtimeClosed(RealtimeProtocol.CLOSE_AUTH, "Not signed in")
        val request = Request.Builder().url(url).header("Sec-WebSocket-Protocol", RealtimeProtocol.protocolHeader(token)).build()
        val socket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                webSocket.send(RealtimeProtocol.subscribe(tenantId))
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                when (val event = RealtimeProtocol.parse(text, json)) {
                    null -> Unit
                    RealtimeEvent.Ping -> webSocket.send(RealtimeProtocol.PONG)
                    RealtimeEvent.ReauthRequired -> tokens.accessToken()?.let { webSocket.send(RealtimeProtocol.auth(it, tenantId)) }
                    else -> trySend(event)
                }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(code, null)
                close(RealtimeClosed(code, reason))
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                close(RealtimeClosed(null, t.message))
            }
        })
        awaitClose { socket.close(NORMAL_CLOSURE, null) }
    }.flowOn(Dispatchers.IO)

    private companion object {
        const val NORMAL_CLOSURE = 1000
    }
}
