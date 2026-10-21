#!/usr/bin/env python3
"""Require byte-identical C after normalizing the permitted product identity edits."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
IDENTITY_MACROS = {
    "kDriver_Name", "kPlugIn_BundleID", "kPlugIn_Icon", "kHas_Driver_Name_Format",
    "kBox_UID", "kDevice_UID", "kDevice2_UID", "kDevice_ModelUID",
    "kDevice_Name", "kDevice2_Name", "kManufacturer_Name",
}


def normalize(text):
    lines = []
    for line in text.splitlines(keepends=True):
        match = re.match(r"#define\s+(\w+)\s+", line)
        if match and match.group(1) in IDENTITY_MACROS:
            line = "#define " + match.group(1) + " <product identity>\n"
        lines.append(line)
    text = "".join(lines).replace("TapSayAudio_Create", "BlackHole_Create")
    for literal in ("Apple Inc.", "Existential Audio Inc.", "TapSay", "BlackHole",
                    "BlackHole Box", "TapSay Audio", "TapSay Audio Box"):
        text = text.replace('CFSTR("' + literal + '")', 'CFSTR("<product identity>")')
    text = text.replace("Box implemented by the TapSay Audio driver.", "Box implemented by the BlackHole driver.")
    return text


def main():
    source = Path(sys.argv[1]) / "BlackHole/BlackHole.c"
    with tempfile.TemporaryDirectory(prefix="tapsay-source-audit-") as directory:
        reference = Path(directory) / "reference"
        shutil.copytree(ROOT / "third_party/blackhole/upstream", reference)
        subprocess.run(["patch", "-p1", "-i", str(ROOT / "third_party/blackhole/blackhole-device-usb.patch"),
                        "-d", str(reference)], check=True, stdout=subprocess.DEVNULL)
        expected = (reference / "BlackHole/BlackHole.c").read_text()
        actual = source.read_text()
        if normalize(expected) != normalize(actual):
            raise SystemExit("参考一致性失败：C 中存在产品身份之外的改动")
    print(json.dumps({"status": "passed", "mode": "reference-identity-only",
                      "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                      "algorithm_changes": 0}, indent=2))


if __name__ == "__main__":
    main()
