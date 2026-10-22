plugins {
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.android.lint)
}

dependencies {
    api(libs.kotlinx.serialization.json)
    testImplementation(libs.junit)
}

// The contract (contracts/openapi.json) is read in place by OwnerContractTest; never copied.
val contractsDir = rootProject.layout.projectDirectory.dir("../../contracts").asFile
tasks.withType<Test>().configureEach {
    systemProperty("asseta.contracts.dir", contractsDir.absolutePath)
    inputs.file(File(contractsDir, "openapi.json")).withPropertyName("openapiContract")
}

// Pure-JVM module: expose its tests under the same task name the Android modules use so
// `./gradlew testDebugUnitTest` covers the whole project.
tasks.register("testDebugUnitTest") {
    group = "verification"
    description = "Runs :core:model JVM tests (alias of `test`)."
    dependsOn(tasks.named("test"))
}
