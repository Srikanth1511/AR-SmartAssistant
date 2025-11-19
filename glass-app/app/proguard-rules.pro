# Add project specific ProGuard rules here.
# You can control the set of applied configuration files using the
# proguardFiles setting in build.gradle.
#
# For more details, see
#   http://developer.android.com/guide/developing/tools/proguard.html

# Keep WebSocket classes
-keep class org.java_websocket.** { *; }

# Keep data classes
-keep class com.arsmartassistant.glass.model.** { *; }

# Keep service classes
-keep class com.arsmartassistant.glass.service.** { *; }

# Keep Timber
-dontwarn org.jetbrains.annotations.**
