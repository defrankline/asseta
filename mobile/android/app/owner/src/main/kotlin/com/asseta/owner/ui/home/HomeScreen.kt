package com.asseta.owner.ui.home

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.OverviewSeverityCountsDto
import com.asseta.core.model.owner.TenantOverviewDto
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import com.asseta.owner.ui.common.freshnessLine
import kotlinx.coroutines.flow.Flow

class HomeViewModel(data: OwnerData, refreshOn: Flow<Unit>) : SnapshotViewModel<TenantOverviewDto>({ data.overview() }, refreshOn)

/** Dashboard: overview KPIs per permitted section, each with the freshness of its source data. */
@Composable
fun HomeScreen(vm: HomeViewModel, tenantName: String, now: () -> Long, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { o ->
        val zone = OwnerFormat.zone(o.timezone)
        val nowMs = now()
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                Text(tenantName, style = MaterialTheme.typography.titleLarge)
                Text("Figures as of ${OwnerFormat.dateTime(o.asOf, zone)} (${o.timezone})", style = MaterialTheme.typography.bodySmall)
            }
            o.fleet?.let { f ->
                item {
                    SectionCard("Fleet", freshnessLine(f.latestSourceAt, nowMs)) {
                        KeyValue("Machines", f.machines.toString())
                        KeyValue("Reporting live / recent", "${f.connectivity.live} / ${f.connectivity.recent}")
                        KeyValue("Stale / offline", "${f.connectivity.stale} / ${f.connectivity.offline}")
                        KeyValue("Never reported / no tracker", "${f.connectivity.never} / ${f.connectivity.noTracker}")
                        KeyValue("Engine on (tracker verified)", f.engineOnVerified.toString())
                        f.reportedWorkState.forEach { (k, v) -> KeyValue("Reported ${OwnerFormat.humanize(k).lowercase()}", v.toString()) }
                        Severity("Open alerts", f.openAlerts)
                        TextButton(onClick = { onOpen(OwnerDestination.Fleet) }) { Text("Open fleet map") }
                        TextButton(onClick = { onOpen(OwnerDestination.Alerts()) }) { Text("Open alerts") }
                    }
                }
            }
            o.work?.let { w ->
                item {
                    SectionCard("Jobs and work", freshnessLine(w.latestSourceAt, nowMs)) {
                        w.jobsByStatus.forEach { (k, v) -> KeyValue(OwnerFormat.humanize(k), v.toString()) }
                        w.pendingApprovals?.let {
                            Text(
                                "Pending approvals: $it",
                                modifier = Modifier.clickable { onOpen(OwnerDestination.Approvals()) },
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.primary,
                            )
                        }
                        w.openExceptions?.let { KeyValue("Open meter exceptions", it.toString()) }
                        w.readingsNeedingReview?.let { KeyValue("Readings needing review", it.toString()) }
                        TextButton(onClick = { onOpen(OwnerDestination.Jobs) }) { Text("Open jobs") }
                    }
                }
            }
            o.money?.let { m ->
                item {
                    SectionCard("Money (month from ${m.monthStart})", freshnessLine(m.latestSourceAt, nowMs)) {
                        if (m.currencies.isEmpty()) Text("No financial activity yet.")
                        m.currencies.forEach { c ->
                            Text(c.currency, style = MaterialTheme.typography.titleSmall)
                            KeyValue("Receivables outstanding", OwnerFormat.money(c.receivablesOutstanding.value, c.currency))
                            KeyValue("Overdue (${c.overdueInvoices} invoices)", OwnerFormat.money(c.receivablesOverdue.value, c.currency))
                            KeyValue("Verified receipts this month", OwnerFormat.money(c.verifiedReceiptsMtd.value, c.currency))
                            KeyValue("Approved expenses this month", OwnerFormat.money(c.approvedExpensesMtd.value, c.currency))
                            KeyValue("Cash with supervisors", OwnerFormat.money(c.cashWithSupervisors.value, c.currency))
                        }
                    }
                }
            }
            o.risk?.let { r ->
                item {
                    SectionCard("Investigations and signals", freshnessLine(r.latestSourceAt, nowMs)) {
                        r.openCases?.let { Severity("Open cases", it) }
                        r.signalsLast7Days?.let { Severity("Signals (last 7 days)", it) }
                        TextButton(onClick = { onOpen(OwnerDestination.Cases) }) { Text("Open investigations") }
                    }
                }
            }
            if (o.fleet == null && o.work == null && o.money == null && o.risk == null) {
                item { Text("Your role has no dashboard sections in this company.") }
            }
        }
    }
}

@Composable
private fun Severity(label: String, counts: OverviewSeverityCountsDto) {
    KeyValue(label, "${counts.total} (critical ${counts.critical}, warning ${counts.warning}, info ${counts.info})")
}
