#!/bin/bash
set -euo pipefail
export LC_ALL=C
export LANG=C

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${OUT:-$ROOT/dist}"
VERSION="$(/usr/bin/plutil -extract product.version raw -o - "$ROOT/config/product.json")"
ARCHIVE="$OUT/TapSayAudio-2ch-$VERSION-source.tar.gz"
STAGE="$OUT/source-stage"

rm -rf "$STAGE"
mkdir -p "$STAGE/TapSayAudio-2ch-$VERSION"
COPYROOT="$STAGE/TapSayAudio-2ch-$VERSION"

cp -R \
    "$ROOT/Driver" \
    "$ROOT/Uninstaller.app" \
    "$ROOT/Tools" \
    "$ROOT/config" \
    "$ROOT/packaging" \
    "$ROOT/scripts" \
    "$ROOT/third_party" \
    "$ROOT/README.md" \
    "$ROOT/LICENSE" \
    "$ROOT/THIRD_PARTY_NOTICES.md" \
    "$ROOT/.gitignore" \
    "$ROOT/.gitattributes" \
    "$COPYROOT/"

mkdir -p "$COPYROOT/docs"
cp -R "$ROOT/docs/implementation" "$COPYROOT/docs/"

for ARCH in arm64 x86_64; do
    cp "$ROOT/.build/native/$ARCH/TapSayAudioDiagnose" \
       "$COPYROOT/Tools/Transaction/TapSayAudioDiagnose-$ARCH"
    cp "$ROOT/.build/native/$ARCH/TapSayAudioLoopback" \
       "$COPYROOT/Tools/Transaction/TapSayAudioLoopback-$ARCH"
    cp "$ROOT/.build/native/$ARCH/TapSayAudioUninstaller" \
       "$COPYROOT/Uninstaller.app/Contents/MacOS/TapSayAudioUninstaller-$ARCH"
    cp "$ROOT/.build/native/$ARCH/TapSayAudioTransaction" \
       "$COPYROOT/Uninstaller.app/Contents/MacOS/TapSayAudioTransaction-$ARCH"
done

find "$COPYROOT" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "$COPYROOT" -name '*.pyc' -delete

(
    cd "$STAGE"
    /usr/bin/tar -czf "$ARCHIVE" "TapSayAudio-2ch-$VERSION"
)
rm -rf "$STAGE"
echo "源码归档：$ARCHIVE"
