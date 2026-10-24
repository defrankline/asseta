plugins {
    alias(libs.plugins.android.library)
}

android {
    namespace = "com.asseta.core.push"
}

// App-agnostic push shared by the Owner and Supervisor apps: FCM-or-no-op token provider, `/me/push-devices`
// registration (parameterised by app), notification channels and the tray notification. Each app compiles FCM in only
// when its own google-services.json exists (BuildConfig.FCM_ENABLED) and keeps its FirebaseMessagingService.
dependencies {
    api(project(":core:network"))
    implementation(libs.androidx.core.ktx)
    implementation(libs.kotlinx.coroutines.android)
    api(libs.firebase.messaging)
}
