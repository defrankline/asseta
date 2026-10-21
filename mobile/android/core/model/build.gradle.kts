plugins {
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.android.lint)
}

dependencies {
    api(libs.kotlinx.serialization.json)
    testImplementation(libs.junit)
}

// Pure-JVM module: expose its tests under the same task name the Android modules use so
// `./gradlew testDebugUnitTest` covers the whole project.
tasks.register("testDebugUnitTest") {
    group = "verification"
    description = "Runs :core:model JVM tests (alias of `test`)."
    dependsOn(tasks.named("test"))
}
