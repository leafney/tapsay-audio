#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARCH=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --arch)
            if [[ $# -lt 2 ]]; then
                echo "--arch 缺少参数" >&2
                exit 2
            fi
            ARCH="$2"
            shift 2
            ;;
        *)
            echo "未知参数：$1" >&2
            exit 2
            ;;
    esac
done
case "$ARCH" in
    arm64|x86_64) ;;
    *)
        echo "--arch 只能是 arm64 或 x86_64" >&2
        exit 2
        ;;
esac
SDK="$(xcrun --sdk macosx --show-sdk-path)"
OUTPUT="$ROOT/.build/native/$ARCH"
MODULE_CACHE="$ROOT/.build/native/module-cache/$ARCH"
mkdir -p "$OUTPUT" "$MODULE_CACHE"

check_binary() {
    local binary="$1"
    local architecture_output architecture_count
    architecture_output="$(lipo -archs "$binary")"
    read -r -a architectures <<< "$architecture_output"
    architecture_count="${#architectures[@]}"
    if [[ "$architecture_count" -ne 1 || "${architectures[0]}" != "$ARCH" ]]; then
        echo "原生工具架构不匹配：$binary（期望 $ARCH，实际 $architecture_output）" >&2
        exit 1
    fi
    if ! xcrun vtool -show-build "$binary" | grep -Fq 'minos 14.0'; then
        echo "原生工具最低系统不是 macOS 14.0：$binary" >&2
        exit 1
    fi
}

xcrun swiftc -O -sdk "$SDK" -target "$ARCH-apple-macosx14.0" \
        -module-cache-path "$MODULE_CACHE" \
        "$ROOT/Tools/Transaction/Architecture.swift" \
        "$ROOT/Tools/Transaction/TransactionSupport.swift" \
        "$ROOT/Tools/Transaction/TransactionRecord.swift" \
        "$ROOT/Tools/Transaction/TransactionRecovery.swift" \
        "$ROOT/Tools/Transaction/HistoricalCleanup.swift" \
        "$ROOT/Tools/Transaction/UninstallResult.swift" \
        "$ROOT/Tools/Transaction/UninstallDeviceCheck.swift" \
        "$ROOT/Tools/Transaction/main.swift" \
        -framework CoreAudio \
        -o "$OUTPUT/TapSayAudioTransaction"
xcrun swiftc -O -sdk "$SDK" -target "$ARCH-apple-macosx14.0" \
        -module-cache-path "$MODULE_CACHE" \
        "$ROOT/Tools/Transaction/Architecture.swift" \
        "$ROOT/Tools/Transaction/TransactionSupport.swift" \
        "$ROOT/Tools/Transaction/HistoricalCleanup.swift" \
        "$ROOT/Tools/Transaction/UninstallResult.swift" \
        "$ROOT/Tools/Transaction/Uninstaller.swift" \
        -framework AppKit -framework Security \
        -o "$OUTPUT/TapSayAudioUninstaller"
xcrun swiftc -O -sdk "$SDK" -target "$ARCH-apple-macosx14.0" \
        -module-cache-path "$MODULE_CACHE" \
        "$ROOT/Tools/Transaction/Diagnose.swift" \
        -framework CoreAudio \
        -o "$OUTPUT/TapSayAudioDiagnose"
xcrun swiftc -O -sdk "$SDK" -target "$ARCH-apple-macosx14.0" \
        -module-cache-path "$MODULE_CACHE" \
        "$ROOT/Tools/Transaction/Loopback.swift" \
        -framework AudioToolbox -framework CoreAudio \
        -o "$OUTPUT/TapSayAudioLoopback"

for binary in \
    "$OUTPUT/TapSayAudioTransaction" \
    "$OUTPUT/TapSayAudioUninstaller" \
    "$OUTPUT/TapSayAudioDiagnose" \
    "$OUTPUT/TapSayAudioLoopback"; do
    check_binary "$binary"
done
