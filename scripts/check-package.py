#!/usr/bin/env python3
"""Verify package identity, payload architecture, scripts, and uninstaller."""

import json
import hashlib
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
PROFILES = json.loads((ROOT / "config/driver-profiles.json").read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    require(len(sys.argv) in (3, 4), "用法：check-package.py PKG ARCH [PROFILE]")
    pkg = Path(sys.argv[1]).resolve()
    expected_arch = sys.argv[2]
    profile = sys.argv[3] if len(sys.argv) == 4 else None
    require(expected_arch == "arm64", f"本阶段只支持 arm64：{expected_arch}")
    if profile:
        require(profile in PROFILES["profiles"], f"未知实验配置：{profile}")
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
        if profile:
            expected_default = PROFILES["profiles"][profile]["default_sample_rate_hz"]
            expected_rates = PROFILES["sample_rates_hz"]
            require(info.get("TapSayAudioProfile") == profile, "驱动实验配置不匹配")
            require(info.get("TapSayAudioDefaultSampleRate") == expected_default, "驱动默认采样率不匹配")
            require(info.get("TapSayAudioSupportedSampleRates") == expected_rates, "驱动支持采样率列表不匹配")
            manifest_path = driver / "Contents/Resources/TapSayAudio-experiment-manifest.json"
            require(manifest_path.is_file(), "实验驱动缺少内嵌实验清单")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            require(manifest.get("profile") == profile, "内嵌清单实验配置不匹配")
            require(manifest.get("architecture") == expected_arch, "内嵌清单架构不匹配")
            require(manifest.get("default_sample_rate_hz") == expected_default, "内嵌清单默认采样率不匹配")
            require(manifest.get("sample_rates_hz") == expected_rates, "内嵌清单支持采样率列表不匹配")
            require(
                manifest.get("device2", {}).get("uid") == PROFILES["device2"]["uid"],
                "内嵌清单隐藏设备 UID 不匹配",
            )
            driver_sha = hashlib.sha256(executable.read_bytes()).hexdigest()
            require(manifest.get("driver_sha256") == driver_sha, "内嵌清单驱动散列不匹配")
            evidence = manifest.get("build_evidence", {})
            audit = manifest.get("reference_audit", {})
            require(evidence.get("driver_sha256") == driver_sha, "实际构建证据与驱动不匹配")
            require(audit.get("driver_sha256") == driver_sha and audit.get("status") == "passed",
                    "缺少通过的参考构建核对")
            require(evidence.get("effective_settings") == manifest.get("build_settings"),
                    "内嵌构建设置与实际构建记录不匹配")
            require(evidence.get("effective_settings", {}).get("ARCHS") == expected_arch,
                    "实际构建架构不匹配")
            require(audit.get("build_evidence_sha256") == manifest.get("build_evidence_sha256"),
                    "参考核对对应的构建证据不匹配")
            evidence_sha = hashlib.sha256((json.dumps(evidence, indent=2) + "\n").encode()).hexdigest()
            require(evidence_sha == manifest.get("build_evidence_sha256"), "内嵌构建证据散列不匹配")
            require(evidence.get("source_commit", "").startswith(manifest.get("source_commit", "!")),
                    "实际构建与打包源码提交不匹配")
        else:
            require("TapSayAudioProfile" not in info, "实验包必须显式提供 profile 参数")
        require(
            DRIVER["plugin_factory_uuid"] in info["CFPlugInFactories"],
            "驱动插件工厂 UUID 不匹配",
        )
        archs = subprocess.check_output(
            ["/usr/bin/lipo", "-archs", str(executable)], text=True
        ).split()
        require(archs == [expected_arch], f"PKG 载荷架构为 {archs}，期望 {expected_arch}")
        strings = subprocess.check_output(["/usr/bin/strings", str(executable)], text=True)
        require(DRIVER["device_uid"] in strings, "驱动设备 UID 缺失")
        require(DRIVER["device_name"] in strings, "驱动设备名称缺失")
        if profile:
            require(PROFILES["device2"]["uid"] in strings, "驱动隐藏设备 UID 缺失")
            require(PROFILES["device2"]["name"] in strings, "驱动隐藏设备名称缺失")
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
        native_archs = subprocess.check_output(
            ["/usr/bin/lipo", "-archs", str(scripts / "TapSayAudioTransaction")],
            text=True,
        ).split()
        require(native_archs == [expected_arch], "PKG 事务工具架构不匹配")
        transaction_source = (ROOT / "Tools/Transaction/main.swift").read_text(encoding="utf-8")
        require("case \"uninstall\"" in transaction_source, "原生事务工具缺少卸载入口")
        for source in (
            "Tools/Transaction/TransactionSupport.swift",
            "Tools/Transaction/TransactionRecord.swift",
            "Tools/Transaction/TransactionRecovery.swift",
            "Tools/Transaction/HistoricalCleanup.swift",
        ):
            require((ROOT / source).is_file(), f"缺少事务模块源码：{source}")

    print(f"PKG 检查通过：{pkg.name} ({expected_arch}, {profile or 'legacy'})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, ValueError, ET.ParseError, subprocess.CalledProcessError) as error:
        print(f"PKG 检查失败：{error}", file=sys.stderr)
        raise SystemExit(1)
