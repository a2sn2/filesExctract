plugins {
    id("com.android.application")
}

// pdfbox-android still brings the pre-1.8 split Kotlin JDK artifacts while
// ML Kit brings kotlin-stdlib 1.8.x. Kotlin 1.8 merged the JDK7/JDK8 classes
// into the base stdlib, so keeping the legacy jars creates duplicate classes.
configurations.configureEach {
    exclude(group = "org.jetbrains.kotlin", module = "kotlin-stdlib-jdk7")
    exclude(group = "org.jetbrains.kotlin", module = "kotlin-stdlib-jdk8")
}

android {
    namespace = "com.filesextract.mobile"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.filesextract.mobile"
        minSdk = 26
        targetSdk = 35
        versionCode = 500
        versionName = "0.5.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // v0.5.0 is a sideload-validation release. A private production
            // signing key must never be committed to this public repository.
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    packaging {
        resources {
            excludes += setOf(
                "META-INF/DEPENDENCIES",
                "META-INF/LICENSE",
                "META-INF/LICENSE.txt",
                "META-INF/NOTICE",
                "META-INF/NOTICE.txt",
                "META-INF/INDEX.LIST"
            )
        }
    }
}

dependencies {
    // Align transitive Kotlin artifacts used by AndroidX / ML Kit / PDFBox.
    implementation(platform("org.jetbrains.kotlin:kotlin-bom:1.8.22"))

    implementation("androidx.core:core:1.15.0")
    implementation("com.google.code.gson:gson:2.11.0")
    implementation("com.tom-roush:pdfbox-android:2.0.27.0")
    implementation("com.google.mlkit:text-recognition:16.0.1")

    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
}
