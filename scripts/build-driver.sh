#!/bin/bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
test "$#" = 0 || { echo "正式构建不接受 profile 或架构参数" >&2; exit 2; }
export LC_ALL=C
python3 "$root/scripts/check-metadata.py"

mkdir -p "$root/.build"
work="$(mktemp -d "$root/.build/tapsay-driver-arm64.XXXXXX")"
source="$work/source"
python3 "$root/scripts/prepare-driver-source.py" "$source"
python3 "$root/scripts/check-reference-source.py" "$source" > "$work/reference-audit.json"
version="$(plutil -extract product.version raw -o - "$root/config/product.json")"
build_number="$(plutil -extract product.build_number raw -o - "$root/config/product.json")"
printf '%s\n' "$version" > "$source/VERSION"

grep -Fq 'com.leafney.tapsay.audio.device.2ch' "$source/BlackHole/BlackHole.c"
grep -Fq 'TapSayAudio_Create' "$source/BlackHole/BlackHole.plist"
grep -Fq 'CC1226D1-A123-47B7-B113-5228AB089AA8' "$source/BlackHole/BlackHole.plist"
grep -Fq 'gDevice_SampleRate                  = 48000.0' "$source/BlackHole/BlackHole.c"
grep -Fq 'kAudioDeviceTransportTypeUSB' "$source/BlackHole/BlackHole.c"

settings=(
  ARCHS=arm64 ONLY_ACTIVE_ARCH=NO MACOSX_DEPLOYMENT_TARGET=14.0
  CODE_SIGNING_ALLOWED=NO PRODUCT_NAME=TapSayAudio
  PRODUCT_BUNDLE_IDENTIFIER=com.leafney.tapsay.audio.driver
  "MARKETING_VERSION=$version" "CURRENT_PROJECT_VERSION=$build_number"
  GCC_PREPROCESSOR_DEFINITIONS='$(inherited) DEBUG=0'
)
xcodebuild -project "$source/BlackHole.xcodeproj" -scheme BlackHole \
  -configuration Release -sdk macosx -derivedDataPath "$work/DerivedData" \
  "${settings[@]}" -showBuildSettings > "$work/build-settings.txt"
xcodebuild -project "$source/BlackHole.xcodeproj" -scheme BlackHole \
  -configuration Release -sdk macosx -derivedDataPath "$work/DerivedData" \
  "${settings[@]}" build > "$work/build.log" 2>&1

output="$work/TapSayAudio.driver"
ditto --norsrc --noextattr --noqtn --noacl \
  "$work/DerivedData/Build/Products/Release/TapSayAudio.driver" "$output"
strip -S "$output/Contents/MacOS/TapSayAudio"
mkdir -p "$work/module-cache"
xcrun swiftc -O -target arm64-apple-macosx14.0 -module-cache-path "$work/module-cache" \
  "$root/Tools/BuildIcon.swift" -o "$work/build-icon"
"$work/build-icon" "$work/TapSayAudio.iconset"
iconutil -c icns "$work/TapSayAudio.iconset" -o "$output/Contents/Resources/TapSayAudio.icns"
codesign --force --deep --sign - --timestamp=none "$output"

plist="$output/Contents/Info.plist"
binary="$output/Contents/MacOS/TapSayAudio"
test "$(plutil -extract CFBundleIdentifier raw -o - "$plist")" = com.leafney.tapsay.audio.driver
test "$(plutil -extract CFBundleName raw -o - "$plist")" = TapSayAudio
test "$(plutil -extract CFBundleShortVersionString raw -o - "$plist")" = "$version"
test "$(plutil -extract CFBundleVersion raw -o - "$plist")" = "$build_number"
test "$(plutil -extract CFPlugInFactories.CC1226D1-A123-47B7-B113-5228AB089AA8 raw -o - "$plist")" = TapSayAudio_Create
test "$(lipo -archs "$binary")" = arm64
xcrun vtool -show-build "$binary" | grep -Fq 'minos 14.0'
codesign --verify --deep --strict "$output"
strings "$binary" | grep -Fxq 'TapSay Audio 2ch'
shasum -a 256 "$binary" > "$work/binary.sha256"
python3 - "$output" "$source" "${TAPSAY_BUILD_RESULT:-$root/.build/latest-driver.json}" <<'PY'
import hashlib, json, pathlib, sys
bundle, source, result = map(pathlib.Path, sys.argv[1:])
binary = bundle / 'Contents/MacOS/TapSayAudio'
data = {'bundle': str(bundle), 'source': str(source), 'architecture': 'arm64',
        'driver_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
        'driver_mode': 'reference-with-property-fixes'}
result.parent.mkdir(parents=True, exist_ok=True)
result.write_text(json.dumps(data, indent=2)+'\n')
PY
echo "TapSay 产物：$output"
