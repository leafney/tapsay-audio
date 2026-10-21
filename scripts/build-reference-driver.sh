#!/bin/bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
archive="${1:-/private/tmp/blackhole-e2b22aaaba4e507a097131704bf96dabc004d9cf.tar.gz}"
expected_archive=5d523d51165873ee339bfb670694de61ad2ce84a0c72a6df32dbb283313f26b0
expected_patch=51dea42771bc432573433f76a0bfb140d9463db112d568f0192e97b5b7a2dc5f
patch="$root/third_party/blackhole/blackhole-device-usb.patch"

check_hash() {
  local actual
  actual="$(shasum -a 256 "$2" | awk '{print $1}')"
  test "$actual" = "$1" || { echo "散列不符：$2" >&2; exit 1; }
}
check_hash "$expected_archive" "$archive"
check_hash "$expected_patch" "$patch"
mkdir -p "$root/.build"
work="$(mktemp -d "$root/.build/reference-arm64.XXXXXX")"
tar -xzf "$archive" -C "$work"
source="$work/BlackHole-e2b22aaaba4e507a097131704bf96dabc004d9cf"
check_hash 5194703e8923713d15159b951b8fe9a8be08e7c0fb7c05b17c8e865e4c2effb6 "$source/BlackHole/BlackHole.c"
check_hash 8346211852797b491245302d6ad5d3e6b855d3d07bf37e4d4d5b0e64656a6c88 "$source/BlackHole.xcodeproj/project.pbxproj"
(cd "$source" && patch --dry-run -p1 -i "$patch" && patch -p1 -i "$patch")
grep -Fq '4a91361d-19af-4ba0-a87a-0a6242ed6ae4' "$source/BlackHole/BlackHole.plist"
driver_source="$source/BlackHole/BlackHole.c"
grep -Fq 'gDevice_SampleRate                  = 48000.0' "$driver_source"
grep -Fq 'kSampleRates       8000, 16000, 24000, 44100, 48000, 88200, 96000, 176400, 192000, 352800, 384000, 705600, 768000' "$driver_source"
grep -Fq 'kDevice_RingBufferSize              = 16384' "$driver_source"
grep -Fq 'kAudioStreamPropertyVirtualFormat:' "$driver_source"
grep -Fq 'kAudioStreamPropertyPhysicalFormat:' "$driver_source"

definitions='$GCC_PREPROCESSOR_DEFINITIONS kDriver_Name=\"MiRemoteV\" kPlugIn_BundleID=\"com.hd838a.MiRemoteV2ch\" kNumber_Of_Channels=2'
settings=(ARCHS=arm64 ONLY_ACTIVE_ARCH=NO MACOSX_DEPLOYMENT_TARGET=14.0 CODE_SIGNING_ALLOWED=NO PRODUCT_NAME=MiRemoteV2ch PRODUCT_BUNDLE_IDENTIFIER=com.hd838a.MiRemoteV2ch "GCC_PREPROCESSOR_DEFINITIONS=$definitions")
xcodebuild -project "$source/BlackHole.xcodeproj" -scheme BlackHole -configuration Release -sdk macosx -derivedDataPath "$work/DerivedData" "${settings[@]}" -showBuildSettings > "$work/build-settings.txt"
xcodebuild -project "$source/BlackHole.xcodeproj" -scheme BlackHole -configuration Release -sdk macosx -derivedDataPath "$work/DerivedData" "${settings[@]}" build > "$work/build.log" 2>&1
output="$work/MiRemoteV2ch.driver"
ditto --norsrc --noextattr --noqtn --noacl "$work/DerivedData/Build/Products/Release/MiRemoteV2ch.driver" "$output"
strip -S "$output/Contents/MacOS/MiRemoteV2ch"
codesign --force --deep --sign - --timestamp=none "$output"
test "$(lipo -archs "$output/Contents/MacOS/MiRemoteV2ch")" = arm64
test "$(plutil -extract CFBundleIdentifier raw -o - "$output/Contents/Info.plist")" = com.hd838a.MiRemoteV2ch
test "$(plutil -extract CFPlugInFactories.4a91361d-19af-4ba0-a87a-0a6242ed6ae4 raw -o - "$output/Contents/Info.plist")" = BlackHole_Create
strings "$output/Contents/MacOS/MiRemoteV2ch" | grep -Fxq 'MiRemoteV %ich'
strings "$output/Contents/MacOS/MiRemoteV2ch" | grep -Fxq 'MiRemoteV%ich_UID'
xcrun vtool -show-build "$output/Contents/MacOS/MiRemoteV2ch" | grep -Fq 'minos 14.0'
codesign --verify --deep --strict "$output"
shasum -a 256 "$output/Contents/MacOS/MiRemoteV2ch" > "$work/binary.sha256"
echo "参考产物：$output"
