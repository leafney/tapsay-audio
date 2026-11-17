#!/usr/bin/env python3
"""Verify one architecture DMG and inspect its user-visible contents."""
import argparse
from pathlib import Path
import subprocess
import tempfile
import time

from product import ROOT, load_product


def verify_image(image):
    result = None
    for _ in range(10):
        result = subprocess.run(
            ['/usr/bin/hdiutil', 'verify', str(image)],
            text=True,
            capture_output=True,
        )
        if result.returncode == 0:
            return
        time.sleep(1)
    if result is not None:
        result.check_returncode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('image', type=Path)
    parser.add_argument('architecture', choices=('arm64', 'x86_64'))
    parser.add_argument(
        '--signing-mode',
        choices=('adhoc', 'developer-id'),
        default='adhoc',
    )
    args = parser.parse_args()
    image = args.image.resolve()
    architecture = args.architecture
    metadata = load_product()
    if architecture not in metadata['product']['architectures']:
        raise ValueError('目标架构不在产品配置中：' + architecture)

    version = metadata['product']['version']
    prefix = f'TapSayAudio-2ch-{version}-{architecture}'
    if image.name != prefix + '.dmg':
        raise ValueError('DMG 文件名与版本或架构不一致')
    if not image.is_file() or image.stat().st_size == 0:
        raise ValueError('DMG 不存在或为空')
    verify_image(image)

    platform = 'Apple Silicon' if architecture == 'arm64' else 'Intel Mac'
    with tempfile.TemporaryDirectory(prefix='tapsay-dmg-check-') as temporary:
        mountpoint = Path(temporary) / 'mount'
        mountpoint.mkdir()
        attached = False
        try:
            subprocess.run([
                '/usr/bin/hdiutil', 'attach', '-readonly', '-nobrowse',
                '-mountpoint', str(mountpoint), str(image),
            ], check=True, text=True, capture_output=True)
            attached = True
            required = {
                prefix + '.pkg': mountpoint / (prefix + '.pkg'),
                metadata['uninstaller']['display_name'] + '.app':
                    mountpoint / (metadata['uninstaller']['display_name'] + '.app'),
                '说明.txt': mountpoint / '说明.txt',
                'GPL-3.0.txt': mountpoint / 'GPL-3.0.txt',
                '第三方许可说明.md': mountpoint / '第三方许可说明.md',
                '.VolumeIcon.icns': mountpoint / '.VolumeIcon.icns',
            }
            for name, path in required.items():
                if not path.exists():
                    raise ValueError('DMG 缺少 ' + name)
            subprocess.run([
                'python3', str(ROOT / 'scripts/check-package.py'),
                str(required[prefix + '.pkg']), architecture,
                '--signing-mode', args.signing_mode,
            ], check=True, cwd=ROOT)
            if required['.VolumeIcon.icns'].read_bytes()[:4] != b'icns':
                raise ValueError('DMG 卷图标格式错误')
            attributes = subprocess.check_output(
                ['/usr/bin/xcrun', 'GetFileInfo', '-a', str(mountpoint)],
                text=True,
                cwd=ROOT,
            ).strip()
            if 'C' not in attributes:
                raise ValueError('DMG 卷未设置自定义图标')
            readme = required['说明.txt'].read_text()
            for placeholder in ('@VERSION@', '@ARCH@', '@PLATFORM@', '@SIGNING_STATUS@'):
                if placeholder in readme:
                    raise ValueError('DMG 说明仍含占位符：' + placeholder)
            if platform not in readme or architecture not in readme:
                raise ValueError('DMG 说明中的平台与架构不匹配')
            subprocess.run([
                'python3', str(ROOT / 'scripts/check-uninstaller.py'),
                str(required[metadata['uninstaller']['display_name'] + '.app']),
                architecture,
            ], check=True, cwd=ROOT)
        finally:
            if attached:
                subprocess.run([
                    '/usr/bin/hdiutil', 'detach', str(mountpoint),
                ], check=True, text=True, capture_output=True)
    print('DMG 内容检查通过：' + image.name)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print('DMG 检查失败：' + str(error))
        raise SystemExit(1)
