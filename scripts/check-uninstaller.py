#!/usr/bin/env python3
"""Inspect the generated uninstaller app for one target architecture."""
import argparse
import json
from pathlib import Path
import plistlib
import subprocess

from product import load_product

MACHO_MAGICS = {
    b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf',
    b'\xce\xfa\xed\xfe', b'\xfe\xed\xfa\xce',
    b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca',
    b'\xca\xfe\xba\xbf', b'\xbf\xba\xfe\xca',
}


def macho_files(app):
    for path in sorted((app / 'Contents/MacOS').iterdir()):
        if path.is_symlink():
            raise ValueError('卸载 APP 不得包含符号链接：' + str(path))
        if path.is_file() and path.read_bytes()[:4] in MACHO_MAGICS:
            yield path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('app', type=Path)
    parser.add_argument('architecture', choices=('arm64', 'x86_64'))
    args = parser.parse_args()
    app = args.app.resolve()
    architecture = args.architecture
    metadata = load_product()
    if architecture not in metadata['product']['architectures']:
        raise ValueError('目标架构不在产品配置中：' + architecture)

    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    if info['CFBundleIdentifier'] != metadata['uninstaller']['bundle_identifier']:
        raise ValueError('卸载标识不一致')
    if info['CFBundleExecutable'] != 'TapSayAudioUninstaller-' + architecture:
        raise ValueError('卸载主可执行文件与目标架构不一致')
    if info['CFBundleShortVersionString'] != metadata['product']['version']:
        raise ValueError('卸载版本不一致')
    if info['CFBundleVersion'] != metadata['product']['build_number']:
        raise ValueError('卸载构建号不一致')
    if info['LSMinimumSystemVersion'] != metadata['product']['minimum_macos']:
        raise ValueError('卸载工具最低系统不一致')
    packaged_metadata = json.loads((app / 'Contents/Resources/product.json').read_text())
    if packaged_metadata != metadata:
        raise ValueError('内置配置不一致')

    required = [
        app / 'Contents/MacOS' / ('TapSayAudioUninstaller-' + architecture),
        app / 'Contents/MacOS' / ('TapSayAudioTransaction-' + architecture),
    ]
    if not (app / 'Contents/MacOS' / info['CFBundleExecutable']).is_file():
        raise ValueError('卸载 APP 主可执行文件缺失')
    for binary in required:
        if not binary.is_file():
            raise ValueError('卸载 APP 缺少架构工具：' + binary.name)
    binaries = list(macho_files(app))
    if {path.resolve() for path in required} != {path.resolve() for path in binaries}:
        raise ValueError('卸载 APP 的 Mach-O 集合不匹配')
    for binary in binaries:
        architectures = subprocess.check_output(
            ['/usr/bin/lipo', '-archs', str(binary)], text=True
        ).split()
        if architectures != [architecture]:
            raise ValueError(binary.name + ' 的架构不匹配')
        build_versions = subprocess.check_output(
            ['/usr/bin/xcrun', 'vtool', '-show-build', str(binary)], text=True
        )
        if f"minos {metadata['product']['minimum_macos']}" not in build_versions:
            raise ValueError(binary.name + ' 的最低系统不匹配')
    subprocess.run(
        ['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)],
        check=True,
    )
    print('卸载 APP 产物检查通过：' + architecture)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print('卸载 APP 检查失败：' + str(error))
        raise SystemExit(1)
