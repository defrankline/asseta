plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.compose)
}

// Machine map shared by the Owner and Supervisor apps: MapLibre with raster tiles (no API key, no Google Maps), the
// machine marker bitmap and the fleet map rules (who sees the map, placed vs unplaced machines, online only).
// Map tiles: OSM raster tiles by default (tile usage policy: low volume, attribution shown, identifying user agent).
// Production deployments should point this at their own/contracted tile server (README "Map tiles").
fun prop(name: String, default: String): String = (findProperty(name) as String?)?.takeIf { it.isNotBlank() } ?: default
val mapTileUrl = prop("asseta.mapTileUrl", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
val mapAttribution = prop("asseta.mapAttribution", "© OpenStreetMap contributors")

android {
    namespace = "com.asseta.core.map"
    defaultConfig {
        buildConfigField("String", "MAP_TILE_URL", "\"$mapTileUrl\"")
        buildConfigField("String", "MAP_ATTRIBUTION", "\"$mapAttribution\"")
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    api(project(":core:domain"))
    implementation(project(":core:ui"))
    implementation(project(":core:network"))
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.maplibre.android)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
}
