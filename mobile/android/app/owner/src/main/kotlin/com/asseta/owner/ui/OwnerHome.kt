package com.asseta.owner.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.asseta.core.domain.owner.DeepLinkRouter
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.ui.components.AssetaTopBar
import com.asseta.core.ui.components.NavigationChrome
import com.asseta.core.ui.session.LocalSessionActions
import com.asseta.owner.OwnerGraph
import com.asseta.owner.SessionSignal
import com.asseta.owner.data.ActionResult
import com.asseta.owner.ui.approvals.ApprovalsViewModel
import com.asseta.owner.ui.common.LocalOnline
import com.asseta.owner.ui.settings.SettingsText
import kotlinx.coroutines.launch

/**
 * Owner app shell for the selected tenant (ADR-008, designs OwnerHome / OwnerSideNav): a sliding side menu instead of
 * bottom tabs, Home with its own top row, a back stack (side-menu destinations reset it to Home + the destination;
 * pushed screens get the top bar with back; system back pops), live updates while started, deep links from
 * notification taps and session signals (tenant revoked / session ended) raised by data loads.
 */
@Composable
fun OwnerHome(graph: OwnerGraph, session: OwnerSession, modifier: Modifier = Modifier) {
    val tenantId = session.tenantId
    val data = remember(tenantId) { graph.data(tenantId).also { it.seedSetupProgress(session.setup) } }
    val features = session.features
    var stack by remember(tenantId) { mutableStateOf(listOf(OwnerNavigation.start(features))) }
    var accessLost by remember(tenantId) { mutableStateOf(false) }
    var confirmSignOut by remember { mutableStateOf(false) }
    val drawer = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    // A destination of a capability the tenant switched off falls back (follow-up F1).
    val open: (OwnerDestination) -> Unit = { stack = OwnerNavigation.navigate(stack, features.route(it)) }
    val online by graph.network.online.collectAsStateWithLifecycle()
    val unread by graph.liveUpdates.unread.collectAsStateWithLifecycle()
    val actions = LocalSessionActions.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    // One approvals list per company, shared by the side menu badge, Home and the Approvals screen.
    val approvals: ApprovalsViewModel? = if (features.approvalsScreen) viewModel(key = "approvals-$tenantId") { approvalsViewModel(graph, data, features) } else null
    val counts = approvals?.counts?.collectAsStateWithLifecycle()?.value
    BackHandler(enabled = drawer.isOpen) { scope.launch { drawer.close() } }
    BackHandler(enabled = !drawer.isOpen && stack.size > 1) { stack = OwnerNavigation.back(stack) }

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
                DeepLinkRouter.fromTarget(n.target?.entity, n.target?.id, n.target?.path, id, n.type, n.recordKind, n.recordId)
            }
        }
        open(resolved ?: link.destination)
    }

    // Titles only a loaded record can give (a variance by its status).
    var titles by remember(tenantId) { mutableStateOf(emptyMap<OwnerDestination, String>()) }
    val route = stack.last()
    val groups = OwnerMenu.groups(features, counts?.all, unread)
    val name = session.displayName?.takeIf { it.isNotBlank() } ?: session.userEmail
    ModalNavigationDrawer(
        drawerState = drawer,
        // Swiping the menu open only from Home (maps and lists keep their own gestures elsewhere).
        gesturesEnabled = drawer.isOpen || route == OwnerDestination.Home,
        drawerContent = {
            OwnerDrawerSheet(
                name = name,
                subtitle = session.tenantName,
                groups = groups,
                footer = OwnerMenu.footer(session.canSwitchTenant),
                selected = OwnerMenu.selectedKey(OwnerNavigation.menuRoot(stack), groups),
                caption = MenuTexts.READ_ONLY.takeIf { session.readOnly },
            ) { e ->
                scope.launch { drawer.close() }
                when (e.key) {
                    MenuTexts.KEY_SWITCH -> actions.switchTenant()
                    MenuTexts.KEY_SIGN_OUT -> confirmSignOut = true
                    else -> e.destination?.let(open)
                }
            }
        },
        modifier = modifier,
    ) {
        Scaffold(
            topBar = {
                if (OwnerNavigation.hasTopBar(stack)) {
                    val previous = stack.getOrNull(stack.size - 2)
                    AssetaTopBar(
                        title = titles[route] ?: OwnerNavigation.title(route, session.tenantName),
                        large = false,
                        onBack = { stack = OwnerNavigation.back(stack) },
                        backLabel = NavigationChrome.backLabel(previous?.let { titles[it] ?: OwnerNavigation.title(it, session.tenantName) }),
                    )
                }
            },
        ) { inner ->
            Column(Modifier.padding(inner).fillMaxSize()) {
                CompositionLocalProvider(LocalOnline provides online) {
                    OwnerRoutes(
                        graph, data, session, route, online, unread, open,
                        approvals = approvals,
                        onMenu = { scope.launch { drawer.open() } },
                    ) { d, title -> titles = titles + (d to title) }
                }
            }
        }
    }
    if (confirmSignOut) {
        AlertDialog(
            onDismissRequest = { confirmSignOut = false },
            title = { Text(SettingsText.SIGN_OUT_CONFIRM) },
            text = { Text(SettingsText.SIGN_OUT_BODY) },
            confirmButton = { TextButton({ confirmSignOut = false; actions.signOut() }) { Text(SettingsText.SIGN_OUT_ACTION) } },
            dismissButton = { TextButton({ confirmSignOut = false }) { Text("Cancel") } },
        )
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
