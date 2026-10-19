#!/usr/bin/env python3
"""Verify the shipped native installer in an isolated temporary root."""

import json
import os
import plistlib
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
META_PATH = ROOT / "config/product.json"
META = json.loads(META_PATH.read_text(encoding="utf-8"))
ARCH = subprocess.check_output(["/usr/bin/uname", "-m"], text=True).strip()
TOOL = ROOT / f".build/native/{ARCH}/TapSayAudioTransaction"
DRIVER = ROOT / f".build/driver/{ARCH}/Build/Products/Release/TapSayAudio.driver"


def run(tool, root, metadata, *args, success=True):
    result = subprocess.run(
        [str(tool), *args, "--metadata", str(metadata), "--test-root", str(root)],
        text=True,
        capture_output=True,
    )
    assert (result.returncode == 0) == success, (
        args,
        result.stdout,
        result.stderr,
    )
    return result


def main():
    assert TOOL.is_file() and DRIVER.is_dir(), "先构建驱动和原生工具"
    protocol_test = ROOT / f".build/native/{ARCH}/UninstallResultTests"
    subprocess.run(
        ["xcrun", "swiftc", "-module-cache-path", str(ROOT / ".build/native/module-cache"),
         str(ROOT / "Tools/Transaction/UninstallResult.swift"),
         str(ROOT / "Tools/Transaction/UninstallDeviceCheck.swift"),
         str(ROOT / "Tests/UninstallResultTests.swift"), "-framework", "CoreAudio",
         "-o", str(protocol_test)], check=True,
    )
    subprocess.run([str(protocol_test)], check=True)
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary).resolve()
        payload = base / "payload/TapSayAudio.driver"
        payload.parent.mkdir()
        shutil.copytree(DRIVER, payload)
        metadata = base / "product.json"
        shutil.copy2(META_PATH, metadata)
        target = base / "Library/Audio/Plug-Ins/HAL/TapSayAudio.driver"
        state = base / "Library/Application Support/TapSay Audio/install-state.json"

        run(TOOL, base, metadata, "install", str(payload))
        original_binary = (target / "Contents/MacOS/TapSayAudio").read_bytes()
        original_state = json.loads(state.read_text())
        assert original_state["verification_status"] == "not_run"

        run(TOOL, base, metadata, "install", str(payload), "--inject-failure", "backup", success=False)
        assert (target / "Contents/MacOS/TapSayAudio").read_bytes() == original_binary
        assert json.loads(state.read_text()) == original_state

        run(TOOL, base, metadata, "install", str(payload), "--inject-failure", "deployed", success=False)
        assert (target / "Contents/MacOS/TapSayAudio").read_bytes() == original_binary
        assert json.loads(state.read_text()) == original_state

        run(TOOL, base, metadata, "install", str(payload), "--inject-failure", "rollback", success=False)
        previous = target.with_name(next(name for name in os.listdir(target.parent) if name.startswith(".TapSayAudio-") and name.endswith(".previous")))
        assert previous.is_dir() and (target / "Contents/MacOS/TapSayAudio").read_bytes() == original_binary

        parked = target.with_name("TapSayAudio.parked")
        target.rename(parked)
        target.symlink_to(parked, target_is_directory=True)
        run(TOOL, base, metadata, "uninstall", "--yes", success=False)
        assert target.is_symlink()
        target.unlink()
        parked.rename(target)

        denied = run(TOOL, base, metadata, "uninstall", "--uninstall-report", success=False)
        assert json.loads(denied.stdout)["status"] == "failed"
        assert target.is_dir() and state.is_file(), "缺少卸载确认不得删除"
        missing = subprocess.run(
            [str(TOOL), "uninstall", "--yes", "--metadata", str(base / "missing.json"),
             "--test-root", str(base), "--uninstall-report"], text=True, capture_output=True)
        assert missing.returncode != 0 and json.loads(missing.stdout)["status"] == "failed"
        assert target.is_dir() and state.is_file(), "配置读取失败不得删除"

        # Execute exactly the shared argv used by the GUI, without administrator access.
        arguments = json.loads(subprocess.check_output(
            [str(protocol_test), "--arguments", str(metadata)], text=True))
        result = subprocess.run([str(TOOL), *arguments, "--test-root", str(base)],
                                text=True, capture_output=True)
        assert result.returncode == 0, (result.stdout, result.stderr)
        report = json.loads(result.stdout)
        assert report["status"] == "unverified" and report["deviceStatus"] == "notChecked"
        assert report["driverAbsent"] and report["receiptAbsent"] and report["stateAbsent"]
        assert not target.exists() and not state.exists()
        assert previous.is_dir(), "卸载必须保留唯一恢复备份"
        repeated = run(TOOL, base, metadata, "uninstall", "--yes", "--uninstall-report")
        assert json.loads(repeated.stdout)["status"] == "unverified"
        bad = run(TOOL, base, metadata, "--privileged-uninstall", "--uninstall-report", success=False)
        assert json.loads(bad.stdout)["status"] == "failed", "旧错误命令不能报告成功"

    print("原生安装事务测试通过")


if __name__ == "__main__":
    main()
