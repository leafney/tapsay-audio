#!/bin/bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
archive="${1:-/private/tmp/blackhole-e2b22aaaba4e507a097131704bf96dabc004d9cf.tar.gz}"
archive_sha=5d523d51165873ee339bfb670694de61ad2ce84a0c72a6df32dbb283313f26b0
usb_patch="$root/third_party/blackhole/blackhole-device-usb.patch"
identity_patch="$root/third_party/blackhole/tapsay-identity.patch"
expected_patch_sha=51dea42771bc432573433f76a0bfb140d9463db112d568f0192e97b5b7a2dc5f

sha256() { shasum -a 256 "$1" | awk '{print $1}'; }
test "$(sha256 "$archive")" = "$archive_sha"
test "$(sha256 "$usb_patch")" = "$expected_patch_sha"
test -s "$identity_patch"

mkdir -p "$root/.build"
work="$(mktemp -d "$root/.build/tapsay-driver-arm64.XXXXXX")"
tar -xzf "$archive" -C "$work"
source="$work/BlackHole-e2b22aaaba4e507a097131704bf96dabc004d9cf"
patch -p1 -i "$usb_patch" -d "$source"
patch -p1 -i "$identity_patch" -d "$source"

grep -Fq 'com.leafney.tapsay.audio.device.2ch' "$source/BlackHole/BlackHole.c"
grep -Fq 'TapSayAudio_Create' "$source/BlackHole/BlackHole.plist"
grep -Fq 'CC1226D1-A123-47B7-B113-5228AB089AA8' "$source/BlackHole/BlackHole.plist"
grep -Fq 'gDevice_SampleRate                  = 48000.0' "$source/BlackHole/BlackHole.c"
grep -Fq 'kAudioDeviceTransportTypeUSB' "$source/BlackHole/BlackHole.c"

settings=(
  ARCHS=arm64 ONLY_ACTIVE_ARCH=NO MACOSX_DEPLOYMENT_TARGET=14.0
  CODE_SIGNING_ALLOWED=NO PRODUCT_NAME=TapSayAudio
  PRODUCT_BUNDLE_IDENTIFIER=com.leafney.tapsay.audio.driver
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
codesign --force --deep --sign - --timestamp=none "$output"

plist="$output/Contents/Info.plist"
binary="$output/Contents/MacOS/TapSayAudio"
test "$(plutil -extract CFBundleIdentifier raw -o - "$plist")" = com.leafney.tapsay.audio.driver
test "$(plutil -extract CFBundleName raw -o - "$plist")" = TapSayAudio
test "$(plutil -extract CFBundleShortVersionString raw -o - "$plist")" = 0.1.0
test "$(plutil -extract CFPlugInFactories.CC1226D1-A123-47B7-B113-5228AB089AA8 raw -o - "$plist")" = TapSayAudio_Create
test "$(lipo -archs "$binary")" = arm64
xcrun vtool -show-build "$binary" | grep -Fq 'minos 14.0'
codesign --verify --deep --strict "$output"
strings "$binary" | grep -Fxq 'TapSay Audio 2ch'
shasum -a 256 "$binary" > "$work/binary.sha256"
echo "TapSay 产物：$output"
