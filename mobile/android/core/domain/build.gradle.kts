plugins {
    alias(libs.plugins.kotlin.jvm)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.android.lint)
}

// Pure-Kotlin field rules shared by every screen and by the sync engine (OCR parsing, policy snapshot selection,
// capture validation, outbox transitions, backoff, clock tamper). No Android types, so all rules are JVM-tested.
dependencies {
    api(project(":core:model"))
    testImplementation(libs.junit)
}

// The shared OCR parse cases live in the monorepo contracts; tests read them in place (never copied).
val contractsDir = rootProject.layout.projectDirectory.dir("../../contracts").asFile
tasks.withType<Test>().configureEach {
    systemProperty("asseta.contracts.dir", contractsDir.absolutePath)
    inputs.dir(File(contractsDir, "fixtures/ocr")).withPropertyName("ocrContracts")
}

tasks.register("testDebugUnitTest") {
    group = "verification"
    description = "Runs :core:domain JVM tests (alias of `test`)."
    dependsOn(tasks.named("test"))
}
