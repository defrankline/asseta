package com.asseta.owner.ui.accountability

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.TenantAccess
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.AccountabilitySummaryDto
import com.asseta.core.model.owner.CountAmountDto
import com.asseta.core.ui.components.NavigationRow
import com.asseta.owner.data.OwnerData
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.common.EmptyState
import com.asseta.owner.ui.common.FootNote
import com.asseta.owner.ui.common.KeyValue
import com.asseta.owner.ui.common.SectionCard
import com.asseta.owner.ui.common.SnapshotScaffold
import com.asseta.owner.ui.common.SnapshotViewModel
import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import java.time.ZoneId

private val T = OwnerAccountabilityTexts

/** One dashboard tile: its rows and the list it opens (when the Owner app has one and the role may open it). */
data class DashboardTile(
    val key: String,
    val title: String,
    val rows: List<Pair<String, String>>,
    val link: OwnerDestination? = null,
    val footer: String? = null,
    /** Further lists the tile opens (label -> destination), e.g. today's overdue remittances from the cash tile. */
    val moreLinks: List<Pair<String, OwnerDestination>> = emptyList(),
)

/** Pure presentation of `AccountabilitySummaryDto` (unit-tested): null tiles (hidden / unavailable) are skipped. */
object DashboardPresentation {
    private fun money(c: CountAmountDto): String = T.count(c.count, c.amount.toBigDecimalOrNull()?.let { OwnerFormat.money(it, c.currency) } ?: "${c.amount} ${c.currency}")

    private fun amounts(list: List<CountAmountDto>): String = if (list.isEmpty()) T.DASH_NONE else list.joinToString(", ", transform = ::money)

    /** Hours figures in the phone's number format, 0–2 decimals (same as the customer-hours screens and iOS). */
    private fun num(raw: String?): String = OwnerFormat.hoursNumber(raw)

    private fun JsonObject.text(key: String): String? = (this[key] as? JsonPrimitive)?.contentOrNull
    private fun JsonObject.int(key: String): Int? = (this[key] as? JsonPrimitive)?.intOrNull
    private fun JsonObject.items(): List<JsonObject> = (this["items"] as? JsonArray).orEmpty().mapNotNull { it as? JsonObject }

    fun tiles(s: AccountabilitySummaryDto, sessionFeatures: OwnerFeatures): List<DashboardTile> = buildList {
        // Switched-off capabilities from `/me` and from the summary itself (follow-up F1).
        val features = sessionFeatures.without(s.disabledCapabilities)
        val cashOn = features.cashCustody
        val engineOn = features.engineHours
        val approvals = OwnerDestination.Approvals().takeIf { features.approvals || features.finance || features.meterEvidence || features.customerHours }
        val hoursOff = TenantAccess.CUSTOMER_HOURS in features.disabled
        s.outstandingApprovals?.let { a ->
            add(
                DashboardTile(
                    "approvals", T.DASH_APPROVALS,
                    listOf(
                        T.DASH_TOTAL to "${a.total}", T.DASH_APPROVAL_REQUESTS to "${a.approvalRequests}", T.DASH_PAYMENTS_TO_VERIFY to "${a.paymentsToVerify}",
                        T.DASH_REMITTANCES_TO_VERIFY to "${a.remittancesToVerify}",
                    ) + if (cashOn) {
                        listOf(T.DASH_CASH_RETENTIONS to "${a.cashRetentions}", T.DASH_CUSTODY_ADJUSTMENTS to "${a.custodyAdjustments}", T.DASH_WRITE_OFFS to "${a.writeOffs}")
                    } else {
                        emptyList()
                    },
                    approvals,
                ),
            )
        }
        s.cash?.let { c ->
            // CASH_CUSTODY off: only the cash basics (remittances awaiting confirmation, what each custodian holds).
            val chain = if (cashOn) {
                listOf(T.DASH_TRANSFERS_AWAITING to amounts(c.transfersAwaitingAcknowledgement), T.DASH_FLOATS_AWAITING to amounts(c.floatsAwaitingAcknowledgement))
            } else {
                emptyList()
            }
            val rows = chain + listOf(T.DASH_REMITTANCES_AWAITING to amounts(c.remittancesAwaitingConfirmation)) +
                listOfNotNull(
                    (T.DASH_PARTIAL_REMITTANCES to "${c.partialRemittancesInWindow}").takeIf { cashOn },
                    c.remittancesOverdueToday?.takeIf { cashOn }?.let { T.DASH_REMITTANCES_OVERDUE to "$it" },
                ) + c.custodians.map { k ->
                val line = k.outstanding.toBigDecimalOrNull()?.let { OwnerFormat.money(it, k.currency) } ?: k.outstanding
                val transit = k.inTransitOut.toBigDecimalOrNull()?.takeIf { it.signum() != 0 }?.let { T.inTransit(OwnerFormat.money(it, k.currency)) }
                k.staffName to listOfNotNull(T.custodianLine(line), transit).joinToString(" · ")
            }
            // Remittance cut-off (null = the tenant has none): today's overdue count opens the flagged custodians.
            val overdue = c.remittancesOverdueToday?.takeIf { features.finance && cashOn }?.let { listOf(T.DASH_REMITTANCES_OVERDUE to OwnerDestination.RemittanceOverdue()) }
            add(
                DashboardTile(
                    "cash", T.DASH_CASH, rows, OwnerDestination.Cash.takeIf { features.finance },
                    footer = c.remittanceCutoffHour?.takeIf { cashOn && c.remittancesOverdueToday != null }?.let(T::dashCutoff),
                    moreLinks = overdue.orEmpty(),
                ),
            )
        }
        s.payments?.let { add(DashboardTile("payments", T.DASH_PAYMENTS, listOf(T.DASH_PAYMENTS to amounts(it.awaitingConfirmation)))) }
        s.discrepancies?.let { d ->
            add(
                DashboardTile(
                    "discrepancies", T.DASH_DISCREPANCIES,
                    (if (cashOn) listOf(T.DASH_OPEN_VARIANCES to amounts(d.openVariances), T.DASH_WRITE_OFFS_PROPOSED to "${d.writeOffsProposed}") else emptyList()) +
                        listOf(T.DASH_SYNC_CONFLICTS to "${d.syncConflictsUnresolved}"),
                    approvals,
                ),
            )
        }
        s.investigations?.let { i ->
            add(DashboardTile("investigations", T.DASH_INVESTIGATIONS, listOf(T.DASH_OPEN to "${i.open}", T.DASH_IN_REVIEW to "${i.inReview}"),
                OwnerDestination.Cases.takeIf { features.cases }))
        }
        s.unauthorizedAttempts?.let { a ->
            add(DashboardTile("attempts", T.DASH_ATTEMPTS, listOf(T.DASH_PERMISSION_DENIED to "${a.permissionDenied}", T.DASH_SOD to "${a.segregationOfDuties}"),
                footer = T.window(a.windowDays)))
        }
        s.customerHours?.takeUnless { hoursOff }?.let { h ->
            add(
                DashboardTile(
                    "customer_hours", T.DASH_CUSTOMER_HOURS,
                    listOf(
                        T.DASH_HOURS_ACTIVATED to num(h.text("activated")), T.DASH_HOURS_CONSUMED to num(h.text("consumed")),
                        T.DASH_HOURS_REMAINING to num(h.text("remaining")), T.DASH_HOURS_AWAITING to num(h.text("awaiting_activation")),
                        T.DASH_HOURS_EXPIRED to num(h.text("expired")), T.DASH_OPEN_OVERRUNS to "${h.int("open_overruns") ?: 0}",
                    ),
                ),
            )
        }
        s.hoursAwaitingActivation?.takeUnless { hoursOff }?.let { h ->
            add(
                DashboardTile(
                    "hours_awaiting_activation", T.DASH_HOURS_AWAITING_TILE,
                    listOf(T.F_HOURS to num(h.text("hours")), T.DASH_PURCHASES_AWAITING_PAYMENT to "${h.int("purchases_awaiting_payment") ?: 0}",
                        T.DASH_PURCHASES_PARTLY_ACTIVE to "${h.int("purchases_partly_active") ?: 0}"),
                ),
            )
        }
        s.engineHours?.takeIf { engineOn }?.let { e ->
            val byStatus = (e["by_status"] as? JsonObject).orEmpty().map { (k, v) -> T.reconciliationStatus(k) to ((v as? JsonPrimitive)?.contentOrNull ?: "0") }
            add(DashboardTile("engine_hours", T.DASH_ENGINE_HOURS, listOf(T.DASH_MACHINES to "${e.int("machines") ?: 0}") + byStatus))
        }
        s.unexplainedHours?.takeIf { engineOn }?.let { u ->
            val rows = listOf(T.F_HOURS to num(u.text("hours"))) + u.items().map {
                (it.text("machine_code") ?: "") to T.unexplainedLine(num(it.text("unexplained_hours")), it.int("oldest_open_item_days"))
            }
            add(DashboardTile("unexplained_hours", T.DASH_UNEXPLAINED, rows, OwnerDestination.Exceptions().takeIf { features.meterEvidence }))
        }
        s.missingDailyReports?.takeIf { engineOn }?.let { m ->
            val items = m.items()
            val rows = if (items.isEmpty()) listOf(T.DASH_MISSING_REPORTS to T.DASH_NONE) else items.map {
                T.missingLine(it.text("machine_code").orEmpty(), it.text("day").orEmpty()) to ""
            }
            add(DashboardTile("missing_daily_reports", T.DASH_MISSING_REPORTS, rows))
        }
        // DEC-031 R3: revenue differences (REVENUE_RECONCILIATION on and the role may read them).
        if (features.revenueRead) {
            RevenuePresentation.tile(s.revenueDifferences)?.let(::add)
        }
        // DEC-031 M2: unbilled work and idle machines (their lists need tenant.oversight.read).
        s.unbilledWork?.let { OversightPresentation.unbilledTile(it, features) }?.let(::add)
        s.idleMachines?.let { OversightPresentation.idleTile(it, features) }?.let(::add)
    }
}

class AccountabilityViewModel(data: OwnerData, refreshOn: Flow<Unit>) : SnapshotViewModel<AccountabilitySummaryDto>({ data.accountabilitySummary() }, refreshOn)

@Composable
fun AccountabilityScreen(vm: AccountabilityViewModel, features: OwnerFeatures, onOpen: (OwnerDestination) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    SnapshotScaffold(state, vm::refresh) { summary ->
        val zone = ZoneId.systemDefault()
        val tiles = DashboardPresentation.tiles(summary, features)
        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
            if (tiles.isEmpty()) item { EmptyState(T.DASH_EMPTY) }
            tiles.forEach { tile ->
                item(key = tile.key) {
                    SectionCard(tile.title, footer = tile.footer) {
                        tile.rows.forEach { (label, value) -> KeyValue(label, value) }
                        tile.link?.let { dest -> NavigationRow(tile.title) { onOpen(dest) } }
                        tile.moreLinks.forEach { (label, dest) -> NavigationRow(label) { onOpen(dest) } }
                    }
                }
            }
            item(key = "footer") {
                SectionCard(null) {
                    if (summary.hiddenTiles.isNotEmpty()) FootNote(T.DASH_HIDDEN)
                    FootNote(T.dashFooter(summary.policyVersion, OwnerFormat.dateTime(summary.asOf, zone)))
                }
            }
        }
    }
}
