#!/usr/bin/env python3
"""Check the exact driver and source selected by a build result."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from product import ROOT
from driver_sources import PATCHES, verify_inputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-result', type=Path, required=True)
    args = parser.parse_args()
    result = json.loads(args.build_result.read_text())
    hashes = verify_inputs()
    if (result.get('driver_mode') != 'reference-with-property-fixes'
            or result.get('patches_sha256') != {name: hashes[name] for name in PATCHES}):
        raise ValueError('本次构建记录未匹配已声明修复补丁')
    bundle, source = Path(result['bundle']), Path(result['source'])
    digest = hashlib.sha256((bundle / 'Contents/MacOS/TapSayAudio').read_bytes()).hexdigest()
    if digest != result['driver_sha256']:
        raise ValueError('驱动与本次构建记录不一致')
    for command in [
        ['python3', str(ROOT / 'Tests/DriverSourceTests.py')],
        ['python3', str(ROOT / 'scripts/check-reference-source.py'), str(source)],
        ['python3', str(ROOT / 'scripts/check-driver-artifact.py'), str(bundle), 'arm64'],
        ['bash', str(ROOT / 'scripts/test-hal-contract.sh'), str(source / 'BlackHole/BlackHole.c'), 'formats'],
        ['bash', str(ROOT / 'scripts/test-hal-contract.sh'), str(source / 'BlackHole/BlackHole.c'), 'plugin-properties'],
        ['bash', str(ROOT / 'scripts/test-hal-contract.sh'), str(source / 'BlackHole/BlackHole.c'), 'control-matrix'],
    ]:
        subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
