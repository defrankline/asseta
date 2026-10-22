package com.asseta.owner.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import com.asseta.core.domain.owner.OwnerDestination

@Composable
fun MoreScreen(unread: Int?, onOpen: (OwnerDestination) -> Unit) {
    Column(Modifier.fillMaxWidth()) {
        listOf(
            "Approvals" to OwnerDestination.Approvals(),
            "Investigations" to OwnerDestination.Cases,
            "Notifications" + (unread?.takeIf { it > 0 }?.let { " ($it unread)" } ?: "") to OwnerDestination.Notifications(),
            "Settings" to OwnerDestination.Settings,
        ).forEach { (label, dest) ->
            Text(
                label,
                Modifier.fillMaxWidth().clickable(role = Role.Button) { onOpen(dest) }.padding(20.dp),
                style = MaterialTheme.typography.titleMedium,
            )
            HorizontalDivider()
        }
    }
}
