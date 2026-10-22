package com.asseta.owner.ui.map

import android.content.Context
import com.asseta.owner.BuildConfig
import okhttp3.OkHttpClient
import org.json.JSONArray
import org.json.JSONObject
import org.maplibre.android.MapLibre
import org.maplibre.android.module.http.HttpRequestUtil

/**
 * MapLibre with a raster tile source (default OSM tiles, configurable via `asseta.mapTileUrl`). No API key, no Google
 * Maps. Tile requests carry an identifying User-Agent as the OSM tile usage policy requires; nothing else is sent.
 */
object MapSetup {
    val userAgent = "AssetaOwner/${BuildConfig.VERSION_NAME} (com.asseta.owner)"

    fun init(context: Context) {
        MapLibre.getInstance(context.applicationContext)
        HttpRequestUtil.setOkHttpClient(
            OkHttpClient.Builder().addNetworkInterceptor { chain ->
                chain.proceed(chain.request().newBuilder().header("User-Agent", userAgent).build())
            }.build(),
        )
    }

    /** Minimal style: one raster source + layer. Built with JSONObject so configured values are always escaped. */
    fun styleJson(tileUrl: String = BuildConfig.MAP_TILE_URL, attribution: String = BuildConfig.MAP_ATTRIBUTION): String =
        JSONObject()
            .put("version", 8)
            .put(
                "sources",
                JSONObject().put(
                    "base",
                    JSONObject().put("type", "raster").put("tiles", JSONArray().put(tileUrl)).put("tileSize", 256)
                        .put("maxzoom", 19).put("attribution", attribution),
                ),
            )
            .put("layers", JSONArray().put(JSONObject().put("id", "base").put("type", "raster").put("source", "base")))
            .toString()
}
