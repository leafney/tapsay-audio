#!/bin/bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
arch=""
signing_mode="adhoc"
application_identity=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --arch)
      if [[ $# -lt 2 ]]; then
        echo "--arch 缺少参数" >&2
        exit 2
      fi
      arch="$2"
      shift 2
      ;;
    --signing-mode)
      if [[ $# -lt 2 ]]; then
        echo "--signing-mode 缺少参数" >&2
        exit 2
      fi
      signing_mode="$2"
      shift 2
      ;;
    --application-identity)
      if [[ $# -lt 2 ]]; then
        echo "--application-identity 缺少参数" >&2
        exit 2
      fi
      application_identity="$2"
      shift 2
      ;;
    *)
      echo "未知参数：$1" >&2
      exit 2
      ;;
  esac
done
case "$arch" in
  arm64|x86_64) ;;
  *)
    echo "--arch 只能是 arm64 或 x86_64" >&2
    exit 2
    ;;
esac
case "$signing_mode" in
  adhoc|developer-id) ;;
  *)
    echo "--signing-mode 只能是 adhoc 或 developer-id" >&2
    exit 2
    ;;
esac
if [[ "$signing_mode" == "developer-id" && -z "$application_identity" ]]; then
  echo "Developer ID 模式缺少应用签名身份" >&2
  exit 2
fi
export LC_ALL=C
python3 "$root/scripts/check-metadata.py"

mkdir -p "$root/.build"
work="$(mktemp -d "$root/.build/tapsay-driver-$arch.XXXXXX")"
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
  "ARCHS=$arch" ONLY_ACTIVE_ARCH=NO MACOSX_DEPLOYMENT_TARGET=14.0
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
host_arch="$(uname -m)"
case "$host_arch" in
  arm64|x86_64) ;;
  *)
    echo "不支持的构建主机架构：$host_arch" >&2
    exit 1
    ;;
esac
xcrun swiftc -O -target "$host_arch-apple-macosx14.0" -module-cache-path "$work/module-cache" \
  "$root/Tools/BuildIcon.swift" -o "$work/build-icon"
"$work/build-icon" "$work/TapSayAudio.iconset" "$output/Contents/Resources/TapSayAudio.icns"
plutil -replace CFBundleIconFile -string TapSayAudio.icns "$output/Contents/Info.plist"
if [[ "$signing_mode" == "adhoc" ]]; then
  codesign --force --deep --sign - --timestamp=none "$output"
else
  codesign --force --deep --options runtime --sign "$application_identity" --timestamp "$output"
fi

plist="$output/Contents/Info.plist"
binary="$output/Contents/MacOS/TapSayAudio"
test "$(plutil -extract CFBundleIdentifier raw -o - "$plist")" = com.leafney.tapsay.audio.driver
test "$(plutil -extract CFBundleName raw -o - "$plist")" = TapSayAudio
test "$(plutil -extract CFBundleShortVersionString raw -o - "$plist")" = "$version"
test "$(plutil -extract CFBundleVersion raw -o - "$plist")" = "$build_number"
test "$(plutil -extract CFBundleIconFile raw -o - "$plist")" = TapSayAudio.icns
test "$(plutil -extract CFPlugInFactories.CC1226D1-A123-47B7-B113-5228AB089AA8 raw -o - "$plist")" = TapSayAudio_Create
test -s "$output/Contents/Resources/TapSayAudio.icns"
read -r -a binary_architectures <<< "$(lipo -archs "$binary")"
test "${#binary_architectures[@]}" = 1
test "${binary_architectures[0]}" = "$arch"
xcrun vtool -show-build "$binary" | grep -Fq 'minos 14.0'
codesign --verify --deep --strict "$output"
strings "$binary" | grep -Fxq 'TapSay Audio 2ch'
shasum -a 256 "$binary" > "$work/binary.sha256"
python3 - "$output" "$source" \
  "${TAPSAY_BUILD_RESULT:-$root/.build/latest-driver-$arch.json}" \
  "$root" "$arch" "$version" "$build_number" "$signing_mode" <<'PY'
import hashlib, json, pathlib, sys
bundle, source, result, root = map(pathlib.Path, sys.argv[1:5])
architecture, version, build_number, signing_mode = sys.argv[5:]
sys.path.insert(0, str(root / 'scripts'))
from driver_sources import PATCHES, verify_inputs
hashes = verify_inputs()
binary = bundle / 'Contents/MacOS/TapSayAudio'
data = {'bundle': str(bundle), 'source': str(source), 'architecture': architecture,
        'version': version, 'build_number': build_number, 'minimum_macos': '14.0',
        'signing_mode': signing_mode,
        'driver_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
        'driver_mode': 'reference-with-property-fixes',
        'patches_sha256': {name: hashes[name] for name in PATCHES}}
result.parent.mkdir(parents=True, exist_ok=True)
result.write_text(json.dumps(data, indent=2)+'\n')
PY
echo "TapSay 产物：$output"
