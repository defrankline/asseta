plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

// Per-app OIDC redirect scheme (RFC 8252 private-use scheme). Must differ between apps so the
// Keycloak callback never reaches the wrong app; registered on Keycloak client `asseta-mobile`.
val oidcRedirectScheme = "com.asseta.owner"

// FCM needs the Firebase project file, an external input that is never committed. Without it the FCM provider is
// compiled but disabled (BuildConfig.FCM_ENABLED=false) and the app uses the no-op push token provider.
val firebaseConfig = file("google-services.json")
val fcmEnabled = firebaseConfig.exists()
if (fcmEnabled) apply(plugin = libs.plugins.google.services.get().pluginId)

// Map tiles: OSM raster tiles by default (tile usage policy: low volume, attribution shown, identifying user agent).
// Production deployments should point this at their own/contracted tile server (README "Map tiles").
fun prop(name: String, default: String): String = (findProperty(name) as String?)?.takeIf { it.isNotBlank() } ?: default
val mapTileUrl = prop("asseta.mapTileUrl", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
val mapAttribution = prop("asseta.mapAttribution", "© OpenStreetMap contributors")

// Shared contract (openapi.json) is read in place by DTO tests; never copied.
val contractsDir = rootProject.layout.projectDirectory.dir("../../contracts").asFile

android {
    namespace = "com.asseta.owner"
    defaultConfig {
        applicationId = "com.asseta.owner"
        versionCode = 2
        versionName = "0.7.0"
        manifestPlaceholders["appAuthRedirectScheme"] = oidcRedirectScheme
        buildConfigField("String", "OIDC_REDIRECT_SCHEME", "\"$oidcRedirectScheme\"")
        buildConfigField("boolean", "FCM_ENABLED", fcmEnabled.toString())
        buildConfigField("String", "MAP_TILE_URL", "\"$mapTileUrl\"")
        buildConfigField("String", "MAP_ATTRIBUTION", "\"$mapAttribution\"")
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    buildTypes {
        getByName("release") {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    testOptions.unitTests.all { it.systemProperty("asseta.contracts.dir", contractsDir.absolutePath) }
}

dependencies {
    implementation(project(":core:ui"))
    implementation(project(":core:domain"))
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.maplibre.android)
    implementation(libs.firebase.messaging)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.robolectric)
    testImplementation(libs.androidx.test.core)
    testImplementation(libs.okhttp.mockwebserver)
    testImplementation(libs.room.runtime)
    testImplementation(platform(libs.compose.bom))
    testImplementation(libs.compose.ui.test.junit4)
    debugImplementation(libs.compose.ui.test.manifest)
}
