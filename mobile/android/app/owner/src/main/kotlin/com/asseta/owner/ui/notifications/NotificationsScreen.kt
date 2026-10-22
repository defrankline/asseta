package com.asseta.owner.ui.notifications

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.DeepLinkRouter
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.NotificationDto
import com.asseta.core.model.owner.PageDto
import com.asseta.core.network.RealtimeEvent
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.LiveUpdates
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.filterIsInstance
import kotlinx.coroutines.launch
import java.time.ZoneId

/** Inbox: loaded over REST (durable record); new items arrive live over the WebSocket while foregrounded. */
class NotificationsViewModel(private val data: OwnerData, private val live: LiveUpdates?, refreshOn: Flow<Unit>) :
    SnapshotViewModel<PageDto<NotificationDto>>({ data.notifications() }, refreshOn) {

    init {
        live?.let { l ->
            viewModelScope.launch {
                l.events.filterIsInstance<RealtimeEvent.Notification>().collect { e -> prepend(e.notification) }
            }
        }
    }

    /** Adds a live notification at the top (ignoring one already listed). */
    fun prepend(n: NotificationDto) = replaceData { page ->
        if (page.items.any { it.id == n.id }) page else page.copy(items = listOf(n) + page.items, total = page.total + 1)
    }

    fun open(n: NotificationDto): OwnerDestination {
        if (n.readAt == null) viewModelScope.launch {
            val r = data.markRead(listOf(n.id.toString()))
            if (r is ActionResult.Done) {
                live?.setUnread(r.value.unread)
                replaceData { p -> p.copy(items = p.items.map { if (it.id == n.id) it.copy(readAt = it.createdAt) else it }) }
            }
        }
        return DeepLinkRouter.fromTarget(n.target?.entity, n.target?.id, n.target?.path, n.id.toString())
    }

    fun markAllRead() {
        viewModelScope.launch {
            val r = data.markAllRead()
            if (r is ActionResult.Done) {
                live?.setUnread(r.value.unread)
                refresh()
            }
        }
    }
}

@Composable
fun NotificationsScreen(vm: NotificationsViewModel, online: Boolean, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { page ->
        val zone = ZoneId.systemDefault()
        Column(Modifier.fillMaxSize()) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), horizontalArrangement = Arrangement.End) {
                TextButton(onClick = vm::markAllRead, enabled = online && !state.stale) { Text("Mark all read") }
            }
            LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (page.items.isEmpty()) item { Text("No notifications.") }
                items(page.items, key = { it.id.toString() }) { n ->
                    val unread = n.readAt == null
                    Card(
                        Modifier.fillMaxWidth().clickable(role = Role.Button) { onOpen(vm.open(n)) }
                            .semantics { stateDescription = if (unread) "Unread" else "Read" },
                        colors = if (unread) CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer) else CardDefaults.cardColors(),
                    ) {
                        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                StatusPill(OwnerFormat.humanize(n.severity), OwnerColors.severity(n.severity))
                                if (n.priority == "HIGH") StatusPill("High priority", OwnerColors.Critical)
                            }
                            Text(n.title, style = MaterialTheme.typography.titleSmall)
                            Text(n.body, style = MaterialTheme.typography.bodySmall)
                            Text(OwnerFormat.dateTime(n.createdAt, zone), style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
            }
        }
    }
}
