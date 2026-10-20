#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "$#" -gt 1 ]]; then
    echo "Usage: $0 [legacy|reference-48k|reference-16k]" >&2
    exit 2
fi
PROFILE="${1:-legacy}"
if [[ "$PROFILE" == "legacy" ]]; then
    python3 "$ROOT/scripts/check-metadata.py"
    python3 "$ROOT/scripts/generate-driver-config.py"
    CONFIG_DIR="$ROOT/Driver/TapSayAudio"
    OUTPUT_DIR="${OUTPUT_DIR:-$ROOT/.build/driver-contract-tests}"
    IS_PROFILE=0
else
    python3 "$ROOT/scripts/check-metadata.py" --profile "$PROFILE"
    CONFIG_DIR="$ROOT/.build/generated/$PROFILE"
    python3 "$ROOT/scripts/generate-driver-config.py" --profile "$PROFILE" --output-dir "$CONFIG_DIR"
    OUTPUT_DIR="${OUTPUT_DIR:-$ROOT/.build/driver-contract-tests/$PROFILE}"
    IS_PROFILE=1
fi
OUTPUT="$OUTPUT_DIR/TapSayAudioTests"

mkdir -p "$OUTPUT_DIR"

xcrun --sdk macosx clang \
    -std=gnu11 \
    -Wall \
    -Wextra \
    -I "$CONFIG_DIR" \
    "$ROOT/Driver/TapSayAudioTests/main.c" \
    -framework Accelerate \
    -framework CoreAudio \
    -framework CoreFoundation \
    -o "$OUTPUT"

if [[ "$IS_PROFILE" == "1" ]]; then
    "$OUTPUT" "$PROFILE"
else
    "$OUTPUT"
fi
