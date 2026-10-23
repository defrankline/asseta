package com.asseta.owner.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Badge
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import com.asseta.core.domain.owner.DeepLinkRouter
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.ui.session.LocalSessionActions
import com.asseta.owner.OwnerGraph
import com.asseta.owner.R
import com.asseta.owner.SessionSignal
import com.asseta.owner.data.ActionResult
import com.asseta.owner.ui.common.LocalOnline

/**
 * Owner app shell for the selected tenant: bottom tabs, a back stack, live updates while started, deep links from
 * notification taps and session signals (tenant revoked / session ended) raised by data loads.
 */
@Composable
fun OwnerHome(graph: OwnerGraph, session: OwnerSession, modifier: Modifier = Modifier) {
    val tenantId = session.tenantId
    val data = remember(tenantId) { graph.data(tenantId) }
    val features = session.features
    val tabs = remember(session.permissions) { OwnerNavigation.tabs(features) }
    var stack by remember(tenantId) { mutableStateOf(listOf(OwnerNavigation.start(features))) }
    var accessLost by remember(tenantId) { mutableStateOf(false) }
    val open: (OwnerDestination) -> Unit = { stack = OwnerNavigation.navigate(stack, it) }
    val online by graph.network.online.collectAsStateWithLifecycle()
    val unread by graph.liveUpdates.unread.collectAsStateWithLifecycle()
    val actions = LocalSessionActions.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    BackHandler(enabled = stack.size > 1) { stack = OwnerNavigation.back(stack) }

    LaunchedEffect(tenantId) { lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) { graph.liveUpdates.run(tenantId) } }
    LaunchedEffect(tenantId) {
        (data.unreadCount() as? ActionResult.Done)?.let { graph.liveUpdates.setUnread(it.value.count) }
        // Re-bind an existing push registration to this tenant (never prompts; enabling happens in Settings).
        if (graph.push.available && graph.push.registeredDeviceId != null) runCatching { graph.push.register() }
    }
    LaunchedEffect(Unit) {
        graph.signals.collect {
            when (it) {
                // Explained first (as on iOS); OK re-reads `/me`, which returns to the company list.
                SessionSignal.TENANT_REVOKED -> accessLost = true
                SessionSignal.SESSION_ENDED -> actions.sessionExpired()
            }
        }
    }
    val pending by graph.pendingDeepLink.collectAsStateWithLifecycle()
    LaunchedEffect(pending, tenantId) {
        val link = pending ?: return@LaunchedEffect
        if (link.tenantId != null && link.tenantId != tenantId) {
            actions.selectTenant(link.tenantId!!)
            return@LaunchedEffect
        }
        graph.pendingDeepLink.value = null
        val resolved = link.notificationId?.let { id ->
            (data.notification(id) as? ActionResult.Done)?.value?.let { n ->
                data.markRead(listOf(id))
                DeepLinkRouter.fromTarget(n.target?.entity, n.target?.id, n.target?.path, id)
            }
        }
        open(resolved ?: link.destination)
    }

    val route = stack.last()
    val tab = OwnerNavigation.currentTab(stack)
    Scaffold(
        modifier = modifier,
        bottomBar = {
            NavigationBar {
                tabs.forEach { t ->
                    NavigationBarItem(
                        selected = t == tab,
                        onClick = { open(t.root) },
                        icon = {
                            // The More tab carries the unread count, as on iOS.
                            val badge = unread?.takeIf { t == OwnerTab.MORE && features.notifications && it > 0 }
                            BadgedBox(badge = { badge?.let { Badge { Text(if (it > 99) "99+" else "$it") } } }) {
                                Icon(painterResource(t.icon()), contentDescription = null)
                            }
                        },
                        label = { Text(t.label) },
                    )
                }
            }
        },
    ) { inner ->
        Column(Modifier.padding(inner).fillMaxSize()) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                if (stack.size > 1) TextButton(onClick = { stack = OwnerNavigation.back(stack) }) { Text("‹ Back") }
                Text(
                    OwnerNavigation.title(route, session.tenantName),
                    Modifier.weight(1f).padding(horizontal = 12.dp).semantics { heading() },
                    style = MaterialTheme.typography.titleLarge,
                )
                if (features.notifications) {
                    IconButton(onClick = { open(OwnerDestination.Notifications()) }) {
                        BadgedBox(badge = { unread?.takeIf { it > 0 }?.let { Badge { Text(if (it > 99) "99+" else "$it") } } }) {
                            Icon(painterResource(R.drawable.ic_bell), contentDescription = "Notifications" + (unread?.takeIf { it > 0 }?.let { ", $it unread" } ?: ""))
                        }
                    }
                }
            }
            CompositionLocalProvider(LocalOnline provides online) { OwnerRoutes(graph, data, session, route, online, unread, open) }
        }
    }
    if (accessLost) {
        AlertDialog(
            onDismissRequest = {},
            title = { Text("Access changed") },
            text = { Text("You no longer have access to ${session.tenantName}. Its saved data was removed from this phone.") },
            confirmButton = { TextButton(onClick = { accessLost = false; actions.refreshProfile() }) { Text("OK") } },
        )
    }
}

private fun OwnerTab.icon(): Int = when (this) {
    OwnerTab.HOME -> R.drawable.ic_nav_home
    OwnerTab.FLEET -> R.drawable.ic_nav_fleet
    OwnerTab.JOBS -> R.drawable.ic_nav_jobs
    OwnerTab.ALERTS -> R.drawable.ic_nav_alerts
    OwnerTab.MORE -> R.drawable.ic_nav_more
}
