import java.net.URI

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

val cameraApiBaseUrl = providers.gradleProperty("cameraApiBaseUrl").getOrElse("http://10.0.2.2:8000/")
val cameraApiUri = runCatching { URI(cameraApiBaseUrl) }.getOrElse { error("Invalid API base URL") }
require(cameraApiUri.scheme in listOf("http", "https") && !cameraApiUri.host.isNullOrBlank() &&
    cameraApiUri.rawUserInfo == null && cameraApiUri.rawQuery == null && cameraApiUri.rawFragment == null && cameraApiBaseUrl.endsWith("/")) {
    "API base URL must be HTTP(S), end with /, and contain no credentials, query or fragment"
}
val validateReleaseEndpoint = tasks.register("validateReleaseEndpoint") {
    val scheme = cameraApiUri.scheme
    inputs.property("apiScheme", scheme)
    doLast { require(scheme == "https") { "Release requires an HTTPS cameraApiBaseUrl" } }
}
tasks.matching { it.name == "preReleaseBuild" }.configureEach { dependsOn(validateReleaseEndpoint) }

android {
    namespace = "com.cameramonitoring.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.cameramonitoring.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField("String", "API_BASE_URL", "\"$cameraApiBaseUrl\"")
    }

    testOptions {
        unitTests {
            isReturnDefaultValues = true
        }
    }

    buildTypes {
        debug { manifestPlaceholders["allowCleartext"] = "true" }
        release {
            manifestPlaceholders["allowCleartext"] = "false"
            optimization {
                enable = false
            }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        buildConfig = true
        compose = true
    }
}

dependencies {
    constraints {
        implementation("com.google.guava:guava:33.7.2-android") {
            version { strictly("33.7.2-android") }
            because("GHSA-xxph-c9ww-hj94: use the reviewed patched Android variant")
        }
    }
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons.extended)
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.navigation.compose)

    implementation(libs.retrofit)
    implementation(libs.retrofit.converter.gson)
    implementation(libs.okhttp.logging)

    implementation(libs.firebase.messaging)
    implementation(libs.coil.compose)

    implementation(libs.media3.exoplayer)
    implementation(libs.media3.exoplayer.hls)
    implementation(libs.media3.ui)

    implementation(libs.androidx.security.crypto)

    testImplementation(libs.junit)
    testImplementation(libs.okhttp.mockwebserver)
    testImplementation(libs.mockito.core)
    testImplementation(libs.mockito.kotlin)

    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(libs.androidx.junit)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
    debugImplementation(libs.androidx.compose.ui.tooling)
}
