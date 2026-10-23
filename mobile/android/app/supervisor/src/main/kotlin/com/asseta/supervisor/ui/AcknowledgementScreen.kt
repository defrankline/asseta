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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
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

/**
 * Customer acknowledgement on the supervisor's phone: typed name confirmation, or a signature drawn on the phone (PNG
 * stored as evidence and uploaded with purpose SIGNATURE). No external customer app.
 */
@Composable
fun AcknowledgementScreen(field: FieldGraph, tenantId: String, jobId: String, onDone: () -> Unit) {
    var method by remember { mutableStateOf(AckMethod.SIGNATURE) }
    var name by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var hours by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var saving by remember { mutableStateOf(false) }
    val signature = rememberSignatureState()
    val scope = rememberCoroutineScope()
    val canSave = name.isNotBlank() && (method != AckMethod.SIGNATURE || !signature.isEmpty) && !saving
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            listOf(AckMethod.SIGNATURE to "Signature", AckMethod.NAME_CONFIRMATION to "Name confirmation").forEachIndexed { i, (value, label) ->
                SegmentedButton(method == value, { method = value }, SegmentedButtonDefaults.itemShape(i, 2)) { Text(label) }
            }
        }
        OutlinedTextField(name, { name = it.take(200) }, label = { Text("Customer representative's name") }, singleLine = true,
            modifier = Modifier.fillMaxWidth())
        OutlinedTextField(phone, { phone = it.take(40) }, label = { Text("Phone (optional)") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone), modifier = Modifier.fillMaxWidth())
        OutlinedTextField(hours, { hours = it.filter { c -> c.isDigit() || c == '.' || c == ',' } }, label = { Text("Hours acknowledged (optional)") },
            singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), modifier = Modifier.fillMaxWidth())
        if (method == AckMethod.SIGNATURE) {
            Section("Signature", footer = "Ask the customer to sign with a finger.") {
                SignaturePad(signature)
                Row { TextButton(onClick = signature::clear) { Text("Clear", color = MaterialTheme.colorScheme.error) } }
            }
        }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(
            enabled = canSave,
            modifier = Modifier.fillMaxWidth(),
            onClick = {
                saving = true
                val png = if (method == AckMethod.SIGNATURE) signature.toPng() else null
                scope.launch {
                    when (val r = field.workflow.acknowledge(tenantId, jobId, method, name, phone, png, hours)) {
                        is WorkflowResult.Done -> onDone()
                        is WorkflowResult.Refused -> error = r.message
                    }
                    saving = false
                }
            },
        ) { Text("Save") }
    }
}
