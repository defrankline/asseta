plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.serialization)
}

fun prop(name: String): String = (findProperty(name) as String?).orEmpty()

/** Web console origin for "Open on the web" links: `asseta.<type>.webBaseUrl`, else the API base URL (same host). */
fun webBase(type: String): String = prop("asseta.$type.webBaseUrl").ifEmpty { prop("asseta.$type.apiBaseUrl") }

android {
    namespace = "com.asseta.core.network"
    buildFeatures { buildConfig = true }
    buildTypes {
        getByName("debug") {
            buildConfigField("String", "API_BASE_URL", "\"${prop("asseta.debug.apiBaseUrl")}\"")
            buildConfigField("boolean", "ALLOW_CLEARTEXT", "true")
            buildConfigField("String", "WEB_BASE_URL", "\"${webBase("debug")}\"")
        }
        getByName("release") {
            buildConfigField("String", "API_BASE_URL", "\"${prop("asseta.release.apiBaseUrl")}\"")
            buildConfigField("boolean", "ALLOW_CLEARTEXT", "false")
            buildConfigField("String", "WEB_BASE_URL", "\"${webBase("release")}\"")
        }
    }
}

dependencies {
    api(project(":core:model"))
    api(libs.okhttp)
    api(libs.retrofit)
    implementation(libs.retrofit.kotlinx.serialization)
    implementation(libs.kotlinx.coroutines.core)

    testImplementation(libs.junit)
    testImplementation(libs.okhttp.mockwebserver)
    testImplementation(libs.kotlinx.coroutines.test)
}
