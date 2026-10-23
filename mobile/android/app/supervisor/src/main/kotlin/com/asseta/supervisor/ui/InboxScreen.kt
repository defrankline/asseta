package com.asseta.supervisor.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.asseta.core.model.owner.NotificationDto
import com.asseta.core.sync.data.InboxSnapshot
import com.asseta.core.ui.components.ButtonRow
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette

/**
 * Inbox tab: what needs my attention (rejected expenses, flagged readings, rejected cash, refused sync items) and the
 * office's notifications (fetched online, kept on the phone for offline reading), each opening the related item.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InboxScreen(
    snapshot: InboxSnapshot,
    notifications: List<NotificationDto>,
    offline: Boolean,
    syncing: Boolean,
    onRefresh: () -> Unit,
    onNotification: (NotificationDto) -> Unit,
    onAttention: (com.asseta.core.sync.data.AttentionItem) -> Unit,
    onMarkAllRead: () -> Unit,
) {
    val attention = snapshot.attention
    PullToRefreshBox(isRefreshing = syncing, onRefresh = onRefresh, modifier = Modifier.fillMaxSize()) {
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
            if (snapshot.loaded && attention.isEmpty() && notifications.isEmpty()) {
                item(key = "empty") { EmptyState("All caught up", "Decisions from the office and items that need your attention appear here.") }
            }
            groupedSection(
                keyPrefix = "attention",
                header = if (attention.isEmpty()) null else "Needs attention",
                items = attention.map { a ->
                    GroupedItem(a.key, onClick = { onAttention(a) }) {
                        InboxRow(InboxTexts.attentionTitle(a.kind), a.status, InboxTexts.attentionDetail(a.status), LocalTime.format(a.atMs))
                    }
                },
            )
            if (notifications.isNotEmpty()) {
                val unread = notifications.count { it.readAt == null }
                groupedSection(
                    keyPrefix = "notifications",
                    header = "Notifications",
                    footer = if (offline) InboxTexts.NOTIFICATIONS_OFFLINE else null,
                    items = notifications.map { n ->
                        GroupedItem(n.id.toString(), onClick = { onNotification(n) }) { NotificationRow(n) }
                    } + if (unread > 0) listOf(GroupedItem("mark-all", chevron = false) { ButtonRow("Mark all as read", onClick = onMarkAllRead) }) else emptyList(),
                )
            } else if (offline && snapshot.loaded) {
                item(key = "offline") {
                    Text(InboxTexts.NOTIFICATIONS_OFFLINE, style = AssetaType.footnote, color = palette.secondaryText,
                        modifier = Modifier.padding(horizontal = 32.dp))
                }
            }
        }
    }
}

@Composable
private fun NotificationRow(n: NotificationDto) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.Top) {
        Box(Modifier.padding(top = 7.dp).size(8.dp).background(if (n.readAt == null) palette.accent else androidx.compose.ui.graphics.Color.Transparent, CircleShape))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(n.title, style = AssetaType.headline, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Text(n.body, style = AssetaType.subheadline, color = palette.secondaryText, maxLines = 3, overflow = TextOverflow.Ellipsis)
            Text(LocalTime.formatIso(n.createdAt), style = AssetaType.caption, color = palette.secondaryText)
        }
    }
}

/** A notification that points to nothing on the phone: its full text. */
@Composable
fun NotificationDetailScreen(n: NotificationDto?) {
    if (n == null) {
        EmptyState("Notification not available", "It is no longer on this phone.")
        return
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Section(null) {
            Text(n.title, style = AssetaType.headline)
            Text(n.body, style = AssetaType.subheadline)
            LabeledRow("Received", LocalTime.formatIso(n.createdAt))
        }
    }
}
