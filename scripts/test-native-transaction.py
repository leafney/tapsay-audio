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

        run(TOOL, base, metadata, "uninstall", "--yes")
        assert not target.exists() and not state.exists()
        assert previous.is_dir(), "卸载必须保留唯一恢复备份"
        run(TOOL, base, metadata, "uninstall", "--yes")

    print("原生安装事务测试通过")


if __name__ == "__main__":
    main()
