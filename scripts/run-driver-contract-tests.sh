#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT/.build/driver-contract-tests}"
OUTPUT="$OUTPUT_DIR/TapSayAudioTests"

python3 "$ROOT/scripts/check-metadata.py"
python3 "$ROOT/scripts/generate-driver-config.py"
mkdir -p "$OUTPUT_DIR"

xcrun --sdk macosx clang \
    -std=gnu11 \
    -Wall \
    -Wextra \
    "$ROOT/Driver/TapSayAudioTests/main.c" \
    -framework Accelerate \
    -framework CoreAudio \
    -framework CoreFoundation \
    -o "$OUTPUT"

"$OUTPUT"
