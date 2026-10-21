plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.serialization)
}

fun prop(name: String): String = (findProperty(name) as String?).orEmpty()

android {
    namespace = "com.asseta.core.network"
    buildFeatures { buildConfig = true }
    buildTypes {
        getByName("debug") {
            buildConfigField("String", "API_BASE_URL", "\"${prop("asseta.debug.apiBaseUrl")}\"")
            buildConfigField("boolean", "ALLOW_CLEARTEXT", "true")
        }
        getByName("release") {
            buildConfigField("String", "API_BASE_URL", "\"${prop("asseta.release.apiBaseUrl")}\"")
            buildConfigField("boolean", "ALLOW_CLEARTEXT", "false")
        }
    }
}

dependencies {
    api(project(":core:model"))
    api(libs.okhttp)
    api(libs.retrofit)
    implementation(libs.retrofit.kotlinx.serialization)

    testImplementation(libs.junit)
    testImplementation(libs.okhttp.mockwebserver)
    testImplementation(libs.kotlinx.coroutines.test)
}
