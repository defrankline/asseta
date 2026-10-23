package com.asseta.supervisor.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.SelectableDates
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TimePicker
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.material3.rememberTimePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.ZoneOffset

/** Device-local date + time picked from a date and a time dialog, kept within [notBefore]..[notAfter] (epoch ms). */
object DateTimeRules {
    fun combine(dateUtcMidnightMs: Long, hour: Int, minute: Int, zone: ZoneId = ZoneId.systemDefault()): Long {
        val date = Instant.ofEpochMilli(dateUtcMidnightMs).atZone(ZoneOffset.UTC).toLocalDate()
        return date.atTime(hour, minute).atZone(zone).toInstant().toEpochMilli()
    }

    fun clamp(valueMs: Long, notBefore: Long?, notAfter: Long?): Long =
        valueMs.coerceAtLeast(notBefore ?: Long.MIN_VALUE).coerceAtMost(notAfter ?: Long.MAX_VALUE)
}

/** A form row showing a date and time (the iOS `DatePicker`); tapping opens the date, then the time dialog. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DateTimeField(
    label: String,
    valueMs: Long,
    onChange: (Long) -> Unit,
    enabled: Boolean = true,
    notBefore: Long? = null,
    notAfter: Long? = null,
) {
    var step by remember { mutableIntStateOf(0) } // 0 closed, 1 date, 2 time
    var pickedDate by remember { mutableStateOf<Long?>(null) }
    OutlinedCard(Modifier.fillMaxWidth().clickable(enabled = enabled) { step = 1 }) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(label, style = MaterialTheme.typography.labelMedium)
            Text(LocalTime.format(valueMs), style = MaterialTheme.typography.bodyLarge)
        }
    }
    val zone = ZoneId.systemDefault()
    val local = Instant.ofEpochMilli(valueMs).atZone(zone)
    if (step == 1) {
        val lastDay = notAfter?.let { Instant.ofEpochMilli(it).atZone(zone).toLocalDate() }
        val firstDay = notBefore?.let { Instant.ofEpochMilli(it).atZone(zone).toLocalDate() }
        val state = rememberDatePickerState(
            initialSelectedDateMillis = local.toLocalDate().atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli(),
            selectableDates = object : SelectableDates {
                override fun isSelectableDate(utcTimeMillis: Long): Boolean {
                    val day = Instant.ofEpochMilli(utcTimeMillis).atZone(ZoneOffset.UTC).toLocalDate()
                    return (lastDay == null || !day.isAfter(lastDay)) && (firstDay == null || !day.isBefore(firstDay))
                }
            },
        )
        DatePickerDialog(
            onDismissRequest = { step = 0 },
            confirmButton = { TextButton(onClick = { pickedDate = state.selectedDateMillis; step = 2 }) { Text("Next") } },
            dismissButton = { TextButton(onClick = { step = 0 }) { Text("Cancel") } },
        ) { DatePicker(state) }
    }
    if (step == 2) {
        val is24 = android.text.format.DateFormat.is24HourFormat(LocalContext.current)
        val state = rememberTimePickerState(local.hour, local.minute, is24)
        AlertDialog(
            onDismissRequest = { step = 0 },
            text = { TimePicker(state) },
            confirmButton = {
                TextButton(onClick = {
                    val date = pickedDate ?: LocalDate.now(zone).atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli()
                    onChange(DateTimeRules.clamp(DateTimeRules.combine(date, state.hour, state.minute, zone), notBefore, notAfter))
                    step = 0
                }) { Text("OK") }
            },
            dismissButton = { TextButton(onClick = { step = 0 }) { Text("Cancel") } },
        )
    }
}
