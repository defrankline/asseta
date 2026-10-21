package com.asseta.supervisor.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.asseta.core.model.sync.AckMethod
import com.asseta.core.sync.usecase.WorkflowResult
import com.asseta.supervisor.FieldGraph
import kotlinx.coroutines.launch

/** Customer acknowledgement on the supervisor's phone: name confirmation or a drawn signature (no customer app). */
@Composable
fun AcknowledgementScreen(field: FieldGraph, tenantId: String, jobId: String, onDone: () -> Unit) {
    var method by remember { mutableStateOf(AckMethod.SIGNATURE) }
    var name by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var message by remember { mutableStateOf<String?>(null) }
    var saving by remember { mutableStateOf(false) }
    var saved by remember { mutableStateOf(false) }
    val signature = rememberSignatureState()
    val scope = rememberCoroutineScope()
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Customer acknowledgement", style = MaterialTheme.typography.headlineSmall)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(method == AckMethod.SIGNATURE, { method = AckMethod.SIGNATURE }, { Text("Signature") })
            FilterChip(method == AckMethod.NAME_CONFIRMATION, { method = AckMethod.NAME_CONFIRMATION }, { Text("Name confirmation") })
        }
        OutlinedTextField(name, { name = it.take(200) }, label = { Text("Customer name") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(phone, { phone = it.take(40) }, label = { Text("Phone (optional)") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone), modifier = Modifier.fillMaxWidth())
        if (method == AckMethod.SIGNATURE) {
            Text("Ask the customer to sign below.")
            SignaturePad(signature)
            TextButton(onClick = signature::clear) { Text("Clear signature") }
        }
        message?.let { NoticeCard(if (saved) "Saved" else "Check", it, isError = !saved) }
        if (saved) {
            Button(onClick = onDone, modifier = Modifier.fillMaxWidth()) { Text("Back to job") }
        } else {
            Button(
                enabled = !saving,
                modifier = Modifier.fillMaxWidth(),
                onClick = {
                    saving = true
                    val png = if (method == AckMethod.SIGNATURE) signature.toPng() else null
                    scope.launch {
                        when (val r = field.workflow.acknowledge(tenantId, jobId, method, name, phone, png)) {
                            is WorkflowResult.Done -> { saved = true; message = "Acknowledgement saved on this device." }
                            is WorkflowResult.Refused -> message = r.message
                        }
                        saving = false
                    }
                },
            ) { Text("Save acknowledgement") }
        }
    }
}
