package com.asseta.owner.data

import com.asseta.core.domain.sync.Backoff
import com.asseta.core.network.RealtimeClosed
import com.asseta.core.network.RealtimeEvent
import com.asseta.core.network.RealtimeProtocol
import com.asseta.core.network.RealtimeSocket
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlin.random.Random

/**
 * Live updates over `/api/v1/ws` while the app is in the foreground: notifications, unread count and
 * "entity changed" hints that make open screens reload. Reconnects with jittered backoff (2 s .. 60 s); stops on an
 * access refusal (4403). The inbox stays the durable record, so missed frames only delay a refresh.
 */
class LiveUpdates(private val socket: RealtimeSocket, private val backoff: Backoff = Backoff(2_000, 60_000)) {
    private val _events = MutableSharedFlow<RealtimeEvent>(extraBufferCapacity = 64)
    val events: SharedFlow<RealtimeEvent> = _events.asSharedFlow()

    private val _unread = MutableStateFlow<Int?>(null)
    val unread: StateFlow<Int?> = _unread.asStateFlow()

    private val _connected = MutableStateFlow(false)
    val connected: StateFlow<Boolean> = _connected.asStateFlow()

    fun setUnread(count: Int) {
        _unread.value = count
    }

    /** Runs until cancelled (call from a lifecycle-scoped coroutine: STARTED). */
    suspend fun run(tenantId: String) {
        var failures = 0
        try {
            while (true) {
                try {
                    socket.connect(tenantId).collect { event ->
                        failures = 0
                        when (event) {
                            is RealtimeEvent.Connected -> { _connected.value = true; event.unreadCount?.let { _unread.value = it } }
                            is RealtimeEvent.UnreadCount -> _unread.value = event.count
                            is RealtimeEvent.Notification -> if (event.notification.readAt == null) _unread.value = (_unread.value ?: 0) + 1
                            else -> Unit
                        }
                        _events.tryEmit(event)
                    }
                } catch (e: CancellationException) {
                    throw e
                } catch (e: RealtimeClosed) {
                    if (e.code != null && RealtimeProtocol.isFatalClose(e.code!!)) return
                } catch (_: Exception) {
                    // transport failure: retry below
                }
                _connected.value = false
                failures++
                delay(backoff.delayFor(failures, Random.nextDouble()))
            }
        } finally {
            _connected.value = false
        }
    }
}
