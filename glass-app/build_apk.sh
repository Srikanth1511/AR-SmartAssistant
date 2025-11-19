#!/bin/bash
# Quick build script for AR-SmartAssistant Glass App

set -e

echo "================================"
echo " Building Glass App"
echo "================================"
echo

# Check if gradlew exists
if [ ! -f "gradlew" ]; then
    echo "Error: gradlew not found. Run this from the glass-app directory."
    exit 1
fi

# Make gradlew executable
chmod +x gradlew

# Build type
BUILD_TYPE=${1:-debug}

if [ "$BUILD_TYPE" = "release" ]; then
    echo "Building RELEASE APK..."
    ./gradlew assembleRelease

    APK_PATH="app/build/outputs/apk/release/app-release-unsigned.apk"

    if [ -f "$APK_PATH" ]; then
        echo
        echo "✓ Build successful!"
        echo "APK: $APK_PATH"
        echo
        echo "Note: Release APKs must be signed before installation."
        echo "See README.md for signing instructions."
    fi

elif [ "$BUILD_TYPE" = "debug" ]; then
    echo "Building DEBUG APK..."
    ./gradlew assembleDebug

    APK_PATH="app/build/outputs/apk/debug/app-debug.apk"

    if [ -f "$APK_PATH" ]; then
        echo
        echo "✓ Build successful!"
        echo "APK: $APK_PATH"
        echo
        echo "To install on Glass:"
        echo "  adb install $APK_PATH"
    fi

else
    echo "Usage: ./build_apk.sh [debug|release]"
    exit 1
fi

echo
echo "================================"
