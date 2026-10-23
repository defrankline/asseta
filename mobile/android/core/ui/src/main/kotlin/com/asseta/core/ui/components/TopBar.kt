package com.asseta.core.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.asseta.core.ui.R
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette

/** Navigation-bar rules shared by both apps (the iOS `NavigationStack` behaviour). */
object NavigationChrome {
    /** iOS back button text: the previous screen's title when it is short enough, else "Back". */
    fun backLabel(previousTitle: String?): String = previousTitle?.takeIf { it.isNotBlank() && it.length <= 14 } ?: "Back"

    /** Unread count on a bell, tab or row: none when nothing is unread, capped at "99+". */
    fun badge(count: Int?): String? = when {
        count == null || count <= 0 -> null
        count > 99 -> "99+"
        else -> "$count"
    }
}

/**
 * Top bar laid out like the iOS navigation bar: on a tab's first screen ([large]) a bold 34 sp title under a row of
 * bar buttons; on a pushed screen a centred title with "‹ <previous title>" back on the left.
 */
@Composable
fun AssetaTopBar(
    title: String,
    large: Boolean,
    onBack: (() -> Unit)? = null,
    backLabel: String = "Back",
    leading: TopBarSlot? = null,
    actions: TopBarSlot = {},
) {
    val p = palette
    Column(Modifier.fillMaxWidth().background(p.groupedBackground).windowInsetsPadding(WindowInsets.statusBars)) {
        Box(Modifier.fillMaxWidth().height(44.dp)) {
            Row(Modifier.align(Alignment.CenterStart).fillMaxHeight(), verticalAlignment = Alignment.CenterVertically) {
                when {
                    onBack != null -> BackButton(backLabel, onBack)
                    leading != null -> Row(Modifier.padding(start = 4.dp), verticalAlignment = Alignment.CenterVertically, content = leading)
                }
            }
            if (!large) {
                Text(
                    title, style = AssetaType.navTitle, maxLines = 1, overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center,
                    modifier = Modifier.align(Alignment.Center).padding(horizontal = 104.dp).semantics { heading() },
                )
            }
            Row(Modifier.align(Alignment.CenterEnd).fillMaxHeight().padding(end = 4.dp), verticalAlignment = Alignment.CenterVertically, content = actions)
        }
        if (large) {
            Text(
                title, style = AssetaType.largeTitle, maxLines = 1, overflow = TextOverflow.Ellipsis,
                modifier = Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 8.dp).semantics { heading() },
            )
        }
    }
}

@Composable
private fun BackButton(label: String, onBack: () -> Unit) {
    Row(
        Modifier.fillMaxHeight().clickable(role = Role.Button, onClick = onBack).padding(start = 8.dp, end = 12.dp)
            .semantics(mergeDescendants = true) { contentDescription = "Back" },
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(painterResource(R.drawable.ic_chevron_back), contentDescription = null, tint = palette.accent, modifier = Modifier.size(22.dp))
        Text(label, style = MaterialTheme.typography.bodyLarge, color = palette.accent, maxLines = 1)
    }
}

/** Text bar button in the accent colour (iOS toolbar `Button("…")`). */
@Composable
fun BarTextButton(text: String, enabled: Boolean = true, onClick: () -> Unit) {
    Text(
        text, style = MaterialTheme.typography.bodyLarge, maxLines = 1,
        color = if (enabled) palette.accent else palette.secondaryText.copy(alpha = 0.6f),
        modifier = Modifier.clickable(enabled = enabled, role = Role.Button, onClick = onClick).padding(horizontal = 12.dp, vertical = 10.dp),
    )
}

/** Icon bar button in the accent colour with an optional count badge (e.g. the notification bell). */
@Composable
fun BarIconButton(icon: Int, contentDescription: String, badge: String? = null, onClick: () -> Unit) {
    Box(
        Modifier.size(44.dp).clickable(role = Role.Button, onClick = onClick).semantics { this.contentDescription = contentDescription },
        contentAlignment = Alignment.Center,
    ) {
        BadgedBox(badge = { badge?.let { Badge { Text(it) } } }) {
            Icon(painterResource(icon), contentDescription = null, tint = palette.accent)
        }
    }
}
