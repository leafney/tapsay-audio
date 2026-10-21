#!/usr/bin/env python3
"""Reproduce the frozen reference defect and test an unshipped proposal."""
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THIRD_PARTY = ROOT / "third_party/blackhole"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    for relative, expected in {
        "upstream/BlackHole/BlackHole.c": "5194703e8923713d15159b951b8fe9a8be08e7c0fb7c05b17c8e865e4c2effb6",
        "blackhole-device-usb.patch": "51dea42771bc432573433f76a0bfb140d9463db112d568f0192e97b5b7a2dc5f",
    }.items():
        if digest(THIRD_PARTY / relative) != expected:
            raise RuntimeError("固定输入散列不匹配：" + relative)
    evidence = ROOT / ".build/experiments/evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="hal-control-list-", dir=evidence))
    reference = work / "reference"
    shutil.copytree(THIRD_PARTY / "upstream", reference)

    def patch(directory, name):
        subprocess.run(["/usr/bin/patch", "-p1", "-i", str(THIRD_PARTY / name),
                        "-d", str(directory)], check=True, stdout=subprocess.DEVNULL)

    patch(reference, "blackhole-device-usb.patch")
    tapsay = work / "tapsay"
    shutil.copytree(reference, tapsay)
    patch(tapsay, "tapsay-identity.patch")
    candidate = work / "proposal"
    shutil.copytree(tapsay, candidate)
    patch(candidate, "proposals/control-list-safety.patch")
    results = []
    for label, directory, mode, expected in [
        ("reference-formats", reference, "formats", 0),
        ("reference-control", reference, "control-list", 134),
        ("tapsay-control", tapsay, "control-list", 134),
        ("proposal-control", candidate, "control-matrix", 0),
        ("proposal-formats", candidate, "formats", 0),
    ]:
        source = directory / "BlackHole/BlackHole.c"
        command = ["/bin/bash", str(ROOT / "scripts/test-hal-contract.sh"), str(source), mode]
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = work / (label + ".log")
        log.write_text(result.stdout)
        row = {"label": label, "source_sha256": digest(source),
               "exit_code": result.returncode, "expected_exit": expected,
               "log_sha256": digest(log)}
        results.append(row)
        (work / "results.json").write_text(json.dumps(results, indent=2) + "\n")
        if result.returncode != expected or (expected and "global-buffer-overflow" not in result.stdout):
            raise RuntimeError("复现结果不符，查看：" + str(log))
        print(label + "：退出码 " + str(result.returncode), flush=True)
    print("基线 HAL 验证失败；候选补丁通过 60 项控制列表用例。候选未进入构建或安装包。")
    print("证据：" + str(work.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
