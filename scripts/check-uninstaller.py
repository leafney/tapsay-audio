#!/usr/bin/env python3
"""Check the double-click uninstaller is self-contained and identity-correct."""

import json
import plistlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METADATA = json.loads((ROOT / "config/product.json").read_text(encoding="utf-8"))
APP = ROOT / "Uninstaller.app"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    info = plistlib.loads((APP / "Contents/Info.plist").read_bytes())
    executable = APP / "Contents/MacOS/TapSayAudioUninstaller"
    resources = APP / "Contents/Resources"
    app_source = ROOT / "Tools/Transaction/Uninstaller.swift"
    require(
        info["CFBundleIdentifier"] == METADATA["uninstaller"]["bundle_identifier"],
        "卸载 APP Bundle ID 不匹配",
    )
    require(info["CFBundleExecutable"] == executable.name, "卸载 APP 可执行文件名不匹配")
    require(
        info["CFBundleShortVersionString"] == METADATA["product"]["version"],
        "卸载 APP 版本不匹配",
    )
    require(
        info["CFBundleVersion"] == METADATA["product"]["build_number"],
        "卸载 APP 构建号不匹配",
    )
    require(
        executable.is_file() and executable.stat().st_mode & 0o111,
        "卸载 APP 入口不可执行",
    )

    require(app_source.is_file(), "缺少卸载 APP 原生入口源码")
    source = app_source.read_text(encoding="utf-8")
    require("NSAlert" in source, "卸载 APP 缺少图形确认")
    require("AuthorizationCopyRights" in source, "卸载 APP 缺少管理员授权")
    require("AuthorizationExecuteWithPrivileges" in source, "卸载 APP 未调用受限卸载工具")
    for arch in METADATA["product"]["architectures"]:
        transaction = ROOT / f".build/native/{arch}/TapSayAudioTransaction"
        ui = ROOT / f".build/native/{arch}/TapSayAudioUninstaller"
        for binary in (transaction, ui):
            require(binary.is_file(), f"缺少 {arch} 原生工具，请先运行 scripts/build-native-tools.sh")
            actual = subprocess.check_output(["/usr/bin/lipo", "-archs", str(binary)], text=True).split()
            require(actual == [arch], f"原生卸载工具架构错误：{binary}")

    for name in ("product.json",):
        require((resources / name).is_file(), f"卸载 APP 缺少内置资源 {name}")
    embedded = json.loads((resources / "product.json").read_text(encoding="utf-8"))
    require(
        embedded["driver"]["device_uid"] == METADATA["driver"]["device_uid"],
        "卸载 APP 内置设备 UID 不一致",
    )
    print("卸载 APP 结构检查通过")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"卸载 APP 检查失败：{error}", file=sys.stderr)
        raise SystemExit(1)
