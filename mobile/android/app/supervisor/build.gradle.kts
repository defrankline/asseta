plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

// Per-app OIDC redirect scheme (RFC 8252 private-use scheme). Must differ between apps so the
// Keycloak callback never reaches the wrong app; registered on Keycloak client `asseta-mobile`.
val oidcRedirectScheme = "com.asseta.supervisor"

android {
    namespace = "com.asseta.supervisor"
    defaultConfig {
        applicationId = "com.asseta.supervisor"
        versionCode = 1
        versionName = "0.1.0"
        manifestPlaceholders["appAuthRedirectScheme"] = oidcRedirectScheme
        buildConfigField("String", "OIDC_REDIRECT_SCHEME", "\"$oidcRedirectScheme\"")
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
}

dependencies {
    implementation(project(":core:ui"))
    implementation(libs.androidx.core.ktx)
}
