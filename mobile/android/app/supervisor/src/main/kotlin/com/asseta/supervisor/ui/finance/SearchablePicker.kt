package com.asseta.supervisor.ui.finance

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.asseta.core.domain.finance.SearchMatch

/** One choice from synced data. [keywords] are extra searchable texts (codes, contacts, ...). */
data class PickerOption(val id: String, val title: String, val subtitle: String? = null, val keywords: String? = null)

/**
 * Searchable picker over synced backend data (never a plain dropdown): a field showing the selection that opens a bottom
 * sheet with a text filter (multi-word, case/accent-insensitive via [SearchMatch]) and the matching options.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SearchablePickerField(
    label: String,
    options: List<PickerOption>,
    selectedId: String?,
    onSelect: (String?) -> Unit,
    modifier: Modifier = Modifier,
    noneLabel: String? = null,
    emptyText: String = "Nothing has been synced to this phone yet. Pull down on the home screen to sync.",
    enabled: Boolean = true,
) {
    var open by rememberSaveable { mutableStateOf(false) }
    val selected = options.firstOrNull { it.id == selectedId }
    OutlinedCard(modifier.fillMaxWidth().clickable(enabled = enabled) { open = true }) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(label, style = MaterialTheme.typography.labelMedium)
            Text(selected?.title ?: noneLabel ?: "Choose…", style = MaterialTheme.typography.bodyLarge)
            selected?.subtitle?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
        }
    }
    if (!open) return
    var query by remember { mutableStateOf("") }
    val sheet = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(onDismissRequest = { open = false }, sheetState = sheet) {
        Column(Modifier.padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(label, style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                label = { Text("Search") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            val matches = remember(options, query) {
                options.filter { SearchMatch.matches(query, it.title, it.subtitle, it.keywords) }
            }
            LazyColumn(Modifier.fillMaxWidth().heightIn(max = 420.dp)) {
                if (noneLabel != null && query.isBlank()) {
                    item { PickerRow(PickerOption("", noneLabel)) { onSelect(null); open = false } }
                }
                if (matches.isEmpty()) {
                    item { Text(if (options.isEmpty()) emptyText else "No results for \"$query\".", Modifier.padding(vertical = 16.dp)) }
                }
                items(matches, key = { it.id }) { option -> PickerRow(option) { onSelect(option.id); open = false } }
            }
        }
    }
}

@Composable
private fun PickerRow(option: PickerOption, onClick: () -> Unit) {
    Column(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 12.dp)) {
        Text(option.title, style = MaterialTheme.typography.bodyLarge)
        option.subtitle?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
    }
    HorizontalDivider()
}
