package com.asseta.supervisor.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.asseta.core.model.sync.ActivityTypes
import com.asseta.core.sync.usecase.WorkflowResult
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.ui.finance.ChoiceChips
import kotlinx.coroutines.launch

/** What the work log entry form records for the chosen type and end setting. */
enum class WorkLogEntryKind { NOTE, FINISHED, RUNNING }

object WorkLogForm {
    val TYPES = listOf(ActivityTypes.WORK, ActivityTypes.STANDBY, ActivityTypes.DOWNTIME, ActivityTypes.MOBILIZATION, ActivityTypes.NOTE)

    fun kind(type: String, hasEnded: Boolean): WorkLogEntryKind = when {
        type == ActivityTypes.NOTE -> WorkLogEntryKind.NOTE
        hasEnded -> WorkLogEntryKind.FINISHED
        else -> WorkLogEntryKind.RUNNING
    }

    /** Billable choices: null = the contract default. */
    val BILLABLE: List<Boolean?> = listOf(null, true, false)

    fun billableLabel(value: Boolean?): String = when (value) {
        null -> "Contract default"
        true -> "Yes"
        false -> "No"
    }
}

/**
 * Supervisor work log entry (`JOB_ACTIVITY`, device-generated `client_id`): a finished entry entered afterwards, a
 * running entry (stopped later on the job screen) or a note.
 */
@Composable
fun WorkLogEntryScreen(field: FieldGraph, tenantId: String, jobId: String, onDone: () -> Unit) {
    var type by remember { mutableStateOf(ActivityTypes.WORK) }
    var startedAt by remember { mutableLongStateOf(field.clock.nowMs()) }
    var hasEnded by remember { mutableStateOf(false) }
    var endedAt by remember { mutableLongStateOf(field.clock.nowMs()) }
    var billable by remember { mutableStateOf<Boolean?>(null) }
    var note by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var saving by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val kind = WorkLogForm.kind(type, hasEnded)
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Type", style = MaterialTheme.typography.titleSmall)
        ChoiceChips(WorkLogForm.TYPES, type, FieldTexts::activityType, { type = it; error = null }, enabled = !saving)
        DateTimeField("Started", startedAt, { startedAt = it; if (endedAt < it) endedAt = it }, enabled = !saving)
        if (kind != WorkLogEntryKind.NOTE) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("Has ended", style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
                Switch(hasEnded, { hasEnded = it }, enabled = !saving)
            }
            if (hasEnded) {
                DateTimeField("Ended", endedAt, { endedAt = it }, enabled = !saving, notBefore = startedAt)
                Text("Billable", style = MaterialTheme.typography.titleSmall)
                ChoiceChips(WorkLogForm.BILLABLE, billable, WorkLogForm::billableLabel, { billable = it }, enabled = !saving)
            } else {
                Text("It keeps running until you stop it.", style = MaterialTheme.typography.bodySmall)
            }
        }
        OutlinedTextField(
            note, { note = it.take(2000); error = null }, label = { Text("Note (downtime reason, issue…)") },
            modifier = Modifier.fillMaxWidth().heightIn(min = 100.dp), enabled = !saving,
        )
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(
            enabled = !saving,
            modifier = Modifier.fillMaxWidth(),
            onClick = {
                saving = true
                scope.launch {
                    val result = when (kind) {
                        WorkLogEntryKind.NOTE -> field.workflow.addNote(tenantId, jobId, note, startedAt)
                        WorkLogEntryKind.FINISHED -> field.workflow.addEntry(tenantId, jobId, type, startedAt, endedAt, billable, note)
                        WorkLogEntryKind.RUNNING -> field.workflow.startEntry(tenantId, jobId, type, note, startedAt)
                    }
                    saving = false
                    when (result) {
                        is WorkflowResult.Done -> onDone()
                        is WorkflowResult.Refused -> error = result.message
                    }
                }
            },
        ) { Text("Save") }
    }
}
