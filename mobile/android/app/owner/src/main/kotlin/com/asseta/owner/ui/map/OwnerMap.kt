package com.asseta.owner.ui.map

import android.os.Bundle
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.asseta.owner.BuildConfig
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.geometry.LatLngBounds
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.Style
import org.maplibre.android.style.expressions.Expression
import org.maplibre.android.style.layers.LineLayer
import org.maplibre.android.style.layers.Property
import org.maplibre.android.style.layers.PropertyFactory
import org.maplibre.android.style.layers.SymbolLayer
import org.maplibre.android.style.sources.GeoJsonSource
import org.maplibre.geojson.Feature
import org.maplibre.geojson.FeatureCollection
import org.maplibre.geojson.LineString
import org.maplibre.geojson.Point

/**
 * A map marker: [color] encodes connectivity, [live] solid vs dashed ring, [alerts] the open-alert badge and [code] the
 * asset code drawn under it (the list view and TalkBack label carry the same information).
 */
data class MapMarker(
    val id: String,
    val latitude: Double,
    val longitude: Double,
    val color: Color,
    val label: String,
    val code: String = "",
    val alerts: Int = 0,
    val live: Boolean = true,
)

private const val MARKERS = "markers"
private const val TRACK = "track"

/**
 * MapLibre map (raster tiles) with machine markers ([MarkerBitmap]) and an optional track polyline. Tapping a marker calls [onMarker].
 * The map is decorative for TalkBack ([description]); every screen using it also offers an accessible list.
 */
@Composable
fun OwnerMap(
    markers: List<MapMarker>,
    description: String,
    modifier: Modifier = Modifier,
    track: List<Pair<Double, Double>> = emptyList(),
    onMarker: (String) -> Unit = {},
) {
    val context = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val tap by rememberUpdatedState(onMarker)
    var map by remember { mutableStateOf<MapLibreMap?>(null) }
    var style by remember { mutableStateOf<Style?>(null) }
    val fitted = remember { arrayOfNulls<Any>(1) } // camera is fitted once per distinct marker set, not per recomposition
    val view = remember {
        MapView(context).apply {
            onCreate(Bundle())
            getMapAsync { m ->
                m.uiSettings.isRotateGesturesEnabled = false
                m.setStyle(Style.Builder().fromJson(MapSetup.styleJson())) { s ->
                    s.addSource(GeoJsonSource(TRACK, FeatureCollection.fromFeatures(emptyList())))
                    s.addLayer(LineLayer(TRACK, TRACK).withProperties(PropertyFactory.lineWidth(4f), PropertyFactory.lineColor(Color(0xFF0F2A3D).toArgb())))
                    s.addSource(GeoJsonSource(MARKERS, FeatureCollection.fromFeatures(emptyList())))
                    s.addLayer(
                        SymbolLayer(MARKERS, MARKERS).withProperties(
                            PropertyFactory.iconImage(Expression.get("icon")),
                            PropertyFactory.iconAnchor(Property.ICON_ANCHOR_TOP),
                            // Anchor at the circle centre, not the bitmap's top edge (badge space sits above it).
                            PropertyFactory.iconOffset(arrayOf(0f, -MarkerBitmap.CENTER_FROM_TOP_DP)),
                            PropertyFactory.iconAllowOverlap(true),
                            PropertyFactory.iconIgnorePlacement(true),
                        ),
                    )
                    style = s
                }
                m.addOnMapClickListener { point ->
                    val hit = m.queryRenderedFeatures(m.projection.toScreenLocation(point), MARKERS).firstOrNull()
                    hit?.getStringProperty("id")?.let { tap(it); true } ?: false
                }
                map = m
            }
        }
    }
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> view.onStart()
                Lifecycle.Event.ON_RESUME -> view.onResume()
                Lifecycle.Event.ON_PAUSE -> view.onPause()
                Lifecycle.Event.ON_STOP -> view.onStop()
                else -> Unit
            }
        }
        lifecycle.addObserver(observer)
        onDispose {
            lifecycle.removeObserver(observer)
            view.onPause()
            view.onStop()
            view.onDestroy()
        }
    }
    Box(modifier) {
        AndroidView(factory = { view }, modifier = Modifier.fillMaxSize().semantics { contentDescription = description }) {
            val s = style ?: return@AndroidView
            val m = map ?: return@AndroidView
            markers.forEach { mk ->
                val id = MarkerBitmap.imageId(mk)
                if (s.getImage(id) == null) s.addImage(id, MarkerBitmap.draw(context, mk))
            }
            s.getSourceAs<GeoJsonSource>(MARKERS)?.setGeoJson(FeatureCollection.fromFeatures(markers.map { it.toFeature() }))
            s.getSourceAs<GeoJsonSource>(TRACK)?.setGeoJson(
                if (track.size >= 2) FeatureCollection.fromFeature(Feature.fromGeometry(LineString.fromLngLats(track.map { Point.fromLngLat(it.second, it.first) })))
                else FeatureCollection.fromFeatures(emptyList()),
            )
            val key = markers.map { it.id } to track.size
            if (fitted[0] != key) {
                fitted[0] = key
                fit(m, markers.map { LatLng(it.latitude, it.longitude) } + track.map { LatLng(it.first, it.second) }, context.resources.displayMetrics.density)
            }
        }
        Surface(Modifier.align(Alignment.BottomEnd).padding(4.dp), color = MaterialTheme.colorScheme.surface.copy(alpha = 0.85f)) {
            Text(BuildConfig.MAP_ATTRIBUTION, style = MaterialTheme.typography.labelSmall, modifier = Modifier.padding(horizontal = 4.dp))
        }
    }
}

private fun MapMarker.toFeature(): Feature = Feature.fromGeometry(Point.fromLngLat(longitude, latitude)).apply {
    addStringProperty("id", id)
    addStringProperty("label", label)
    addStringProperty("icon", MarkerBitmap.imageId(this@toFeature))
}

private fun fit(map: MapLibreMap, points: List<LatLng>, density: Float) {
    when {
        points.isEmpty() -> Unit
        points.size == 1 -> map.moveCamera(CameraUpdateFactory.newLatLngZoom(points.first(), 13.0))
        else -> runCatching {
            // Padding leaves room for the marker bitmap (circle, badge and asset code) at the edges.
            map.moveCamera(CameraUpdateFactory.newLatLngBounds(LatLngBounds.Builder().includes(points).build(), (64 * density).toInt()))
        }
    }
}
