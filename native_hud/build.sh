#!/bin/bash
# Friday Native HUD Build Script

OUTPUT_DIR="Build"
mkdir -p $OUTPUT_DIR

echo "🚀 Compiling Friday Native HUD..."

swiftc -O \
    Sources/HUDApp.swift \
    Sources/HUDView.swift \
    -o $OUTPUT_DIR/FridayHUD \
    -sdk $(xcrun --show-sdk-path --sdk macosx) \
    -target arm64-apple-macosx14.0

if [ $? -eq 0 ]; then
    echo "✅ Build Successful: $OUTPUT_DIR/FridayHUD"
else
    echo "❌ Build Failed."
    exit 1
fi
