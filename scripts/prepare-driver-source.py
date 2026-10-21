#!/usr/bin/env python3
"""Copy frozen upstream inputs and apply only the reference and identity patches."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "third_party/blackhole"


def prepare(destination):
    hashes = json.loads((BASE / "SOURCE-SHA256.json").read_text())
    for relative, expected in hashes.items():
        actual = hashlib.sha256((BASE / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError("构建输入散列不符：" + relative)
    shutil.copytree(BASE / "upstream", destination)
    for patch in ("blackhole-device-usb.patch", "tapsay-identity.patch"):
        subprocess.run(["/usr/bin/patch", "-p1", "-i", str(BASE / patch),
                        "-d", str(destination)], check=True)
    return hashes


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("用法：prepare-driver-source.py 新建源码目录")
    prepare(Path(sys.argv[1]))
