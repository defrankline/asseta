package com.asseta.owner.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.NotificationMatrix
import com.asseta.core.domain.owner.PushCell
import com.asseta.core.model.owner.NotificationRoutingChangeIn
import com.asseta.core.model.owner.NotificationRoutingDto
import com.asseta.core.model.owner.PushDeviceDto
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.OwnerData
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Registration of this installation for push (null provider = push unavailable on this build). */
interface PushControl {
    val available: Boolean
    val providerName: String
    suspend fun register(): PushDeviceDto?
}

data class SettingsUi(
    val loading: Boolean = true,
    val original: List<PushCell> = emptyList(),
    val cells: List<PushCell> = emptyList(),
    val devices: List<PushDeviceDto> = emptyList(),
    val saving: Boolean = false,
    val message: String? = null,
    val error: String? = null,
) {
    val dirty: Boolean get() = NotificationMatrix.changes(original, cells).isNotEmpty()
}

/** Settings: push priority matrix (category x severity) and push devices. Online only; nothing is cached. */
class SettingsViewModel(private val data: OwnerData, private val push: PushControl) : ViewModel() {
    private val _ui = MutableStateFlow(SettingsUi())
    val ui: StateFlow<SettingsUi> = _ui.asStateFlow()
    private var emailByCell: Map<Pair<String, String>, Boolean> = emptyMap()

    val pushAvailable: Boolean get() = push.available
    val pushProvider: String get() = push.providerName

    init { load() }

    fun load() {
        _ui.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            when (val r = data.routing()) {
                is ActionResult.Done -> apply(r.value)
                is ActionResult.Refused -> _ui.update { it.copy(loading = false, error = r.error.message) }
            }
            loadDevices()
        }
    }

    private fun apply(rows: List<NotificationRoutingDto>) {
        emailByCell = rows.associate { (it.category to it.severity) to it.email }
        val cells = NotificationMatrix.sorted(rows.map { PushCell(it.category, it.severity, it.push, it.email, "PUSH" in it.mandatoryChannels) })
        _ui.update { it.copy(loading = false, original = cells, cells = cells) }
    }

    fun toggle(category: String, severity: String, on: Boolean) =
        _ui.update { it.copy(cells = NotificationMatrix.toggle(it.cells, category, severity, on), message = null) }

    fun save() {
        val s = _ui.value
        val changes = NotificationMatrix.changes(s.original, s.cells)
        if (changes.isEmpty() || s.saving) return
        _ui.update { it.copy(saving = true, error = null) }
        viewModelScope.launch {
            val body = changes.map { NotificationRoutingChangeIn(it.category, it.severity, it.push, emailByCell[it.category to it.severity] ?: it.email) }
            when (val r = data.updateRouting(body)) {
                is ActionResult.Done -> { apply(r.value); _ui.update { it.copy(saving = false, message = "Notification settings saved.") } }
                is ActionResult.Refused -> _ui.update { it.copy(saving = false, error = r.error.message) }
            }
        }
    }

    fun enablePush() {
        viewModelScope.launch {
            val result = runCatching { push.register() }
            _ui.update {
                it.copy(
                    message = result.getOrNull()?.let { "Push notifications enabled on this device." },
                    error = result.exceptionOrNull()?.let { "Could not register this device for push. Try again online." }
                        ?: if (result.getOrNull() == null) "Push is not available on this build." else null,
                )
            }
            loadDevices()
        }
    }

    fun deactivate(id: String) {
        viewModelScope.launch {
            when (val r = data.deactivatePushDevice(id)) {
                is ActionResult.Done -> loadDevices()
                is ActionResult.Refused -> _ui.update { it.copy(error = r.error.message) }
            }
        }
    }

    private suspend fun loadDevices() {
        (data.pushDevices() as? ActionResult.Done)?.let { r -> _ui.update { it.copy(devices = r.value) } }
    }
}
