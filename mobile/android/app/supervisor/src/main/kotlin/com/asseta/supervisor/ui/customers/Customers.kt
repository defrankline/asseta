package com.asseta.supervisor.ui.customers

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.customers.CustomerDraft
import com.asseta.core.domain.customers.CustomerRules
import com.asseta.core.domain.finance.FormCheck
import com.asseta.core.model.sync.FieldCustomerDto
import com.asseta.core.sync.data.CustomerResult
import com.asseta.core.ui.components.GroupedItem
import com.asseta.core.ui.components.groupedSection
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.FieldGraph
import com.asseta.supervisor.R
import com.asseta.supervisor.ui.ActionRow
import com.asseta.supervisor.ui.EmptyState
import com.asseta.supervisor.ui.InboxRow
import com.asseta.supervisor.ui.LabeledRow
import com.asseta.supervisor.ui.LinkActionRow
import com.asseta.supervisor.ui.NoticeCard
import com.asseta.supervisor.ui.Route
import com.asseta.supervisor.ui.Section
import com.asseta.supervisor.ui.accountability.FormColumn
import com.asseta.supervisor.ui.finance.SaveSection
import com.asseta.supervisor.ui.finance.SaveState
import com.asseta.supervisor.ui.finance.TextInput
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Wording of the Supervisor customers screens, word for word the iOS `CustomerTexts` (strings doc "Supervisor — customers"). */
object CustomerTexts {
    const val SECTION = "Customers"
    const val ROW = "Customers"
    const val TITLE = "Customers"
    const val SEARCH = "Search by name or code"
    const val EMPTY = "No customers found."
    const val OFFLINE = "Customers need a connection. Connect to see, add or edit them."
    const val LOAD_FAILED = "The customers could not be loaded. Pull to try again."
    const val ADD = "Add a customer"
    const val TITLE_ADD = "Add a customer"
    const val TITLE_EDIT = "Edit customer"
    const val TITLE_DETAIL = "Customer"
    const val EDIT = "Edit details"
    const val CODE = "Code"
    const val NAME = "Name"
    const val TAX_ID = "Tax ID (optional)"
    const val CONTACT_NAME = "Contact name (optional)"
    const val PHONE = "Phone (optional)"
    const val EMAIL = "Email (optional)"
    const val LABEL_TAX_ID = "Tax ID"
    const val LABEL_CONTACT = "Contact"
    const val LABEL_PHONE = "Phone"
    const val LABEL_EMAIL = "Email"
    const val TERMS = "Payment terms"
    fun termsDays(n: Int) = "$n days"
    fun termsByOffice(n: Int) = "$n days · Set by the office"
    const val FOOTER = "Contracts, rates and payment terms stay with the office. Once saved, the customer is on this phone for hours sales and cash collections."
    const val SAVED = "Customer saved."
    const val STALE = "Someone else changed this customer. Reload to see it."

    /** "{code} · {contact}" under a customer's name. */
    fun rowDetail(c: FieldCustomerDto): String = listOfNotNull(c.code, c.contactName?.takeIf { it.isNotBlank() }).joinToString(" · ")

    /** The customer's details in screen order; empty values left out. */
    fun fields(c: FieldCustomerDto, termsEditable: Boolean): List<Pair<String, String>> = listOfNotNull(
        CODE to c.code,
        c.taxId?.takeIf { it.isNotBlank() }?.let { LABEL_TAX_ID to it },
        c.contactName?.takeIf { it.isNotBlank() }?.let { LABEL_CONTACT to it },
        c.contactPhone?.takeIf { it.isNotBlank() }?.let { LABEL_PHONE to it },
        c.contactEmail?.takeIf { it.isNotBlank() }?.let { LABEL_EMAIL to it },
        TERMS to if (termsEditable) termsDays(c.paymentTermsDays) else termsByOffice(c.paymentTermsDays),
    )

    /** A customer's details back in the form. */
    fun draft(c: FieldCustomerDto) = CustomerDraft(
        c.code, c.name, c.taxId.orEmpty(), c.contactName.orEmpty(), c.contactPhone.orEmpty(), c.contactEmail.orEmpty(), c.paymentTermsDays.toString(),
    )
}

/** The Money tab's "Customers" section (only for `tenant.customer.details` or `tenant.customer.write`). */
fun LazyListScope.customersSection(onRoute: (Route) -> Unit) {
    item(key = "customers") {
        Column(Modifier.padding(horizontal = 16.dp)) {
            Section(CustomerTexts.SECTION) { LinkActionRow(CustomerTexts.ROW, R.drawable.ic_account) { onRoute(Route.Customers) } }
        }
    }
}

/** One online read of a screen. */
data class CustomerScreenState<T>(val loading: Boolean = true, val data: T? = null, val offline: Boolean = false, val error: String? = null)

private fun <T> CustomerResult<T>.toState(): CustomerScreenState<T> = when (this) {
    is CustomerResult.Done -> CustomerScreenState(false, value)
    CustomerResult.Offline -> CustomerScreenState(false, offline = true)
    is CustomerResult.Refused -> CustomerScreenState(false, error = message)
}

// --- List ------------------------------------------------------------------------------------------------------------

class CustomersViewModel(private val field: FieldGraph, private val tenantId: String) : ViewModel() {
    val query = MutableStateFlow("")
    private val _state = MutableStateFlow(CustomerScreenState<List<FieldCustomerDto>>())
    val state: StateFlow<CustomerScreenState<List<FieldCustomerDto>>> = _state.asStateFlow()

    fun load() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true) }
            _state.value = field.customers.list(tenantId, query.value).toState()
        }
    }
}

@Composable
fun CustomersScreen(vm: CustomersViewModel, canEdit: Boolean, onRoute: (Route) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val query by vm.query.collectAsStateWithLifecycle()
    LaunchedEffect(query) {
        delay(300)
        vm.load()
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
        item(key = "search") {
            Column(Modifier.padding(horizontal = 16.dp)) {
                Section(null) {
                    TextInput(CustomerTexts.SEARCH, query, { vm.query.value = it }, enabled = true)
                    if (canEdit && !state.offline) ActionRow(CustomerTexts.ADD, R.drawable.ic_add) { onRoute(Route.CustomerForm(null)) }
                }
            }
        }
        when {
            state.offline -> item(key = "offline") { NoticeCard(CustomerTexts.TITLE, CustomerTexts.OFFLINE) }
            state.error != null -> item(key = "error") { NoticeCard(CustomerTexts.TITLE, state.error ?: CustomerTexts.LOAD_FAILED, isError = true) }
            state.data?.isEmpty() == true -> item(key = "empty") { EmptyState(CustomerTexts.TITLE, CustomerTexts.EMPTY) }
            else -> groupedSection(
                keyPrefix = "customers",
                items = state.data.orEmpty().map { c ->
                    GroupedItem(c.id, onClick = { onRoute(Route.CustomerDetail(c.id)) }) { InboxRow(c.name, null, CustomerTexts.rowDetail(c)) }
                },
            )
        }
    }
}

// --- Detail ----------------------------------------------------------------------------------------------------------

class CustomerDetailViewModel(private val field: FieldGraph, private val tenantId: String, val customerId: String) : ViewModel() {
    private val _state = MutableStateFlow(CustomerScreenState<FieldCustomerDto>())
    val state: StateFlow<CustomerScreenState<FieldCustomerDto>> = _state.asStateFlow()

    fun load() {
        viewModelScope.launch { _state.value = field.customers.get(tenantId, customerId).toState() }
    }
}

@Composable
fun CustomerDetailScreen(vm: CustomerDetailViewModel, permissions: Set<String>, onRoute: (Route) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    LaunchedEffect(Unit) { vm.load() } // also after coming back from the edit form
    FormColumn {
        val c = state.data
        when {
            state.offline -> NoticeCard(CustomerTexts.TITLE_DETAIL, CustomerTexts.OFFLINE)
            state.error != null -> NoticeCard(CustomerTexts.TITLE_DETAIL, state.error!!, isError = true)
            c != null -> {
                Section(c.name) { CustomerTexts.fields(c, CustomerRules.termsEditable(permissions)).forEach { (label, value) -> LabeledRow(label, value) } }
                if (CustomerRules.canEdit(permissions)) Section(null) { ActionRow(CustomerTexts.EDIT) { onRoute(Route.CustomerForm(c.id)) } }
            }
        }
    }
}

// --- Add / edit ------------------------------------------------------------------------------------------------------

/** Add ([customerId] null) or edit a customer's details online; payment terms only with `tenant.customer.write`. */
class CustomerFormViewModel(private val field: FieldGraph, private val tenantId: String, val customerId: String?, permissions: Set<String>) : ViewModel() {
    val termsEditable = CustomerRules.termsEditable(permissions)
    val draft = MutableStateFlow(CustomerDraft())
    private val _save = MutableStateFlow(SaveState())
    val save: StateFlow<SaveState> = _save.asStateFlow()
    private val _loaded = MutableStateFlow<CustomerScreenState<FieldCustomerDto>>(CustomerScreenState(loading = customerId != null))
    val loaded: StateFlow<CustomerScreenState<FieldCustomerDto>> = _loaded.asStateFlow()

    init {
        if (customerId != null) reload()
    }

    /** Reads the customer again (the form shows the server's current details and version). */
    fun reload(message: String? = null) {
        val id = customerId ?: return
        viewModelScope.launch {
            val state = field.customers.get(tenantId, id).toState()
            _loaded.value = state
            state.data?.let { draft.value = CustomerTexts.draft(it) }
            if (message != null) _save.value = SaveState(messages = listOf(message))
        }
    }

    fun edit(change: (CustomerDraft) -> CustomerDraft) {
        draft.update(change)
        _save.update { it.copy(messages = emptyList()) }
    }

    fun check() = CustomerRules.check(draft.value, termsEditable, _loaded.value.data?.paymentTermsDays ?: CustomerRules.DEFAULT_TERMS)

    fun save() {
        if (_save.value.saving || _save.value.saved) return
        val values = when (val c = check()) {
            is FormCheck.Invalid -> return _save.update { it.copy(messages = c.messages) }
            is FormCheck.Valid -> c.value
        }
        if (customerId != null && _loaded.value.data == null) return
        _save.update { it.copy(saving = true, messages = emptyList()) }
        viewModelScope.launch {
            when (val r = field.customers.save(tenantId, customerId, values, _loaded.value.data?.version)) {
                is CustomerResult.Done -> _save.value = SaveState(saved = true)
                CustomerResult.Offline -> _save.value = SaveState(messages = listOf(CustomerTexts.OFFLINE))
                is CustomerResult.Refused -> if (r.stale) reload(CustomerTexts.STALE) else _save.value = SaveState(messages = listOf(r.message))
            }
        }
    }
}

@Composable
fun CustomerFormScreen(vm: CustomerFormViewModel, onDone: () -> Unit) {
    val draft by vm.draft.collectAsStateWithLifecycle()
    val save by vm.save.collectAsStateWithLifecycle()
    val loaded by vm.loaded.collectAsStateWithLifecycle()
    val editable = !save.saving && !save.saved
    FormColumn {
        if (vm.customerId != null && loaded.data == null) {
            when {
                loaded.offline -> NoticeCard(CustomerTexts.TITLE_EDIT, CustomerTexts.OFFLINE)
                loaded.error != null -> NoticeCard(CustomerTexts.TITLE_EDIT, loaded.error!!, isError = true)
            }
            SaveSection(save, {}, onDone, enabled = false)
            return@FormColumn
        }
        Section(null, footer = CustomerTexts.FOOTER) {
            TextInput(CustomerTexts.CODE, draft.code, { v -> vm.edit { it.copy(code = v) } }, editable)
            TextInput(CustomerTexts.NAME, draft.name, { v -> vm.edit { it.copy(name = v) } }, editable)
            TextInput(CustomerTexts.TAX_ID, draft.taxId, { v -> vm.edit { it.copy(taxId = v) } }, editable)
            TextInput(CustomerTexts.CONTACT_NAME, draft.contactName, { v -> vm.edit { it.copy(contactName = v) } }, editable)
            TextInput(CustomerTexts.PHONE, draft.phone, { v -> vm.edit { it.copy(phone = v) } }, editable)
            TextInput(CustomerTexts.EMAIL, draft.email, { v -> vm.edit { it.copy(email = v) } }, editable)
            if (vm.termsEditable) {
                TextInput(CustomerTexts.TERMS, draft.termsText, { v -> vm.edit { it.copy(termsText = v.filter(Char::isDigit).take(3)) } }, editable)
            } else {
                LabeledRow(CustomerTexts.TERMS, CustomerTexts.termsByOffice(loaded.data?.paymentTermsDays ?: CustomerRules.DEFAULT_TERMS), palette.secondaryText)
            }
        }
        val check = vm.check()
        if (check is FormCheck.Invalid && (draft.code.isNotBlank() || draft.name.isNotBlank())) {
            Section(null) { check.messages.forEach { Text(it, color = palette.secondaryText) } }
        }
        SaveSection(save, vm::save, onDone, enabled = check is FormCheck.Valid)
    }
}
