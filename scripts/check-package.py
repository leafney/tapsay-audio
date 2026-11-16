#!/usr/bin/env python3
"""Verify package identity, payload architecture, scripts, and uninstaller."""

import json
import plistlib
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METADATA = json.loads((ROOT / "config/product.json").read_text(encoding="utf-8"))
DRIVER = METADATA["driver"]
PRODUCT = METADATA["product"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    require(len(sys.argv) == 3, "用法：check-package.py PKG arm64|x86_64")
    pkg = Path(sys.argv[1]).resolve()
    expected_arch = sys.argv[2]
    require(expected_arch in ("arm64", "x86_64"), f"目标架构无效：{expected_arch}")
    require(pkg.is_file(), f"PKG 不存在：{pkg}")

    with tempfile.TemporaryDirectory() as directory:
        expanded = Path(directory) / "expanded"
        subprocess.run(
            ["/usr/sbin/pkgutil", "--expand-full", str(pkg), str(expanded)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        package_info = (expanded / "PackageInfo").read_text(encoding="utf-8")
        package_xml = ET.fromstring(package_info)
        require(
            f'identifier="{DRIVER["package_receipt_identifier"]}"' in package_info,
            "PKG 收据标识不匹配",
        )
        require(
            f'version="{PRODUCT["version"]}"' in package_info,
            "PKG 版本不匹配",
        )
        require(
            f'minimumSystemVersion="{PRODUCT["minimum_macos"]}"' in package_info,
            "PKG 最低系统不匹配",
        )

        driver = expanded / "Scripts/package-payload/TapSayAudio.driver"
        require(driver.is_dir(), "PKG 缺少事务安装载荷")
        info = plistlib.loads((driver / "Contents/Info.plist").read_bytes())
        require(info["CFBundleIdentifier"] == DRIVER["bundle_identifier"], "驱动 Bundle ID 不匹配")
        require(
            info["CFBundleShortVersionString"] == PRODUCT["version"],
            "驱动版本不匹配",
        )
        require(info["CFBundleVersion"] == PRODUCT["build_number"], "驱动构建号不匹配")
        executable = driver / "Contents/MacOS" / DRIVER["executable_name"]
        require("TapSayAudioProfile" not in info, "正式包不能含实验 profile")
        require(
            DRIVER["plugin_factory_uuid"] in info["CFPlugInFactories"],
            "驱动插件工厂 UUID 不匹配",
        )
        archs = subprocess.check_output(
            ["/usr/bin/lipo", "-archs", str(executable)], text=True
        ).split()
        require(archs == [expected_arch], f"PKG 载荷架构为 {archs}，期望 {expected_arch}")
        minimum_system = subprocess.check_output(
            ["/usr/bin/xcrun", "vtool", "-show-build", str(executable)],
            text=True,
        )
        require(
            f"minos {PRODUCT['minimum_macos']}" in minimum_system,
            "PKG 驱动最低系统不匹配",
        )
        strings = subprocess.check_output(["/usr/bin/strings", str(executable)], text=True)
        require(DRIVER["device_uid"] in strings, "驱动设备 UID 缺失")
        require(DRIVER["device_name"] in strings, "驱动设备名称缺失")
        # Upstream private function names and copyright are retained for provenance.
        for forbidden in ("MiRemoteV", "Q5C99V536K", "audio.existential.BlackHole2ch"):
            require(forbidden not in strings, f"成品包含其他产品标识：{forbidden}")

        scripts = expanded / "Scripts"
        payload_info = package_xml.find("payload")
        require(
            payload_info is not None
            and payload_info.get("numberOfFiles") == "1"
            and payload_info.get("installKBytes") == "0",
            "PKG 必须含空根目录载荷以生成系统收据",
        )
        payload = expanded / "Payload"
        require(payload.is_dir() and not any(payload.iterdir()), "PKG 不能绕过事务写入任何系统文件")
        require((expanded / "Bom").is_file(), "PKG 缺少系统收据所需 Bom")
        require((scripts / "preinstall").is_file(), "PKG 缺少 preinstall")
        require((scripts / "postinstall").is_file(), "PKG 缺少 postinstall")
        require(
            "TapSayAudioTransaction" in (scripts / "postinstall").read_text(encoding="utf-8"),
            "PKG postinstall 未调用事务安装逻辑",
        )
        for required in (
            "TapSayAudioTransaction",
            "product.json",
            "package-payload/TapSayAudio.driver/Contents/Info.plist",
        ):
            require((scripts / required).is_file(), f"PKG 脚本目录缺少 {required}")
        require(json.loads((scripts / "product.json").read_text()) == METADATA, "包内产品配置不一致")
        subprocess.run(["codesign", "--verify", "--deep", "--strict", str(driver)], check=True)
        native_archs = subprocess.check_output(
            ["/usr/bin/lipo", "-archs", str(scripts / "TapSayAudioTransaction")],
            text=True,
        ).split()
        require(native_archs == [expected_arch], "PKG 事务工具架构不匹配")
        subprocess.run(
            ["/usr/bin/codesign", "--verify", "--strict",
             str(scripts / "TapSayAudioTransaction")],
            check=True,
        )
        transaction_system = subprocess.check_output(
            ["/usr/bin/xcrun", "vtool", "-show-build",
             str(scripts / "TapSayAudioTransaction")],
            text=True,
        )
        require(
            f"minos {PRODUCT['minimum_macos']}" in transaction_system,
            "PKG 事务工具最低系统不匹配",
        )
        transaction_source = (ROOT / "Tools/Transaction/main.swift").read_text(encoding="utf-8")
        require("case \"uninstall\"" in transaction_source, "原生事务工具缺少卸载入口")
        for source in (
            "Tools/Transaction/TransactionSupport.swift",
            "Tools/Transaction/TransactionRecord.swift",
            "Tools/Transaction/TransactionRecovery.swift",
            "Tools/Transaction/HistoricalCleanup.swift",
        ):
            require((ROOT / source).is_file(), f"缺少事务模块源码：{source}")

    print(f"PKG 检查通过：{pkg.name} ({expected_arch})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, ValueError, ET.ParseError, subprocess.CalledProcessError) as error:
        print(f"PKG 检查失败：{error}", file=sys.stderr)
        raise SystemExit(1)
