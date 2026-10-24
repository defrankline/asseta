package com.asseta.owner.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.ui.components.ButtonRow
import com.asseta.core.ui.components.GroupedSection
import com.asseta.core.ui.components.NavigationChrome
import com.asseta.core.ui.components.NavigationRow
import com.asseta.core.ui.session.LocalSessionActions
import com.asseta.owner.R
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.KeyValue

/** Entries of the More tab the role may open (same gating and order as iOS `MoreView`). */
fun moreEntries(features: OwnerFeatures): List<Pair<String, OwnerDestination>> = listOfNotNull(
    ("Approvals" to OwnerDestination.Approvals()).takeIf { features.approvals },
    ("Meter exceptions" to OwnerDestination.Exceptions()).takeIf { features.meterEvidence },
    ("Field spend" to OwnerDestination.FieldSpend).takeIf { features.expenses },
    ("Cash with supervisors" to OwnerDestination.Cash).takeIf { features.finance },
    ("Investigations" to OwnerDestination.Cases).takeIf { features.cases },
    ("Notifications" to OwnerDestination.Notifications()).takeIf { features.notifications },
    "Settings" to OwnerDestination.Settings,
)

@Composable
fun MoreScreen(session: OwnerSession, unread: Int?, onOpen: (OwnerDestination) -> Unit) {
    val actions = LocalSessionActions.current
    // Same sections as iOS `MoreView`: the lists, Settings, then the company.
    val entries = moreEntries(session.features)
    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(top = 16.dp)) {
        val lists = entries.filter { it.second != OwnerDestination.Settings }
        if (lists.isNotEmpty()) {
            GroupedSection {
                lists.forEach { (label, dest) ->
                    NavigationRow(
                        label, icon = moreIcon(dest),
                        badge = NavigationChrome.badge(unread?.takeIf { dest is OwnerDestination.Notifications }),
                    ) { onOpen(dest) }
                }
            }
        }
        GroupedSection { NavigationRow("Settings", icon = R.drawable.ic_settings) { onOpen(OwnerDestination.Settings) } }
        GroupedSection(header = "Company") {
            KeyValue("Name", session.tenantName)
            if (session.readOnly) FootNote("This company is read-only. Viewing only.")
            if (session.canSwitchTenant) ButtonRow("Switch company", onClick = actions.switchTenant)
        }
    }
}

private fun moreIcon(d: OwnerDestination): Int = when (d) {
    is OwnerDestination.Approvals -> R.drawable.ic_approval
    is OwnerDestination.Exceptions -> R.drawable.ic_warning
    OwnerDestination.FieldSpend -> R.drawable.ic_receipt
    OwnerDestination.Cash -> R.drawable.ic_cash
    OwnerDestination.Cases -> R.drawable.ic_investigation
    is OwnerDestination.Notifications -> R.drawable.ic_bell
    else -> R.drawable.ic_settings
}
