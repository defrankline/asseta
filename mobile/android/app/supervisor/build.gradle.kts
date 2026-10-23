plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

// Per-app OIDC redirect scheme (RFC 8252 private-use scheme). Must differ between apps so the
// Keycloak callback never reaches the wrong app; registered on Keycloak client `asseta-mobile`.
val oidcRedirectScheme = "com.asseta.supervisor"

// Shared OCR fixtures (contracts/fixtures/ocr) are mounted read-only as instrumented-test assets; never copied.
val ocrFixtures = rootProject.layout.projectDirectory.dir("../../contracts/fixtures/ocr").asFile

android {
    namespace = "com.asseta.supervisor"
    defaultConfig {
        applicationId = "com.asseta.supervisor"
        versionCode = 2
        versionName = "0.4.0"
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
    sourceSets {
        named("androidTest") { assets.directories.add(ocrFixtures.absolutePath) }
    }
}

dependencies {
    implementation(project(":core:ui"))
    implementation(project(":core:sync"))
    implementation(project(":core:security"))
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.camerax.core)
    implementation(libs.camerax.camera2)
    implementation(libs.camerax.lifecycle)
    implementation(libs.camerax.view)
    implementation(libs.mlkit.text.recognition)
    implementation(libs.play.services.location)

    testImplementation(libs.junit)

    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.androidx.test.ext.junit)
    androidTestImplementation(libs.kotlinx.coroutines.test)
}
