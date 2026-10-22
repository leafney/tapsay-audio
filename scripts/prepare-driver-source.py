#!/usr/bin/env python3
"""Copy frozen upstream inputs and apply the explicit reviewed patches."""
from pathlib import Path
import shutil
import sys
from driver_sources import BASE, PATCHES, verify_inputs, apply_patches



def prepare(destination):
    hashes = verify_inputs()
    shutil.copytree(BASE / "upstream", destination)
    apply_patches(destination, PATCHES)
    return hashes


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("用法：prepare-driver-source.py 新建源码目录")
    prepare(Path(sys.argv[1]))
