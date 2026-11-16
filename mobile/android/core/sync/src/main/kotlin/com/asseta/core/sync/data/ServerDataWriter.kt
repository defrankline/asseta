package com.asseta.core.sync.data

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.CashCustodyBalanceEntity
import com.asseta.core.database.ExpenseCategoryEntity
import com.asseta.core.database.FieldDataDao
import com.asseta.core.database.MachineEntity
import com.asseta.core.database.PolicySnapshotEntity
import com.asseta.core.database.ReferenceRecordEntity
import com.asseta.core.database.SyncStateEntity
import com.asseta.core.database.inTransaction
import com.asseta.core.model.sync.BootstrapDto
import com.asseta.core.model.sync.ChangesDto
import com.asseta.core.model.sync.DeviceSessionDto
import com.asseta.core.model.sync.PolicySnapshotDto
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.model.sync.SyncData
import com.asseta.core.model.sync.SyncDepositAccountDto
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.Json
import java.time.Instant
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneOffset

/** ISO-8601 parsing tolerant of `Z`, numeric offsets and (defensively) naive UTC timestamps. */
object IsoTime {
    fun parse(raw: String): Instant = runCatching { OffsetDateTime.parse(raw).toInstant() }
        .getOrElse { LocalDateTime.parse(raw).toInstant(ZoneOffset.UTC) }

    fun format(epochMs: Long): String = Instant.ofEpochMilli(epochMs).toString()
}

/**
 * Applies server snapshots/deltas to the local cache in one transaction per page, together with the cursor, so a crash
 * can never persist a cursor without its data. Server-owned rows are upserted by (id, version): newer wins.
 */
class ServerDataWriter(private val db: () -> AssetaDatabase, private val json: Json) {

    suspend fun applyRegistration(tenantId: String, session: DeviceSessionDto) {
        val database = db()
        database.inTransaction {
            val states = database.syncStateDao()
            val current = states.get(tenantId) ?: SyncStateEntity(tenantId)
            states.put(
                current.copy(
                    deviceSessionId = session.id,
                    offlineGrantUntil = IsoTime.parse(session.offlineGrantUntil).toEpochMilli(),
                ),
            )
        }
    }

    suspend fun applyBootstrap(tenantId: String, dto: BootstrapDto, receivedElapsedMs: Long) {
        val database = db()
        database.inTransaction {
            val field = database.fieldDataDao()
            val categories = dto.data.expenseCategories.map { it.id }
            val finance = database.financeDataDao()
            if (categories.isEmpty()) finance.deleteAllCategories(tenantId) else finance.deleteCategoriesNotIn(tenantId, categories)
            // The bootstrap inbox is the server's full window: start it afresh (later pages arrive as changes).
            if (SyncCapabilities.SUPERVISOR_INBOX_V1 in dto.capabilities) database.inboxDao().deleteTenant(tenantId)
            // Deposit accounts in the bootstrap are the full list: accounts no longer delivered leave the picker.
            dto.data.depositAccounts?.let { accounts ->
                val keepAccounts = accounts.map { it.id }
                if (keepAccounts.isEmpty()) field.deleteReferencesOfKind(tenantId, KIND_DEPOSIT_ACCOUNT)
                else field.deleteReferencesNotIn(tenantId, KIND_DEPOSIT_ACCOUNT, keepAccounts)
            }
            applyData(database, tenantId, dto.data)
            replacePettyCash(database, tenantId, dto.capabilities, dto.data)
            replaceHoursPrices(database, tenantId, dto.capabilities, dto.data)
            replaceMachineReports(database, tenantId, dto.capabilities, dto.data)
            applySnapshots(database, tenantId, dto.policySnapshots)
            val states = database.syncStateDao()
            val current = states.get(tenantId) ?: SyncStateEntity(tenantId)
            states.put(
                current.copy(
                    capabilities = dto.capabilities.joinToString(","),
                    tenantTimezone = dto.tenantTimezone ?: current.tenantTimezone,
                    deviceSessionId = dto.deviceSession.id,
                    offlineGrantUntil = IsoTime.parse(dto.deviceSession.offlineGrantUntil).toEpochMilli(),
                    cursor = dto.cursor,
                    serverTime = IsoTime.parse(dto.serverTime).toEpochMilli(),
                    serverTimeElapsed = receivedElapsedMs,
                ),
            )
        }
    }

    suspend fun applyChanges(tenantId: String, dto: ChangesDto, receivedElapsedMs: Long) {
        val database = db()
        database.inTransaction {
            applyData(database, tenantId, dto.data)
            replacePettyCash(database, tenantId, dto.capabilities, dto.data)
            replaceHoursPrices(database, tenantId, dto.capabilities, dto.data)
            replaceMachineReports(database, tenantId, dto.capabilities, dto.data)
            applySnapshots(database, tenantId, dto.policySnapshots)
            val states = database.syncStateDao()
            val current = states.get(tenantId) ?: SyncStateEntity(tenantId)
            states.put(
                current.copy(
                    capabilities = dto.capabilities.joinToString(","),
                    tenantTimezone = dto.tenantTimezone ?: current.tenantTimezone,
                    cursor = maxOf(dto.cursor, current.cursor ?: 0),
                    serverTime = IsoTime.parse(dto.serverTime).toEpochMilli(),
                    serverTimeElapsed = receivedElapsedMs,
                ),
            )
        }
    }

    private suspend fun applyData(database: AssetaDatabase, tenantId: String, data: SyncData) {
        val field = database.fieldDataDao()
        field.upsertMachines(
            data.machines.map { MachineEntity(it.id, tenantId, it.assetCode, it.name, it.meterDecimalPlaces, it.status, it.version) },
        )
        val refs = data.sites.map { ref(KIND_SITE, it.id, tenantId, it.name, json.encodeToString(it)) } +
            data.customers.map { ref(KIND_CUSTOMER, it.id, tenantId, it.name, json.encodeToString(it)) } +
            data.staff.map { ref(KIND_STAFF, it.id, tenantId, it.fullName, json.encodeToString(it)) }
        if (refs.isNotEmpty()) field.upsertReferences(refs)
        applyDepositAccounts(database, tenantId, data.depositAccounts.orEmpty())
        applyFinance(database, tenantId, data)
        InboxWriter(json).apply(database, tenantId, data)
    }

    /**
     * Petty cash (OP_PETTY_CASH, DEC-033) is a full snapshot on every pull: each local set is replaced. Without the
     * capability (switched off, or an older server) nothing of it is kept on the phone.
     */
    private suspend fun replacePettyCash(database: AssetaDatabase, tenantId: String, capabilities: List<String>, data: SyncData) {
        val field = database.fieldDataDao()
        val on = SyncCapabilities.OP_PETTY_CASH in capabilities
        val sets = listOf(
            KIND_PETTY_FUND to (if (on) data.pettyCashFunds.map { ref(KIND_PETTY_FUND, it.id, tenantId, it.name, json.encodeToString(it)) } else emptyList()),
            KIND_PETTY_AWAITING to (if (on) data.pettyCashAwaiting.map { ref(KIND_PETTY_AWAITING, it.id, tenantId, it.number, json.encodeToString(it)) } else emptyList()),
            KIND_PETTY_HOLDER_CHANGE to (if (on) data.pettyCashHolderChanges.map { ref(KIND_PETTY_HOLDER_CHANGE, it.id, tenantId, it.fundName.orEmpty(), json.encodeToString(it)) } else emptyList()),
            KIND_PETTY_ADVANCE to (if (on) data.pettyCashAdvances.map { ref(KIND_PETTY_ADVANCE, it.id, tenantId, it.number, json.encodeToString(it)) } else emptyList()),
            KIND_PETTY_WITNESS to (if (on) data.pettyCashWitnesses.map { ref(KIND_PETTY_WITNESS, it.userId, tenantId, it.name, json.encodeToString(it)) } else emptyList()),
        )
        sets.forEach { (kind, rows) ->
            keepOnly(field, tenantId, kind, rows.map { it.id })
            if (rows.isNotEmpty()) field.upsertReferences(rows)
        }
    }

    /**
     * Hours-sale prices (SYNC_HOURS_PRICES) are full snapshots on every pull: machine rates (keyed by machine) and
     * customer discounts (keyed by customer) replace the local sets. Without the capability nothing of them is kept.
     */
    private suspend fun replaceHoursPrices(database: AssetaDatabase, tenantId: String, capabilities: List<String>, data: SyncData) {
        val field = database.fieldDataDao()
        val on = SyncCapabilities.SYNC_HOURS_PRICES in capabilities
        val sets = listOf(
            KIND_HOURS_PRICE to (if (on) data.hoursPrices.map { ref(KIND_HOURS_PRICE, it.machineId, tenantId, it.currency, json.encodeToString(it)) } else emptyList()),
            KIND_CUSTOMER_DISCOUNT to (if (on) data.customerDiscounts.map { ref(KIND_CUSTOMER_DISCOUNT, it.customerId, tenantId, it.percent, json.encodeToString(it)) } else emptyList()),
        )
        sets.forEach { (kind, rows) ->
            keepOnly(field, tenantId, kind, rows.map { it.id })
            if (rows.isNotEmpty()) field.upsertReferences(rows)
        }
    }

    /**
     * ADR-008 machine reports (OP_MACHINE_REPORT) and open credit invoices (OP_CREDIT_INVOICE_PAYMENT) are full
     * snapshots on every pull: each local set is replaced. Without the capability nothing of them is kept.
     */
    private suspend fun replaceMachineReports(database: AssetaDatabase, tenantId: String, capabilities: List<String>, data: SyncData) {
        val field = database.fieldDataDao()
        val reports = SyncCapabilities.OP_MACHINE_REPORT in capabilities
        val invoices = SyncCapabilities.OP_CREDIT_INVOICE_PAYMENT in capabilities
        val sets = listOf(
            KIND_REPORT_REASON to (if (reports) data.machineReportReasons.map { ref(KIND_REPORT_REASON, it.id, tenantId, it.name, json.encodeToString(it)) } else emptyList()),
            KIND_REPORT_STATE to (if (reports) data.machineReportStates.map { ref(KIND_REPORT_STATE, it.machineId, tenantId, it.machineCode.orEmpty(), json.encodeToString(it)) } else emptyList()),
            KIND_REPORT_HOURS to (if (reports) data.machineReportHours.map { ref(KIND_REPORT_HOURS, hoursKey(it.customerId, it.machineId), tenantId, it.customerName.orEmpty(), json.encodeToString(it)) } else emptyList()),
            KIND_MY_REPORT to (if (reports) data.myMachineReports.map { ref(KIND_MY_REPORT, it.id, tenantId, it.submittedAt, json.encodeToString(it)) } else emptyList()),
            KIND_CREDIT_INVOICE to (if (invoices) data.openCreditInvoices.map { ref(KIND_CREDIT_INVOICE, it.id, tenantId, it.dueDate, json.encodeToString(it)) } else emptyList()),
        )
        sets.forEach { (kind, rows) ->
            keepOnly(field, tenantId, kind, rows.map { it.id })
            if (rows.isNotEmpty()) field.upsertReferences(rows)
        }
    }

    /** Deposit accounts upsert by sync revision (an older revision never replaces a newer one; deactivations kept). */
    private suspend fun applyDepositAccounts(database: AssetaDatabase, tenantId: String, accounts: List<SyncDepositAccountDto>) {
        if (accounts.isEmpty()) return
        val field = database.fieldDataDao()
        val newer = accounts.filter { incoming ->
            val stored = field.reference(KIND_DEPOSIT_ACCOUNT, incoming.id)?.let {
                runCatching { json.decodeFromString(SyncDepositAccountDto.serializer(), it.json) }.getOrNull()
            }
            stored == null || incoming.syncRevision >= stored.syncRevision
        }
        if (newer.isNotEmpty()) field.upsertReferences(newer.map { ref(KIND_DEPOSIT_ACCOUNT, it.id, tenantId, it.name, json.encodeToString(it)) })
    }

    private suspend fun keepOnly(field: FieldDataDao, tenantId: String, kind: String, ids: List<String>) {
        if (ids.isEmpty()) field.deleteReferencesOfKind(tenantId, kind) else field.deleteReferencesNotIn(tenantId, kind, ids)
    }

    /** Expense categories upsert by sync revision (deactivations arrive as is_active=false); custody is replaced. */
    private suspend fun applyFinance(database: AssetaDatabase, tenantId: String, data: SyncData) {
        val finance = database.financeDataDao()
        if (data.expenseCategories.isNotEmpty()) {
            finance.upsertCategories(
                data.expenseCategories.map {
                    ExpenseCategoryEntity(it.id, tenantId, it.code, it.name, it.isActive, it.syncRevision, it.version)
                },
            )
        }
        val custody = data.cashCustody ?: return // field absent: keep what we have
        val now = System.currentTimeMillis()
        finance.replaceCustody(
            tenantId,
            custody.map {
                CashCustodyBalanceEntity(
                    tenantId = tenantId, currency = it.currency, staffMemberId = it.staffMemberId,
                    outstanding = it.outstanding.toPlainString(),
                    claimedUnverifiedHandovers = it.claimedUnverifiedHandovers.toPlainString(),
                    pendingSpending = it.pendingSpending.toPlainString(),
                    asOf = IsoTime.parse(it.asOf).toEpochMilli(), receivedAt = now,
                )
            },
        )
    }

    private suspend fun applySnapshots(database: AssetaDatabase, tenantId: String, snapshots: List<PolicySnapshotDto>) {
        if (snapshots.isEmpty()) return
        val now = System.currentTimeMillis()
        database.fieldDataDao().upsertSnapshots(
            snapshots.map {
                PolicySnapshotEntity(
                    tenantId = tenantId,
                    policyType = it.policyType,
                    scopeKey = it.scopeKey,
                    versionIdsJson = json.encodeToString(ListSerializer(String.serializer()), it.versionIds),
                    versionStamp = it.versionStamp,
                    valuesJson = json.encodeToString(it.values),
                    validUntil = IsoTime.parse(it.validUntil).toEpochMilli(),
                    receivedAt = now,
                )
            },
        )
    }

    private fun ref(kind: String, id: String, tenantId: String, title: String, body: String) =
        ReferenceRecordEntity(kind, id, tenantId, title, body)

    companion object {
        const val KIND_SITE = "site"
        const val KIND_CUSTOMER = "customer"
        const val KIND_STAFF = "staff"
        const val KIND_DEPOSIT_ACCOUNT = "deposit_account"
        const val KIND_PETTY_FUND = "petty_cash_fund"
        const val KIND_PETTY_AWAITING = "petty_cash_awaiting"
        const val KIND_PETTY_HOLDER_CHANGE = "petty_cash_holder_change"
        const val KIND_PETTY_ADVANCE = "petty_cash_advance"
        const val KIND_PETTY_WITNESS = "petty_cash_witness"
        const val KIND_HOURS_PRICE = "hours_price"
        const val KIND_CUSTOMER_DISCOUNT = "customer_discount"
        const val KIND_REPORT_REASON = "machine_report_reason"
        const val KIND_REPORT_STATE = "machine_report_state"
        const val KIND_REPORT_HOURS = "machine_report_hours"
        const val KIND_MY_REPORT = "my_machine_report"
        const val KIND_CREDIT_INVOICE = "open_credit_invoice"

        /** Key of an available-hours row: the customer, per machine when the company's report scope is MACHINE. */
        fun hoursKey(customerId: String, machineId: String?) = if (machineId == null) customerId else "$customerId:$machineId"
    }
}
