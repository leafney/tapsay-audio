"""Frozen input verification and the explicitly reviewed patch sequence."""
import hashlib
import json
from pathlib import Path
import subprocess

BASE = Path(__file__).resolve().parents[1] / 'third_party/blackhole'
PROPERTY_PATCHES = ('plugin-properties.patch', 'control-list-properties.patch')
PATCHES = ('blackhole-device-usb.patch', 'tapsay-identity.patch', *PROPERTY_PATCHES)


def verify_inputs():
    hashes = json.loads((BASE / 'SOURCE-SHA256.json').read_text())
    for required in (*PATCHES, 'upstream/BlackHole/BlackHole.c'):
        if required not in hashes:
            raise ValueError('构建输入未固定散列：' + required)
    for relative, expected in hashes.items():
        if hashlib.sha256((BASE / relative).read_bytes()).hexdigest() != expected:
            raise ValueError('构建输入散列不符：' + relative)
    return hashes


def apply_patches(destination, patches):
    for name in patches:
        subprocess.run(['/usr/bin/patch', '--batch', '--forward', '-F', '0', '-p1',
                        '-i', str(BASE / name), '-d', str(destination)],
                       check=True, stdout=subprocess.DEVNULL)
