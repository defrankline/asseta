import java.util.Properties

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

// Map tiles (`asseta.mapTileUrl`, `asseta.mapAttribution`) are configured in :core:map, shared with the Supervisor app.

// Shared contract (openapi.json) is read in place by DTO tests; never copied.
val contractsDir = rootProject.layout.projectDirectory.dir("../../contracts").asFile

// Release signing: a properties file kept outside the repo (storeFile, storePassword, keyAlias, keyPassword), default
// ~/.asseta/release-signing.properties, override with -Passeta.release.signingProperties=<path>. Without it the release
// build is unsigned. The key is never committed.
val releaseSigningFile = file(
    (findProperty("asseta.release.signingProperties") as String?)
        ?: "${System.getProperty("user.home")}/.asseta/release-signing.properties"
)
val releaseSigning = Properties().apply { if (releaseSigningFile.exists()) releaseSigningFile.inputStream().use { load(it) } }

android {
    namespace = "com.asseta.owner"
    defaultConfig {
        applicationId = "com.asseta.owner"
        versionCode = 5
        versionName = "0.8.2"
        manifestPlaceholders["appAuthRedirectScheme"] = oidcRedirectScheme
        buildConfigField("String", "OIDC_REDIRECT_SCHEME", "\"$oidcRedirectScheme\"")
        buildConfigField("boolean", "FCM_ENABLED", fcmEnabled.toString())
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    signingConfigs {
        if (releaseSigning.isNotEmpty()) {
            create("release") {
                storeFile = file(releaseSigning.getProperty("storeFile"))
                storePassword = releaseSigning.getProperty("storePassword")
                keyAlias = releaseSigning.getProperty("keyAlias")
                keyPassword = releaseSigning.getProperty("keyPassword")
            }
        }
    }
    buildTypes {
        getByName("release") {
            if (releaseSigning.isNotEmpty()) signingConfig = signingConfigs.getByName("release")
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
    implementation(project(":core:push"))
    implementation(project(":core:map"))
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.kotlinx.serialization.json)
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
