package com.asseta.supervisor.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.asseta.core.domain.owner.Connectivity
import com.asseta.core.map.FleetMapRules
import com.asseta.core.map.MachineMap
import com.asseta.core.map.MapMarker
import com.asseta.core.map.MapSetup
import com.asseta.core.ui.components.Pill
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.supervisor.BuildConfig
import com.asseta.supervisor.FieldGraph
import com.asseta.core.ui.R as CoreR

/** The Map / List switch over "My machines" (same look as the Owner app's Fleet screen). */
@Composable
fun MapListSwitch(showMap: Boolean, onChange: (Boolean) -> Unit, modifier: Modifier = Modifier) {
    SingleChoiceSegmentedButtonRow(modifier.fillMaxWidth()) {
        SegmentedButton(showMap, { onChange(true) }, SegmentedButtonDefaults.itemShape(0, 2)) { Text(FleetMapRules.MAP) }
        SegmentedButton(!showMap, { onChange(false) }, SegmentedButtonDefaults.itemShape(1, 2)) { Text(FleetMapRules.LIST) }
    }
}

/**
 * Map of the machines the server lets this supervisor see (`getFleetMap`, never filtered on the phone). Online only:
 * offline it says so and the List keeps working from the phone's data. Tapping a marker opens a small status card.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MyMachinesMap(field: FieldGraph, tenantId: String, online: Boolean, reloadKey: Int, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    remember { MapSetup.init(context, "AssetaSupervisor/${BuildConfig.VERSION_NAME} (com.asseta.supervisor)") }
    var retry by remember { mutableStateOf(0) }
    val state by produceState<FleetMapRules.State>(FleetMapRules.State.Loading, tenantId, online, reloadKey, retry) {
        if (online) value = FleetMapRules.State.Loading
        value = FleetMapRules.load(online, System::currentTimeMillis) { field.fleetMap() }
    }
    var selected by remember { mutableStateOf<String?>(null) }
    Box(modifier) {
        when (val s = state) {
            FleetMapRules.State.Offline -> EmptyState(FleetMapRules.MAP, FleetMapRules.OFFLINE, CoreR.drawable.ic_wifi_off)
            FleetMapRules.State.Loading -> Column(
                Modifier.fillMaxSize(), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                CircularProgressIndicator()
                Text(FleetMapRules.LOADING, Modifier.padding(top = 12.dp))
            }
            is FleetMapRules.State.Failed -> Column(
                Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                EmptyState(FleetMapRules.MAP, s.message, CoreR.drawable.ic_cloud_off)
                Button({ retry++ }) { Text(FleetMapRules.TRY_AGAIN) }
            }
            is FleetMapRules.State.Loaded -> {
                val now = System.currentTimeMillis()
                val split = FleetMapRules.split(s.machines)
                val markers = split.placed.map { m ->
                    val status = FleetMapRules.status(m, s.fetchedAtMs, now)
                    MapMarker(
                        m.machineId.toString(), m.latitude!!, m.longitude!!, connectivityColor(status.connectivity), m.name,
                        code = m.assetCode, live = status.connectivity == Connectivity.LIVE,
                    )
                }
                if (s.machines.isEmpty()) {
                    EmptyState(FleetMapRules.MAP, FleetMapRules.EMPTY)
                } else {
                    MachineMap(markers, FleetMapRules.mapDescription(markers.size), Modifier.fillMaxSize(), onMarker = { selected = it })
                    FleetMapRules.unplacedNote(split.unplaced.size)?.let {
                        Text(
                            it, style = AssetaType.caption,
                            modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 8.dp)
                                .background(palette.cell.copy(alpha = 0.92f), RoundedCornerShape(50)).padding(8.dp),
                        )
                    }
                }
                s.machines.firstOrNull { it.machineId.toString() == selected }?.let { m ->
                    val status = FleetMapRules.status(m, s.fetchedAtMs, System.currentTimeMillis())
                    ModalBottomSheet(onDismissRequest = { selected = null }) { MachineStatusCard(status) }
                }
            }
        }
    }
}

@Composable
private fun MachineStatusCard(status: FleetMapRules.Status) {
    Column(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 32.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(status.title, style = AssetaType.headline, modifier = Modifier.weight(1f))
            Pill(status.connectivity.label, connectivityColor(status.connectivity))
        }
        Text(status.lastSeen, style = AssetaType.subheadline, color = palette.secondaryText)
        Text(status.reported, style = AssetaType.subheadline, color = palette.secondaryText)
    }
}

@Composable
private fun connectivityColor(c: Connectivity): Color = when (c) {
    Connectivity.LIVE -> palette.live
    Connectivity.RECENT -> palette.recent
    Connectivity.STALE -> palette.stale
    Connectivity.OFFLINE -> palette.offline
    else -> palette.neutral
}
