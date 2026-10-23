package com.asseta.owner.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Badge
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.ui.session.LocalSessionActions
import com.asseta.owner.ui.common.KeyValue

/** Entries of the More tab the role may open (same gating and order as iOS `MoreView`). */
fun moreEntries(features: OwnerFeatures): List<Pair<String, OwnerDestination>> = listOfNotNull(
    ("Approvals" to OwnerDestination.Approvals()).takeIf { features.approvals },
    ("Investigations" to OwnerDestination.Cases).takeIf { features.cases },
    ("Notifications" to OwnerDestination.Notifications()).takeIf { features.notifications },
    "Settings" to OwnerDestination.Settings,
)

@Composable
fun MoreScreen(session: OwnerSession, unread: Int?, onOpen: (OwnerDestination) -> Unit) {
    val actions = LocalSessionActions.current
    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState())) {
        moreEntries(session.features).forEach { (label, dest) ->
            Row(
                Modifier.fillMaxWidth().clickable(role = Role.Button) { onOpen(dest) }.padding(20.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(label, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                val count = unread?.takeIf { dest is OwnerDestination.Notifications && it > 0 }
                count?.let { Badge { Text(if (it > 99) "99+" else "$it") } }
            }
            HorizontalDivider()
        }
        Column(Modifier.padding(20.dp)) {
            Text("Company", style = MaterialTheme.typography.titleSmall, modifier = Modifier.semantics { heading() })
            KeyValue("Name", session.tenantName)
            if (session.readOnly) Text("This company is read-only. Viewing only.", style = MaterialTheme.typography.bodySmall)
            if (session.canSwitchTenant) OutlinedButton(onClick = actions.switchTenant) { Text("Switch company") }
        }
    }
}
