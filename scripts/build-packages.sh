#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${OUT:-$ROOT/dist}"
METADATA="$ROOT/config/product.json"
read_meta() {
    /usr/bin/plutil -extract "$1" raw -o - "$METADATA"
}

VERSION="$(read_meta product.version)"
BUILD_NUMBER="$(read_meta product.build_number)"
MINIMUM_MACOS="$(read_meta product.minimum_macos)"
RECEIPT="$(read_meta driver.package_receipt_identifier)"
DRIVER_BUNDLE="$(read_meta driver.bundle_identifier)"
DRIVER_EXECUTABLE="$(read_meta driver.executable_name)"
DRIVER_UID="$(read_meta driver.device_uid)"
UNINSTALLER_NAME="$(read_meta uninstaller.display_name)"
ARCHES=(arm64)

mkdir -p "$OUT"
rm -f "$OUT/TapSayAudio-2ch-$VERSION"*.pkg \
      "$OUT/TapSayAudio-2ch-$VERSION"*.dmg \
      "$OUT/arm64.pkg" "$OUT/x86_64.pkg" \
      "$OUT/SHA256SUMS.txt" "$OUT/TapSayAudio-2ch-$VERSION-source.tar.gz"
python3 "$ROOT/scripts/check-metadata.py"
mkdir -p "$ROOT/.build/native"
bash "$ROOT/scripts/build-native-tools.sh"
python3 "$ROOT/scripts/check-uninstaller.py"
bash "$ROOT/scripts/build-driver.sh"

for ARCH in "${ARCHES[@]}"; do
    BUNDLE="$(find "$ROOT/.build" -path '*/tapsay-driver-arm64.*/TapSayAudio.driver' -type d -print | sort | tail -1)"
    test -n "$BUNDLE" && test -d "$BUNDLE"
    SCRIPTS="$OUT/scripts-$ARCH"
    EMPTY_ROOT="$OUT/empty-root-$ARCH"
    DMGROOT="$OUT/dmg-$ARCH"
    PKG="$OUT/TapSayAudio-2ch-$VERSION.pkg"
    FINAL_PKG="$OUT/TapSayAudio-2ch-$VERSION-$ARCH.pkg"
    FINAL_DMG="$OUT/TapSayAudio-2ch-$VERSION-$ARCH.dmg"

    rm -rf "$SCRIPTS" "$DMGROOT" "$EMPTY_ROOT"
    mkdir -p "$SCRIPTS/package-payload" "$EMPTY_ROOT"
    cp -R "$BUNDLE" "$SCRIPTS/package-payload/"
    cp "$ROOT/.build/native/$ARCH/TapSayAudioTransaction" "$SCRIPTS/"
    cp "$METADATA" "$SCRIPTS/product.json"
    cp "$ROOT/packaging/pkg-scripts/preinstall" \
       "$ROOT/packaging/pkg-scripts/postinstall" "$SCRIPTS/"
    chmod 755 "$SCRIPTS/preinstall" "$SCRIPTS/postinstall" \
              "$SCRIPTS/TapSayAudioTransaction"

    /usr/bin/pkgbuild \
        --root "$EMPTY_ROOT" \
        --scripts "$SCRIPTS" \
        --identifier "$RECEIPT" \
        --version "$VERSION" \
        --install-location / \
        --min-os-version "$MINIMUM_MACOS" \
        "$PKG"
    mv "$PKG" "$FINAL_PKG"

    mkdir -p "$DMGROOT"
    cp "$FINAL_PKG" "$DMGROOT/TapSayAudio-2ch-$VERSION.pkg"
    cp -R "$ROOT/Uninstaller.app" "$DMGROOT/$UNINSTALLER_NAME.app"
    rm -f "$DMGROOT/$UNINSTALLER_NAME.app/Contents/MacOS/TapSayAudioTransaction-arm64" \
          "$DMGROOT/$UNINSTALLER_NAME.app/Contents/MacOS/TapSayAudioTransaction-x86_64" \
          "$DMGROOT/$UNINSTALLER_NAME.app/Contents/MacOS/TapSayAudioUninstaller-arm64" \
          "$DMGROOT/$UNINSTALLER_NAME.app/Contents/MacOS/TapSayAudioUninstaller-x86_64"
    cp "$ROOT/.build/native/$ARCH/TapSayAudioUninstaller" \
       "$DMGROOT/$UNINSTALLER_NAME.app/Contents/MacOS/TapSayAudioUninstaller"
    cp "$ROOT/.build/native/$ARCH/TapSayAudioTransaction" \
       "$DMGROOT/$UNINSTALLER_NAME.app/Contents/MacOS/TapSayAudioTransaction-$ARCH"
    cp "$ROOT/packaging/dmg/README.txt" "$DMGROOT/说明.txt"
    cp "$ROOT/LICENSE" "$DMGROOT/GPL-3.0.txt"
    cp "$ROOT/THIRD_PARTY_NOTICES.md" "$DMGROOT/第三方许可说明.md"

    if ! /usr/bin/hdiutil create \
        -volname "TapSay Audio $ARCH" \
        -srcfolder "$DMGROOT" \
        -format UDZO \
        -ov \
        "$FINAL_DMG"; then
        echo "DMG 创建失败：$FINAL_DMG" >&2
        exit 1
    fi

    python3 "$ROOT/scripts/check-package.py" "$FINAL_PKG" "$ARCH"
    rm -rf "$SCRIPTS" "$DMGROOT" "$EMPTY_ROOT"
done

bash "$ROOT/scripts/build-source-archive.sh"
(
    cd "$OUT"
    /usr/bin/shasum -a 256 TapSayAudio-2ch-"$VERSION"-arm64.pkg \
        TapSayAudio-2ch-"$VERSION"-arm64.dmg \
        TapSayAudio-2ch-"$VERSION"-source.tar.gz > SHA256SUMS.txt
)
python3 "$ROOT/scripts/check-release-readiness.py"
