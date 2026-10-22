import com.android.build.api.dsl.ApplicationExtension
import com.android.build.api.dsl.CommonExtension
import com.android.build.api.dsl.LibraryExtension
import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import org.jetbrains.kotlin.gradle.dsl.KotlinJvmProjectExtension

plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.android.library) apply false
    alias(libs.plugins.android.lint) apply false
    alias(libs.plugins.kotlin.jvm) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.ksp) apply false
    alias(libs.plugins.room) apply false
    alias(libs.plugins.google.services) apply false
}

val catalog = extensions.getByType<VersionCatalogsExtension>().named("libs")
fun v(name: String): String = catalog.findVersion(name).get().requiredVersion
val javaTarget = JavaVersion.toVersion(v("jvmTarget"))

// Shared Android configuration so supervisor/owner apps and core libraries never drift.
fun CommonExtension.assetaDefaults() {
    compileSdk = v("compileSdk").toInt()
    defaultConfig.minSdk = v("minSdk").toInt()
    defaultConfig.testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    compileOptions.sourceCompatibility = javaTarget
    compileOptions.targetCompatibility = javaTarget
    lint.abortOnError = true
    lint.warningsAsErrors = false
    lint.checkReleaseBuilds = false
    // Version bumps are a deliberate catalog decision, not a lint failure.
    lint.disable += setOf("GradleDependency", "NewerVersionAvailable", "AndroidGradlePluginVersion", "OldTargetApi")
    testOptions.unitTests.isIncludeAndroidResources = true
}

subprojects {
    pluginManager.withPlugin("com.android.library") {
        extensions.configure<LibraryExtension> {
            assetaDefaults()
            defaultConfig.consumerProguardFiles("consumer-rules.pro")
            // AppAuth's manifest needs this placeholder when library unit-test manifests are merged.
            // Test-only value: each app module sets its own redirect scheme (see app/*/build.gradle.kts).
            defaultConfig.manifestPlaceholders["appAuthRedirectScheme"] = "com.asseta.librarytest"
        }
    }
    pluginManager.withPlugin("com.android.application") {
        extensions.configure<ApplicationExtension> {
            assetaDefaults()
            defaultConfig.targetSdk = v("targetSdk").toInt()
        }
    }
    // Pure-JVM modules run standalone lint (which also scans the shared version catalog): same deliberate-pin policy.
    pluginManager.withPlugin("com.android.lint") {
        extensions.configure<com.android.build.api.dsl.Lint> {
            disable += setOf("GradleDependency", "NewerVersionAvailable", "AndroidGradlePluginVersion")
        }
    }
    pluginManager.withPlugin("org.jetbrains.kotlin.jvm") {
        extensions.configure<JavaPluginExtension> {
            sourceCompatibility = javaTarget
            targetCompatibility = javaTarget
        }
        extensions.configure<KotlinJvmProjectExtension> {
            compilerOptions.jvmTarget.set(JvmTarget.fromTarget(v("jvmTarget")))
        }
    }
    tasks.withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompilationTask<*>>().configureEach {
        compilerOptions {
            allWarningsAsErrors.set(false)
            if (this is org.jetbrains.kotlin.gradle.dsl.KotlinJvmCompilerOptions) {
                jvmTarget.set(JvmTarget.fromTarget(v("jvmTarget")))
            }
        }
    }
}
