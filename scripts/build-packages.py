#!/usr/bin/env python3
"""Build and verify the DMG and PKG for one native architecture."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from product import ROOT, load_product, render_uninstaller

ARCHITECTURES = ('arm64', 'x86_64')
DEVELOPER_ID_ENVIRONMENT = (
    'DEVELOPER_ID_APPLICATION_IDENTITY',
    'DEVELOPER_ID_INSTALLER_IDENTITY',
    'APPLE_TEAM_ID',
    'APP_STORE_CONNECT_ISSUER_ID',
    'APP_STORE_CONNECT_KEY_ID',
    'APP_STORE_CONNECT_PRIVATE_KEY_PATH',
)


def signing_status(signing_mode, architecture):
    platform = 'Apple Silicon' if architecture == 'arm64' else 'Intel Mac'
    if signing_mode == 'adhoc':
        return f'未认证内部测试包：仅供测试，尚未使用 Developer ID 签名或完成 Apple 公证。目标平台：{platform}。'
    return 'Developer ID 已签名并公证。'


def developer_id_environment():
    missing = [name for name in DEVELOPER_ID_ENVIRONMENT if not os.environ.get(name)]
    if missing:
        raise ValueError('Developer ID 环境缺失：' + ', '.join(missing))
    return {name: os.environ[name] for name in DEVELOPER_ID_ENVIRONMENT}


def verify_developer_identities(environment):
    team_id = environment['APPLE_TEAM_ID']
    if re.fullmatch(r'[A-Z0-9]{10}', team_id) is None:
        raise ValueError('APPLE_TEAM_ID 格式无效')
    for kind, variable in (
        ('Developer ID Application', 'DEVELOPER_ID_APPLICATION_IDENTITY'),
        ('Developer ID Installer', 'DEVELOPER_ID_INSTALLER_IDENTITY'),
    ):
        identity = environment[variable]
        if (not identity.startswith(kind + ': ')
                or not identity.endswith(' (' + team_id + ')')):
            raise ValueError(kind + ' 身份与 APPLE_TEAM_ID 不匹配')
        result = subprocess.run(
            ['/usr/bin/security', 'find-identity', '-v', '-p', 'codesigning'],
            text=True,
            capture_output=True,
        )
        result.check_returncode()
        if f'"{identity}"' not in result.stdout:
            raise ValueError(kind + ' 身份不可用')


def notarize(image, environment):
    authentication = [
        '--key', environment['APP_STORE_CONNECT_PRIVATE_KEY_PATH'],
        '--key-id', environment['APP_STORE_CONNECT_KEY_ID'],
        '--issuer', environment['APP_STORE_CONNECT_ISSUER_ID'],
    ]
    result = subprocess.run(
        [
            '/usr/bin/xcrun', 'notarytool', 'submit', str(image),
            *authentication, '--wait', '--timeout', '30m',
            '--output-format', 'json',
        ],
        text=True,
        capture_output=True,
        cwd=ROOT,
    )
    if result.returncode != 0:
        raise ValueError('公证提交失败：' + (result.stderr or result.stdout).strip())
    try:
        submission = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ValueError('公证服务返回了无法解析的结果') from error
    status = submission.get('status')
    submission_id = submission.get('id')
    if status != 'Accepted':
        details = ''
        if submission_id:
            log_result = subprocess.run(
                [
                    '/usr/bin/xcrun', 'notarytool', 'log', submission_id,
                    *authentication, '--output-format', 'json',
                ],
                text=True,
                capture_output=True,
                cwd=ROOT,
            )
            details = (log_result.stdout or log_result.stderr).strip()
        message = 'Apple 公证未通过：' + str(status)
        if details:
            message += '\n' + details
        raise ValueError(message)
    return submission_id


def build(architecture, output, signing_mode='adhoc'):
    if architecture not in ARCHITECTURES:
        raise ValueError('目标架构无效：' + str(architecture))
    metadata = load_product()
    if architecture not in metadata['product']['architectures']:
        raise ValueError('目标架构不在产品配置中：' + architecture)
    if signing_mode not in ('adhoc', 'developer-id'):
        raise ValueError('签名模式无效：' + str(signing_mode))
    signing_environment = None
    if signing_mode == 'developer-id':
        signing_environment = developer_id_environment()
        verify_developer_identities(signing_environment)

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
                signing_arguments = [
                    '/usr/bin/codesign', '--force', '--options', 'runtime',
                ]
                if signing_mode == 'adhoc':
                    signing_arguments.extend(['--sign', '-', '--timestamp=none'])
                else:
                    signing_arguments.extend([
                        '--sign',
                        signing_environment['DEVELOPER_ID_APPLICATION_IDENTITY'],
                        '--timestamp',
                    ])
                run([*signing_arguments, str(native / name)])

            result_path = work / ('driver-result-' + architecture + '.json')
            driver_arguments = [
                'bash', 'scripts/build-driver.sh', '--arch', architecture,
                '--signing-mode', signing_mode,
            ]
            if signing_mode == 'developer-id':
                driver_arguments.extend([
                    '--application-identity',
                    signing_environment['DEVELOPER_ID_APPLICATION_IDENTITY'],
                ])
            run(
                driver_arguments,
                {'TAPSAY_BUILD_RESULT': str(result_path)},
            )
            result = json.loads(result_path.read_text())
            expected_result = {
                'architecture': architecture,
                'version': metadata['product']['version'],
                'build_number': metadata['product']['build_number'],
                'minimum_macos': metadata['product']['minimum_macos'],
                'signing_mode': signing_mode,
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
            if signing_mode == 'developer-id':
                signed_package = release / (prefix + '-signed.pkg')
                run([
                    '/usr/bin/productsign', '--sign',
                    signing_environment['DEVELOPER_ID_INSTALLER_IDENTITY'],
                    str(package), str(signed_package),
                ])
                signed_package.replace(package)
            run([
                'python3', 'scripts/check-package.py', str(package), architecture,
                '--signing-mode', signing_mode,
            ])

            app = image_root / (metadata['uninstaller']['display_name'] + '.app')
            render_uninstaller(app, metadata, native, architecture)
            app_arguments = [
                '/usr/bin/codesign', '--force', '--deep', '--options', 'runtime',
            ]
            if signing_mode == 'adhoc':
                app_arguments.extend(['--sign', '-', '--timestamp=none'])
            else:
                app_arguments.extend([
                    '--sign',
                    signing_environment['DEVELOPER_ID_APPLICATION_IDENTITY'],
                    '--timestamp',
                ])
            run([*app_arguments, str(app)])
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
            if signing_mode == 'developer-id':
                run([
                    '/usr/bin/codesign', '--force', '--options', 'runtime',
                    '--sign',
                    signing_environment['DEVELOPER_ID_APPLICATION_IDENTITY'],
                    '--timestamp', str(image),
                ])
                notarize(image, signing_environment)
                run(['/usr/bin/xcrun', 'stapler', 'staple', str(image)])
                run(['/usr/bin/xcrun', 'stapler', 'validate', str(image)])
                run([
                    '/usr/sbin/spctl', '--assess', '--type', 'open',
                    '--context', 'context:primary-signature', '-v', str(image),
                ])
                run(['/usr/bin/codesign', '--verify', '--strict', str(image)])

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
