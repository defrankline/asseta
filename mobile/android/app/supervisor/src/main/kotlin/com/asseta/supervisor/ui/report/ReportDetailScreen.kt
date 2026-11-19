package com.asseta.supervisor.ui.report

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.asseta.core.domain.reports.MachineReportRules
import com.asseta.core.domain.reports.VisitPlace
import com.asseta.core.domain.reports.Visits
import com.asseta.core.model.sync.MachineReportDto
import com.asseta.core.model.sync.MachineReportLineDto
import com.asseta.core.ui.shell.PillTone
import com.asseta.core.ui.shell.SecondaryAction
import com.asseta.core.ui.shell.SectionLabel
import com.asseta.core.ui.shell.ShellCard
import com.asseta.core.ui.shell.StatusPill
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.ui.EmptyState
import com.asseta.supervisor.ui.EvidenceImage
import com.asseta.supervisor.ui.home.HomeTexts
import java.math.BigDecimal

/** Visit lines of a report (shared with the Owner app and web): since last visit, where, the last visit. */
object ReportVisitTexts {
    fun since(r: MachineReportDto): String = Visits.sinceLastVisit(r.sincePreviousVisitSeconds)

    fun where(r: MachineReportDto): VisitPlace = VisitPlace(r.visitPlace, r.visitSiteName, r.visitLat, r.visitLng, r.visitAccuracyM)

    fun previous(r: MachineReportDto): VisitPlace =
        VisitPlace(r.previousVisitPlace, r.previousVisitSiteName, r.previousVisitLat, r.previousVisitLng, r.previousVisitAccuracyM)

    fun lastVisit(r: MachineReportDto): String? = Visits.lastVisit(r.previousVisitAt, previous(r))
}

/**
 * One of my machine reports, read-only (a rejected report is final: kept as a record with the approver's reason; a new
 * report takes a new reading). [onNewReport] opens the machine report flow for its machine.
 */
@Composable
fun ReportDetailScreen(
    report: MachineReportDto?,
    photoUrl: (suspend (String) -> String?),
    onNewReport: (String) -> Unit,
) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if (report == null) {
            Column(Modifier.padding(horizontal = 16.dp)) { EmptyState(ReportTexts.TITLE, HomeTexts.NO_REPORTS) }
            return@Column
        }
        val r = report
        ShellCard {
            Row {
                Text(r.machineCode ?: r.machineName ?: r.reportNumber, fontWeight = FontWeight.Bold, fontSize = 17.sp, modifier = Modifier.weight(1f))
                StatusPill(
                    HomeTexts.reportStatus(r.status),
                    when (r.status) {
                        MachineReportDto.APPROVED -> PillTone.GOOD
                        MachineReportDto.REJECTED -> PillTone.BAD
                        else -> PillTone.WAITING
                    },
                )
            }
            Text(r.reportNumber, style = MaterialTheme.typography.bodySmall, color = palette.secondaryText)
            Text(ReportTexts.readings(r.startReading, r.endReading, r.isOpening), modifier = Modifier.padding(top = 4.dp))
            Text(Visits.dateTime(r.endAt), style = MaterialTheme.typography.bodySmall, color = palette.secondaryText)
        }
        SectionLabel(ReportTexts.VISIT)
        ShellCard {
            Text(ReportVisitTexts.since(r))
            WhereLine(ReportVisitTexts.where(r), Modifier.padding(top = 4.dp))
            ReportVisitTexts.lastVisit(r)?.let { WhereLine(ReportVisitTexts.previous(r), Modifier.padding(top = 4.dp), text = it) }
        }
        if (r.status == MachineReportDto.REJECTED) {
            ShellCard { Text(ReportTexts.rejected(r.decisionNote), color = palette.offline) }
        }
        r.photoAttachmentId?.let { id -> ShellCard { EvidenceImage(r.reportNumber, local = null, remoteUrl = { photoUrl(id) }) } }
        val customers = r.lines.filter { it.kind == MachineReportLineDto.CUSTOMER }.sortedBy { it.lineNo }
        val non = r.lines.filter { it.kind != MachineReportLineDto.CUSTOMER }.sortedBy { it.lineNo }
        if (customers.isNotEmpty()) {
            SectionLabel(ReportTexts.productive(dec(r.customerHours)))
            ShellCard { customers.forEach { Line(it.customerName ?: ReportTexts.CHOOSE_CUSTOMER, it.hours, null) } }
        }
        if (non.isNotEmpty()) {
            SectionLabel(ReportTexts.nonProductive(dec(r.nonProductiveHours)))
            ShellCard { non.forEach { Line(it.reasonName ?: ReportTexts.CHOOSE_REASON, it.hours, it.note) } }
        }
        r.note?.takeIf { it.isNotBlank() }?.let { ShellCard { Text(it, color = palette.secondaryText) } }
        if (r.status == MachineReportDto.REJECTED) {
            Column(Modifier.padding(horizontal = 20.dp)) { SecondaryAction(ReportTexts.TITLE) { onNewReport(r.machineId) } }
        }
    }
}

@Composable
private fun Line(title: String, hours: String, note: String?) {
    Column(Modifier.padding(vertical = 6.dp)) {
        Row {
            Text(title, modifier = Modifier.weight(1f))
            Text("${MachineReportRules.formatHours(dec(hours))} h", fontWeight = FontWeight.SemiBold)
        }
        note?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = palette.secondaryText) }
    }
}

private fun dec(v: String): BigDecimal = v.toBigDecimalOrNull() ?: BigDecimal.ZERO
