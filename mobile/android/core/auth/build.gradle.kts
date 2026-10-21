plugins {
    alias(libs.plugins.android.library)
}

fun prop(name: String): String = (findProperty(name) as String?).orEmpty()

android {
    namespace = "com.asseta.core.auth"
    buildFeatures { buildConfig = true }
    defaultConfig {
        buildConfigField("String", "OIDC_CLIENT_ID", "\"asseta-mobile\"")
    }
    buildTypes {
        getByName("debug") {
            buildConfigField("String", "KEYCLOAK_ISSUER", "\"${prop("asseta.debug.keycloakIssuer")}\"")
            buildConfigField("boolean", "ALLOW_INSECURE_HTTP", "true")
        }
        getByName("release") {
            buildConfigField("String", "KEYCLOAK_ISSUER", "\"${prop("asseta.release.keycloakIssuer")}\"")
            buildConfigField("boolean", "ALLOW_INSECURE_HTTP", "false")
        }
    }
}

dependencies {
    api(project(":core:network"))
    implementation(project(":core:security"))
    api(libs.appauth)
    implementation(libs.androidx.core.ktx)
    implementation(libs.kotlinx.coroutines.android)

    testImplementation(libs.junit)
}
