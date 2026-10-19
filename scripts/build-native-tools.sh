#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SDK="$(xcrun --sdk macosx --show-sdk-path)"
mkdir -p "$ROOT/.build/native/module-cache"
for ARCH in arm64 x86_64; do
    mkdir -p "$ROOT/.build/native/$ARCH"
    xcrun swiftc -O -sdk "$SDK" -target "$ARCH-apple-macosx14.0" \
        -module-cache-path "$ROOT/.build/native/module-cache" \
        "$ROOT/Tools/Transaction/Architecture.swift" \
        "$ROOT/Tools/Transaction/TransactionRecord.swift" \
        "$ROOT/Tools/Transaction/TransactionRecovery.swift" \
        "$ROOT/Tools/Transaction/UninstallResult.swift" \
        "$ROOT/Tools/Transaction/UninstallDeviceCheck.swift" \
        "$ROOT/Tools/Transaction/main.swift" \
        -framework CoreAudio \
        -o "$ROOT/.build/native/$ARCH/TapSayAudioTransaction"
    xcrun swiftc -O -sdk "$SDK" -target "$ARCH-apple-macosx14.0" \
        -module-cache-path "$ROOT/.build/native/module-cache" \
        "$ROOT/Tools/Transaction/Architecture.swift" \
        "$ROOT/Tools/Transaction/UninstallResult.swift" \
        "$ROOT/Tools/Transaction/Uninstaller.swift" \
        -framework AppKit -framework Security \
        -o "$ROOT/.build/native/$ARCH/TapSayAudioUninstaller"
    xcrun swiftc -O -sdk "$SDK" -target "$ARCH-apple-macosx14.0" \
        -module-cache-path "$ROOT/.build/native/module-cache" \
        "$ROOT/Tools/Transaction/Diagnose.swift" \
        -framework CoreAudio \
        -o "$ROOT/.build/native/$ARCH/TapSayAudioDiagnose"
    xcrun swiftc -O -sdk "$SDK" -target "$ARCH-apple-macosx14.0" \
        -module-cache-path "$ROOT/.build/native/module-cache" \
        "$ROOT/Tools/Transaction/Loopback.swift" \
        -framework AudioToolbox -framework CoreAudio \
        -o "$ROOT/.build/native/$ARCH/TapSayAudioLoopback"
done
