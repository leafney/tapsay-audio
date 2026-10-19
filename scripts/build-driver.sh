#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT="$ROOT/Driver/TapSayAudio.xcodeproj"
BUILD_ROOT="${BUILD_ROOT:-$ROOT/.build/driver}"

python3 "$ROOT/scripts/check-metadata.py"
python3 "$ROOT/scripts/generate-driver-config.py"

PRODUCT_VERSION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["product"]["version"])' "$ROOT/config/product.json")"
BUILD_NUMBER="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["product"]["build_number"])' "$ROOT/config/product.json")"
MINIMUM_MACOS="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["product"]["minimum_macos"])' "$ROOT/config/product.json")"
DRIVER_BUNDLE_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["driver"]["bundle_identifier"])' "$ROOT/config/product.json")"
FACTORY_UUID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["driver"]["plugin_factory_uuid"])' "$ROOT/config/product.json")"

for ARCH in arm64 x86_64; do
    DERIVED_DATA="$BUILD_ROOT/$ARCH"
    xcodebuild \
        -project "$PROJECT" \
        -scheme TapSayAudio \
        -configuration Release \
        -sdk macosx \
        -arch "$ARCH" \
        -derivedDataPath "$DERIVED_DATA" \
        ONLY_ACTIVE_ARCH=YES \
        CODE_SIGNING_ALLOWED=NO \
        TAPSAY_DRIVER_BUNDLE_ID="$DRIVER_BUNDLE_ID" \
        TAPSAY_PRODUCT_VERSION="$PRODUCT_VERSION" \
        TAPSAY_MINIMUM_MACOS="$MINIMUM_MACOS" \
        TAPSAY_PLUGIN_FACTORY_UUID="$FACTORY_UUID" \
        CURRENT_PROJECT_VERSION="$BUILD_NUMBER" \
        build

    python3 "$ROOT/scripts/check-driver-artifact.py" \
        "$DERIVED_DATA/Build/Products/Release/TapSayAudio.driver" \
        "$ARCH"
done
