#!/usr/bin/env python3
"""Verify the shipped native installer in an isolated temporary root."""

import argparse
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
parser = argparse.ArgumentParser()
parser.add_argument('--build-result', type=Path, required=True)
options = parser.parse_args()
BUILD_RESULT = json.loads(options.build_result.read_text())
ARCH = BUILD_RESULT.get('architecture')
if ARCH not in ('arm64', 'x86_64'):
    raise ValueError('构建记录中的架构无效')
TOOL = ROOT / f".build/native/{ARCH}/TapSayAudioTransaction"
DRIVER = Path(BUILD_RESULT['bundle'])


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


def transaction_root(root):
    return root / "Library/Application Support/TapSay Audio/transactions"


def assert_no_transaction_material(root, target):
    transactions = transaction_root(root)
    assert not transactions.exists() or not any(transactions.iterdir()), "安装成功后不得遗留事务目录"
    assert not [
        item for item in target.parent.iterdir()
        if item.name.startswith(".TapSayAudio-")
    ], "安装成功后不得遗留本次临时驱动"


def main():
    assert TOOL.is_file() and DRIVER.is_dir(), "先构建驱动和原生工具"
    protocol_test = ROOT / f".build/native/{ARCH}/UninstallResultTests"
    subprocess.run(
        ["xcrun", "swiftc", "-target", f"{ARCH}-apple-macosx14.0",
         "-module-cache-path", str(ROOT / f".build/native/module-cache/{ARCH}"),
         str(ROOT / "Tools/Transaction/UninstallResult.swift"),
         str(ROOT / "Tools/Transaction/TransactionSupport.swift"),
         str(ROOT / "Tools/Transaction/HistoricalCleanup.swift"),
         str(ROOT / "Tools/Transaction/UninstallDeviceCheck.swift"),
         str(ROOT / "Tests/UninstallResultTests.swift"), "-framework", "CoreAudio",
         "-o", str(protocol_test)], check=True,
    )
    subprocess.run([str(protocol_test)], check=True)
    transaction_test = ROOT / f".build/native/{ARCH}/TransactionRecordTests"
    subprocess.run(
        ["xcrun", "swiftc", "-target", f"{ARCH}-apple-macosx14.0",
         "-module-cache-path", str(ROOT / f".build/native/module-cache/{ARCH}"),
         str(ROOT / "Tools/Transaction/TransactionSupport.swift"),
         str(ROOT / "Tools/Transaction/TransactionRecord.swift"),
         str(ROOT / "Tests/TransactionRecordTests.swift"),
         "-o", str(transaction_test)], check=True,
    )
    subprocess.run([str(transaction_test)], check=True)
    history_test = ROOT / f".build/native/{ARCH}/HistoricalCleanupTests"
    subprocess.run(
        ["xcrun", "swiftc", "-target", f"{ARCH}-apple-macosx14.0",
         "-module-cache-path", str(ROOT / f".build/native/module-cache/{ARCH}"),
         str(ROOT / "Tools/Transaction/TransactionSupport.swift"),
         str(ROOT / "Tools/Transaction/HistoricalCleanup.swift"),
         str(ROOT / "Tests/HistoricalCleanupTests.swift"),
         "-o", str(history_test)], check=True,
    )
    subprocess.run([str(history_test), str(DRIVER)], check=True)
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
        assert_no_transaction_material(base, target)
        assert not (transaction_root(base) / "backup.driver").exists()
        original_binary = (target / "Contents/MacOS/TapSayAudio").read_bytes()
        original_state = json.loads(state.read_text())
        assert original_state["verification_status"] == "not_run"
        assert "backup" not in original_state

        run(TOOL, base, metadata, "install", str(payload), "--inject-failure", "backup", success=False)
        assert (target / "Contents/MacOS/TapSayAudio").read_bytes() == original_binary
        assert json.loads(state.read_text()) == original_state
        assert_no_transaction_material(base, target)

        run(TOOL, base, metadata, "install", str(payload), "--inject-failure", "deployed", success=False)
        assert (target / "Contents/MacOS/TapSayAudio").read_bytes() == original_binary
        assert json.loads(state.read_text()) == original_state
        assert_no_transaction_material(base, target)

        run(TOOL, base, metadata, "install", str(payload), "--inject-failure", "state-write", success=False)
        assert (target / "Contents/MacOS/TapSayAudio").read_bytes() == original_binary
        assert json.loads(state.read_text()) == original_state
        assert_no_transaction_material(base, target)

        run(TOOL, base, metadata, "install", str(payload), "--inject-failure", "move", success=False)
        assert (target / "Contents/MacOS/TapSayAudio").read_bytes() == original_binary
        assert json.loads(state.read_text()) == original_state
        assert_no_transaction_material(base, target)

        run(TOOL, base, metadata, "install", str(payload), "--inject-failure", "rollback", success=False)
        previous = target.with_name(next(
            name for name in os.listdir(target.parent)
            if name.startswith(".TapSayAudio-") and name.endswith(".previous")
        ))
        assert previous.is_dir() and (target / "Contents/MacOS/TapSayAudio").read_bytes() == original_binary
        records = list(transaction_root(base).glob("*/transaction.json"))
        assert len(records) == 1, "恢复失败必须保留唯一事务记录"
        record = json.loads(records[0].read_text())
        assert record["phase"] == "recovery_required"
        assert record["terminal"] == "recovery_required"
        blocked = run(TOOL, base, metadata, "install", str(payload), success=False)
        assert "待人工恢复" in blocked.stderr
        assert (target / "Contents/MacOS/TapSayAudio").read_bytes() == original_binary

        # Simulate an abnormal exit after the old driver moved but before deployment.
        shutil.rmtree(previous)
        target.rename(previous)
        record["phase"] = "replacing"
        record["terminal"] = "active"
        record["terminal_result"] = "none"
        record["cleanup"] = "none"
        record["cleanup_remaining_paths"] = []
        record["cleanup_reason"] = ""
        records[0].write_text(json.dumps(record), encoding="utf-8")
        run(TOOL, base, metadata, "install", str(payload))
        assert target.is_dir()
        assert_no_transaction_material(base, target)

        # A committed install must not roll back merely because temporary cleanup fails.
        deployed_binary = (target / "Contents/MacOS/TapSayAudio").read_bytes()
        deployed_state = json.loads(state.read_text())
        deployed_version = deployed_state["version"]
        run(TOOL, base, metadata, "install", str(payload), "--inject-failure", "cleanup", success=False)
        assert (target / "Contents/MacOS/TapSayAudio").read_bytes() == deployed_binary
        after_cleanup_failure = json.loads(state.read_text())
        assert after_cleanup_failure["version"] == deployed_version
        assert after_cleanup_failure["target"] == deployed_state["target"]
        assert after_cleanup_failure["device_uid"] == deployed_state["device_uid"]
        pending_records = list(transaction_root(base).glob("*/transaction.json"))
        assert len(pending_records) == 1, "提交后清理失败必须保留事务记录"
        pending = json.loads(pending_records[0].read_text())
        assert pending["phase"] == "committed"
        assert pending["terminal"] == "cleanup_pending"
        assert pending["terminal_result"] == "deployed"
        run(TOOL, base, metadata, "install", str(payload))
        assert_no_transaction_material(base, target)
        # Rolled-back metadata cleanup failure must not move the restored driver again.
        restored_binary = (target / "Contents/MacOS/TapSayAudio").read_bytes()
        run(TOOL, base, metadata, "install", str(payload),
            "--inject-failure", "cleanup-rollback", success=False)
        assert (target / "Contents/MacOS/TapSayAudio").read_bytes() == restored_binary
        pending_records = list(transaction_root(base).glob("*/transaction.json"))
        assert len(pending_records) == 1, "回滚后清理失败必须保留事务记录"
        pending = json.loads(pending_records[0].read_text())
        assert pending["phase"] == "rolled_back"
        assert pending["terminal"] == "cleanup_pending"
        assert pending["terminal_result"] == "rolled_back"
        run(TOOL, base, metadata, "install", str(payload))
        assert_no_transaction_material(base, target)
        historical = transaction_root(base) / "AAAAAAAA-BBBB-4CCC-8DDD-EEEEEEEEEEEE"
        historical.mkdir(parents=True)
        shutil.copytree(DRIVER, historical / "backup.driver")
        (historical / "previous-state.json").write_text(json.dumps({
            "target": str(target),
            "bundle_identifier": META["driver"]["bundle_identifier"],
            "device_uid": META["driver"]["device_uid"],
        }), encoding="utf-8")

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
        assert report["schemaVersion"] == 2
        assert report["cleanupStatus"] == "pendingDeviceRemoval"
        assert not target.exists() and not state.exists()
        assert historical.exists(), "测试环境无法确认设备消失时不得删除历史材料"
        repeated = run(TOOL, base, metadata, "uninstall", "--yes", "--uninstall-report")
        assert json.loads(repeated.stdout)["status"] == "unverified"
        bad = run(TOOL, base, metadata, "--privileged-uninstall", "--uninstall-report", success=False)
        assert json.loads(bad.stdout)["status"] == "failed", "旧错误命令不能报告成功"

    print("原生安装事务测试通过")


if __name__ == "__main__":
    main()
