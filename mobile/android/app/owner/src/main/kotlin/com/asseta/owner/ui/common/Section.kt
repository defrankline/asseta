package com.asseta.owner.ui.common

import com.asseta.owner.data.Load
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** One independently loaded part of a composite screen (a failing part never hides the others). */
class Section<T>(private val scope: CoroutineScope, private val loader: suspend () -> Load<T>) {
    private val _state = MutableStateFlow(ScreenState<T>(loading = true))
    val state: StateFlow<ScreenState<T>> = _state.asStateFlow()
    private var job: Job? = null

    fun refresh() {
        job?.cancel()
        job = scope.launch {
            _state.update { it.copy(loading = true) }
            when (val r = loader()) {
                is Load.Ok -> _state.value = ScreenState(false, r.snapshot)
                is Load.Failed -> _state.update { it.copy(loading = false, error = r.error) }
            }
        }
    }
}
