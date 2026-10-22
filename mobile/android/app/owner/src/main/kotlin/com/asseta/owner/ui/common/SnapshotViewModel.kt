package com.asseta.owner.ui.common

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.asseta.core.domain.owner.DataSource
import com.asseta.core.ui.session.UiError
import com.asseta.owner.data.Load
import com.asseta.owner.data.Snapshot
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Screen state: the last good snapshot (live or cached/stale) plus the latest error, if any. */
data class ScreenState<out T>(val loading: Boolean = false, val snapshot: Snapshot<T>? = null, val error: UiError? = null) {
    val data: T? get() = snapshot?.data
    val stale: Boolean get() = snapshot?.source == DataSource.CACHE
}

/**
 * Loads a screen through the repository (server first, offline snapshot on network failure) and reloads on
 * [refreshOn] (WebSocket "entity changed" hints, connectivity regained). A failed reload keeps showing the previous
 * snapshot together with the error.
 */
open class SnapshotViewModel<T>(
    private val loader: suspend () -> Load<T>,
    refreshOn: Flow<Unit> = emptyFlow(),
) : ViewModel() {
    private val _state = MutableStateFlow(ScreenState<T>(loading = true))
    val state: StateFlow<ScreenState<T>> = _state.asStateFlow()
    private var job: Job? = null

    init {
        refresh()
        viewModelScope.launch { refreshOn.collect { refresh() } }
    }

    fun refresh() {
        job?.cancel()
        job = viewModelScope.launch {
            _state.update { it.copy(loading = true) }
            when (val result = loader()) {
                is Load.Ok -> _state.value = ScreenState(loading = false, snapshot = result.snapshot)
                is Load.Failed -> _state.update { it.copy(loading = false, error = result.error) }
            }
        }
    }

    /** Replaces the shown data after a successful mutation (keeps provenance). */
    protected fun replaceData(transform: (T) -> T) {
        _state.update { s -> s.snapshot?.let { s.copy(snapshot = it.copy(data = transform(it.data))) } ?: s }
    }
}
