package com.asseta.core.ui.session

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.TenantAccessState
import com.asseta.core.ui.R
import com.asseta.core.ui.components.EmptyState
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.Pill
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.theme.AssetaPalette
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette

/** "Choose a company" (iOS `TenantPickerView`): one row per membership with its status and access badge. */
@Composable
fun TenantPickerScreen(state: SessionState.Ready, onSelect: (String) -> Unit, modifier: Modifier = Modifier) {
    val p = palette
    val header = stringResource(R.string.choose_tenant)
    LazyColumn(modifier = modifier.fillMaxSize(), contentPadding = PaddingValues(top = 16.dp, bottom = 16.dp)) {
        if (state.me.tenants.isEmpty()) {
            item { EmptyState(stringResource(R.string.no_tenants_title), stringResource(R.string.no_tenants), icon = R.drawable.ic_business) }
        } else {
            groupedSection(
                "tenants",
                state.me.tenants.map { tenant ->
                    val enabled = tenant.accessState.canEnter
                    GroupedItem(tenant.tenantId.toString(), onClick = if (enabled) ({ onSelect(tenant.tenantId.toString()) }) else null, chevron = false) {
                        TenantRow(tenant, enabled, p)
                    }
                },
                header = header,
            )
        }
    }
}

@Composable
private fun TenantRow(tenant: TenantAccess, enabled: Boolean, p: AssetaPalette) {
    val alpha = if (enabled) 1f else 0.45f
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(tenant.name, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurface.copy(alpha = alpha))
            Text(tenant.status.lowercase().replaceFirstChar { it.uppercase() }, style = AssetaType.caption,
                color = p.secondaryText.copy(alpha = alpha))
        }
        Pill(stringResource(accessLabel(tenant.accessState)), accessColor(tenant.accessState, p))
    }
}

private fun accessLabel(state: TenantAccessState): Int = when (state) {
    TenantAccessState.FULL -> R.string.access_full
    TenantAccessState.READ_ONLY -> R.string.access_read_only
    TenantAccessState.BLOCKED -> R.string.access_blocked
    TenantAccessState.UNKNOWN -> R.string.access_unknown
}

private fun accessColor(state: TenantAccessState, p: AssetaPalette): Color = when (state) {
    TenantAccessState.FULL -> p.live
    TenantAccessState.READ_ONLY -> p.stale
    else -> p.offline
}
