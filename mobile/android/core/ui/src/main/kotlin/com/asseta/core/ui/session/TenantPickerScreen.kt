package com.asseta.core.ui.session

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.selectable
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.TenantAccessState
import com.asseta.core.ui.R

@Composable
fun TenantPickerScreen(state: SessionState.Ready, onSelect: (String) -> Unit, modifier: Modifier = Modifier) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text(state.me.displayName, style = MaterialTheme.typography.titleLarge)
            Text(state.me.email, style = MaterialTheme.typography.bodyMedium)
        }
        state.selectedTenant?.let { selected ->
            item {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondary)) {
                    Column(Modifier.padding(16.dp)) {
                        Text(stringResource(R.string.selected_tenant, selected.name), style = MaterialTheme.typography.titleMedium)
                        Text(stringResource(R.string.later_gates_notice), style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
        item { Text(stringResource(R.string.choose_tenant), style = MaterialTheme.typography.titleMedium) }
        if (state.me.tenants.isEmpty()) {
            item { Text(stringResource(R.string.no_tenants)) }
        }
        items(state.me.tenants, key = { it.tenantId.toString() }) { tenant ->
            TenantRow(tenant, tenant.tenantId.toString() == state.selectedTenantId) { onSelect(tenant.tenantId.toString()) }
        }
    }
}

@Composable
private fun TenantRow(tenant: TenantAccess, selected: Boolean, onClick: () -> Unit) {
    val enabled = tenant.accessState.canEnter
    Card(
        modifier = Modifier.fillMaxWidth()
            .selectable(selected = selected, enabled = enabled, role = Role.RadioButton, onClick = onClick),
    ) {
        Column(Modifier.padding(16.dp)) {
            Text(tenant.name, style = MaterialTheme.typography.titleMedium)
            Text(stringResource(R.string.tenant_status, tenant.status), style = MaterialTheme.typography.bodySmall)
            AssistChip(onClick = {}, enabled = enabled, label = { Text(stringResource(accessLabel(tenant.accessState))) })
            RadioButton(selected = selected, onClick = null, enabled = enabled)
        }
    }
}

private fun accessLabel(state: TenantAccessState): Int = when (state) {
    TenantAccessState.FULL -> R.string.access_full
    TenantAccessState.READ_ONLY -> R.string.access_read_only
    TenantAccessState.BLOCKED -> R.string.access_blocked
    TenantAccessState.UNKNOWN -> R.string.access_unknown
}
