#!/usr/bin/env python3
"""Build and verify the DMG and PKG for one native architecture."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from product import ROOT, load_product, render_uninstaller

ARCHITECTURES = ('arm64', 'x86_64')


def signing_status(signing_mode, architecture):
    platform = 'Apple Silicon' if architecture == 'arm64' else 'Intel Mac'
    if signing_mode == 'adhoc':
        return f'未认证内部测试包：仅供测试，尚未使用 Developer ID 签名或完成 Apple 公证。目标平台：{platform}。'
    return 'Developer ID 已签名并公证。'


def build(architecture, output, signing_mode='adhoc'):
    if architecture not in ARCHITECTURES:
        raise ValueError('目标架构无效：' + str(architecture))
    metadata = load_product()
    if architecture not in metadata['product']['architectures']:
        raise ValueError('目标架构不在产品配置中：' + architecture)
    if signing_mode == 'developer-id':
        raise ValueError('Developer ID 签名阶段尚未配置')
    if signing_mode != 'adhoc':
        raise ValueError('签名模式无效：' + str(signing_mode))

    output = Path(output).absolute()
    if output == ROOT or output in ROOT.parents or output.is_symlink():
        raise ValueError('产物目录不能覆盖源码或使用符号链接')
    output.parent.mkdir(parents=True, exist_ok=True)
    lock_path = output.parent / ('.' + output.name + '.build.lock')
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with tempfile.TemporaryDirectory(prefix='.tapsay-package-', dir=output.parent) as temporary:
            work = Path(temporary)
            release = work / 'release'
            release.mkdir()
            env = dict(os.environ, LC_ALL='C', LANG='C')

            def run(args, extra=None, cwd=ROOT):
                subprocess.run(args, check=True, cwd=cwd, env=dict(env, **(extra or {})))

            run(['bash', 'scripts/build-native-tools.sh', '--arch', architecture])
            native = ROOT / '.build/native' / architecture
            for name in (
                'TapSayAudioTransaction',
                'TapSayAudioUninstaller',
                'TapSayAudioDiagnose',
                'TapSayAudioLoopback',
            ):
                run([
                    '/usr/bin/codesign', '--force', '--sign', '-',
                    '--timestamp=none', str(native / name),
                ])

            result_path = work / ('driver-result-' + architecture + '.json')
            run(
                ['bash', 'scripts/build-driver.sh', '--arch', architecture],
                {'TAPSAY_BUILD_RESULT': str(result_path)},
            )
            result = json.loads(result_path.read_text())
            expected_result = {
                'architecture': architecture,
                'version': metadata['product']['version'],
                'build_number': metadata['product']['build_number'],
                'minimum_macos': metadata['product']['minimum_macos'],
            }
            for key, value in expected_result.items():
                if result.get(key) != value:
                    raise ValueError('驱动构建记录不匹配：' + key)
            bundle = Path(result['bundle'])
            binary = bundle / 'Contents/MacOS/TapSayAudio'
            if hashlib.sha256(binary.read_bytes()).hexdigest() != result['driver_sha256']:
                raise ValueError('本次构建结果散列不符')
            run(['bash', 'scripts/run-driver-contract-tests.sh',
                 '--build-result', str(result_path)])
            run(['python3', 'scripts/test-native-transaction.py',
                 '--build-result', str(result_path)])

            version = metadata['product']['version']
            prefix = 'TapSayAudio-2ch-' + version + '-' + architecture
            scripts, empty, image_root = work / 'scripts', work / 'empty', work / 'image'
            scripts.mkdir()
            empty.mkdir()
            image_root.mkdir()
            shutil.copytree(bundle, scripts / 'package-payload/TapSayAudio.driver')
            shutil.copy2(native / 'TapSayAudioTransaction', scripts / 'TapSayAudioTransaction')
            shutil.copy2(ROOT / 'config/product.json', scripts / 'product.json')
            for name in ('preinstall', 'postinstall'):
                shutil.copy2(ROOT / 'packaging/pkg-scripts' / name, scripts / name)
                (scripts / name).chmod(0o755)

            package = release / (prefix + '.pkg')
            run([
                '/usr/bin/pkgbuild', '--root', str(empty), '--scripts', str(scripts),
                '--identifier', metadata['driver']['package_receipt_identifier'],
                '--version', version, '--install-location', '/', '--min-os-version',
                metadata['product']['minimum_macos'], str(package),
            ])
            run(['python3', 'scripts/check-package.py', str(package), architecture])

            app = image_root / (metadata['uninstaller']['display_name'] + '.app')
            render_uninstaller(app, metadata, native, architecture)
            run([
                '/usr/bin/codesign', '--force', '--deep', '--sign', '-',
                '--timestamp=none', str(app),
            ])
            run(['python3', 'scripts/check-uninstaller.py', str(app), architecture])
            shutil.copy2(package, image_root / package.name)

            platform = 'Apple Silicon' if architecture == 'arm64' else 'Intel Mac'
            readme = (ROOT / 'packaging/dmg/README.txt').read_text()
            readme = (readme
                      .replace('@VERSION@', version)
                      .replace('@PLATFORM@', platform)
                      .replace('@ARCH@', architecture)
                      .replace('@SIGNING_STATUS@',
                               signing_status(signing_mode, architecture)))
            (image_root / '说明.txt').write_text(readme)
            shutil.copy2(ROOT / 'LICENSE', image_root / 'GPL-3.0.txt')
            shutil.copy2(ROOT / 'THIRD_PARTY_NOTICES.md', image_root / '第三方许可说明.md')
            image = release / (prefix + '.dmg')
            run([
                '/usr/bin/hdiutil', 'create',
                '-volname', 'TapSay Audio ' + architecture,
                '-srcfolder', str(image_root), '-format', 'UDZO', str(image),
            ])
            run(['python3', 'scripts/check-dmg.py', str(image), architecture])

            assets = [package.name, image.name]
            (release / 'SHA256SUMS.txt').write_text(''.join(
                hashlib.sha256((release / name).read_bytes()).hexdigest() + '  ' + name + '\n'
                for name in assets
            ))
            run(['/usr/bin/shasum', '-a', '256', '-c', 'SHA256SUMS.txt'], cwd=release)

            spec = importlib.util.spec_from_file_location(
                'publish_artifacts', ROOT / 'scripts/publish-artifacts.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.publish(release, output)
            print('已发布 ' + architecture + ' 本地产物：' + str(output))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--arch', required=True, choices=ARCHITECTURES)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--signing-mode', choices=('adhoc', 'developer-id'), default='adhoc')
    args = parser.parse_args()
    build(args.arch, args.output, args.signing_mode)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
