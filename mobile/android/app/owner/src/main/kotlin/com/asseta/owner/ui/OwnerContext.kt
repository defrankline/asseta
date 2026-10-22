package com.asseta.owner.ui

import com.asseta.core.domain.owner.DataSource
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.MutationGate
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.network.RealtimeEvent
import com.asseta.owner.OwnerGraph
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.flow.drop
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.filterIsInstance
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.merge

/** The selected tenant as the Owner UI needs it. Permissions only hide/disable UI; the server decides. */
data class OwnerSession(
    val tenantId: String,
    val tenantName: String,
    val permissions: Set<String>,
    val readOnly: Boolean,
) {
    fun can(action: OwnerAction, online: Boolean, source: DataSource?): MutationCheck =
        MutationGate.check(action, online, source ?: DataSource.CACHE, permissions, readOnly)
}

/**
 * Reload triggers for a screen: WebSocket "entity changed" frames for [entities] and connectivity coming back.
 * Debounced so a burst of position updates causes one reload.
 */
@OptIn(FlowPreview::class)
fun OwnerGraph.refreshTriggers(vararg entities: String, debounceMs: Long = 1_500): Flow<Unit> {
    val set = entities.toSet()
    val changes = liveUpdates.events.filterIsInstance<RealtimeEvent.EntityChanged>().filter { it.entity in set }.map { }
    val reconnected = network.online.drop(1).filter { it }.map { }
    return merge(changes, reconnected).debounce(debounceMs)
}
