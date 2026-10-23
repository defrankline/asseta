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
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.DataSource
import com.asseta.core.domain.owner.DeepLinkRouter
import com.asseta.core.domain.owner.FailureKind
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.NotificationDto
import com.asseta.core.model.owner.PageDto
import com.asseta.core.network.RealtimeEvent
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.LiveUpdates
import com.asseta.owner.data.Load
import com.asseta.owner.data.OwnerData
import com.asseta.owner.data.Snapshot
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.OwnerColors
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.StatusPill
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.filterIsInstance
import kotlinx.coroutines.launch
import java.time.ZoneId

/** Inbox wording shared with iOS (`NotificationsView`). */
object InboxText {
    const val EMPTY_TITLE = "No notifications"
    const val NO_TARGET = "Open the web console for details."

    fun visible(items: List<NotificationDto>, unreadOnly: Boolean): List<NotificationDto> = if (unreadOnly) items.filter { it.readAt == null } else items
}

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

/** One notification without an in-app screen (opened from a push or the inbox): fetched online, never cached. */
class NotificationDetailViewModel(data: OwnerData, id: String) : SnapshotViewModel<NotificationDto>({
    when (val r = data.notification(id)) {
        is ActionResult.Done -> Load.Ok(Snapshot(r.value, System.currentTimeMillis(), DataSource.LIVE))
        is ActionResult.Refused -> Load.Failed(r.error, FailureKind.NETWORK)
    }
})

@Composable
fun NotificationsScreen(vm: NotificationsViewModel, online: Boolean, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    var unreadOnly by rememberSaveable { mutableStateOf(false) }
    SnapshotScaffold(state, vm::refresh) { page ->
        val zone = ZoneId.systemDefault()
        val items = InboxText.visible(page.items, unreadOnly)
        Column(Modifier.fillMaxSize()) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("Unread only", Modifier.weight(1f))
                Switch(unreadOnly, { unreadOnly = it })
                TextButton(onClick = vm::markAllRead, enabled = online && !state.stale && page.items.any { it.readAt == null }) { Text("Mark all read") }
            }
            LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (items.isEmpty()) item { EmptyState(InboxText.EMPTY_TITLE) }
                items(items, key = { it.id.toString() }) { n ->
                    val unread = n.readAt == null
                    Card(
                        Modifier.fillMaxWidth().clickable(role = Role.Button) { onOpen(vm.open(n)) }
                            .semantics { stateDescription = if (unread) "Unread" else "Read" },
                        colors = if (unread) CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer) else CardDefaults.cardColors(),
                    ) { NotificationRow(n, zone, Modifier.padding(12.dp)) }
                }
            }
        }
    }
}

@Composable
fun NotificationRow(n: NotificationDto, zone: ZoneId, modifier: Modifier = Modifier) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            // INFO is the default and carries no pill (same as iOS); priority is called out when high.
            if (n.severity != "INFO") StatusPill(OwnerFormat.humanize(n.severity), OwnerColors.severity(n.severity))
            if (n.priority == "HIGH") StatusPill("High priority", OwnerColors.Critical)
        }
        Text(n.title, style = if (n.readAt == null) MaterialTheme.typography.titleSmall else MaterialTheme.typography.bodyLarge)
        Text(n.body, style = MaterialTheme.typography.bodySmall, maxLines = 3)
        Text(OwnerFormat.dateTime(n.createdAt, zone), style = MaterialTheme.typography.labelSmall)
    }
}

@Composable
fun NotificationDetailScreen(vm: NotificationDetailViewModel) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { n ->
        Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Card(Modifier.fillMaxWidth()) { NotificationRow(n, ZoneId.systemDefault(), Modifier.padding(12.dp)) }
            FootNote(InboxText.NO_TARGET)
        }
    }
}
