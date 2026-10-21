#!/usr/bin/env python3
"""Audit local release assets; never publishes or creates a GitHub release."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
META = json.loads((ROOT / "config/product.json").read_text(encoding="utf-8"))
VERSION = META["product"]["version"]
DIST = ROOT / "dist"
ASSETS = [
    f"TapSayAudio-2ch-{VERSION}-arm64.pkg",
    f"TapSayAudio-2ch-{VERSION}-arm64.dmg",
    f"TapSayAudio-2ch-{VERSION}-source.tar.gz",
]


def run(command):
    return subprocess.run(command, text=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--formal", action="store_true", help="将未满足的正式发行门槛作为失败退出")
    args = parser.parse_args()
    required = [DIST / name for name in ASSETS]
    missing = [path.name for path in required if not path.is_file()]
    checksums_path = DIST / "SHA256SUMS.txt"
    failures = []
    if missing:
        failures.append("缺少资产：" + "、".join(missing))
    checksums = {}
    if checksums_path.is_file():
        for line in checksums_path.read_text(encoding="utf-8").splitlines():
            fields = line.split()
            if len(fields) == 2:
                checksums[fields[1].lstrip("*")] = fields[0]
    else:
        failures.append("缺少 SHA256SUMS.txt")

    rows = []
    for path in required:
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = checksums.get(path.name)
        if digest != expected:
            failures.append(f"{path.name} 的散列与 SHA256SUMS.txt 不一致")
        rows.append(f"| `{path.name}` | {path.stat().st_size} | `{digest}` |")

    for arch in ("arm64",):
        pkg = DIST / f"TapSayAudio-2ch-{VERSION}-{arch}.pkg"
        if pkg.is_file():
            check = run(["/usr/sbin/pkgutil", "--check-signature", str(pkg)])
            signature = check.stdout + check.stderr
            if "no signature" in signature.lower():
                failures.append(f"{arch} PKG 未签名")
            elif check.returncode != 0:
                failures.append(f"{arch} PKG 签名检查无法完成")
            image = DIST / f"TapSayAudio-2ch-{VERSION}-{arch}.dmg"
            if image.is_file():
                # A mounted older image at this path can make hdiutil report EAGAIN.
                with tempfile.TemporaryDirectory(prefix="tapsay-image-verify-") as directory:
                    snapshot = Path(directory) / image.name
                    shutil.copyfile(image, snapshot)
                    verify = run(["/usr/bin/hdiutil", "verify", str(snapshot)])
                if verify.returncode != 0:
                    failures.append(f"{arch} DMG 完整性检查失败")

    source = DIST / f"TapSayAudio-2ch-{VERSION}-source.tar.gz"
    if source.is_file():
        with tarfile.open(source, "r:gz") as archive:
            names = set(archive.getnames())
        prefix = f"TapSayAudio-2ch-{VERSION}/"
        for relative in (
            "LICENSE",
            "THIRD_PARTY_NOTICES.md",
            "third_party/blackhole/LICENSE",
            "third_party/blackhole/UPSTREAM.md",
            "Tools/Transaction/main.swift",
            "Tools/Transaction/Uninstaller.swift",
            "Tools/Transaction/UninstallResult.swift",
            "Tools/Transaction/UninstallDeviceCheck.swift",
            "Tools/Transaction/TransactionSupport.swift",
            "Tools/Transaction/TransactionRecord.swift",
            "Tools/Transaction/TransactionRecovery.swift",
            "Tools/Transaction/HistoricalCleanup.swift",
            "Tests/TransactionRecordTests.swift",
            "Tests/HistoricalCleanupTests.swift",
            "Tests/UninstallResultTests.swift",
            "Tools/Transaction/Diagnose.swift",
            "Tools/Transaction/Loopback.swift",
            "scripts/build-native-tools.sh",
        ):
            if prefix + relative not in names:
                failures.append(f"源码归档缺少 {relative}")

    failures.extend(
        [
            "Developer ID 签名及公证未完成",
            "arm64 升级、降级、真实卸载清理、真实遥控器及第三方软件链路未完成（同版重装、收据、三种采样率合成环回、隔离回滚与历史清理及主程序默认格式单声道图已通过）",
            "Intel x86_64 暂不支持",
            "GitHub Release 未发布，真实下载地址不存在",
        ]
    )
    report = [
        f"# TapSay Audio {VERSION} 本地发行检查",
        "",
        "状态：**不可正式发布**。本报告不创建 GitHub Release，也不设置下载地址。",
        "",
        "## 本地资产",
        "",
        "| 文件 | 字节数 | SHA-256 |",
        "| --- | ---: | --- |",
        *(rows or ["| 无 | — | — |"]),
        "",
        "## 未满足门槛",
        "",
        *(f"- {item}" for item in failures or ["无"]),
        "",
        "当前下载 URL：未配置。",
        "",
    ]
    output = DIST / "RELEASE-READINESS.md"
    output.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    if args.formal and failures:
        return 2
    return 1 if missing else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, tarfile.TarError) as error:
        print(f"发行检查失败：{error}", file=sys.stderr)
        raise SystemExit(1)
