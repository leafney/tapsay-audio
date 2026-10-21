#!/bin/bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
test "$#" = 2 || { echo "用法：$0 SOURCE_C formats|control-list|control-matrix" >&2; exit 2; }
driver_source="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
mkdir -p "$root/.build/contract-tests"
test_binary="$(mktemp "$root/.build/contract-tests/hal.XXXXXX")"
xcrun clang -std=gnu11 -g -O1 -fsanitize=address -fno-omit-frame-pointer \
  -DDEBUG=0 "-DTAPSAY_DRIVER_SOURCE=\"$driver_source\"" \
  "$root/Tests/DriverContract.c" -framework CoreAudio -framework CoreFoundation \
  -framework Accelerate -o "$test_binary"
ASAN_OPTIONS=symbolize=0 "$test_binary" "$2"
