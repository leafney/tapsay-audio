"""Verify the public two-architecture release asset set."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile


def command(arguments):
    return subprocess.run(arguments, text=True, capture_output=True)


def check_source_archive(path, prefix, metadata, errors):
    try:
        with tarfile.open(path, 'r:gz') as bundle:
            members = bundle.getmembers()
            entries = {
                member.name.removeprefix(prefix + '/'): member
                for member in members
                if member.isfile()
            }
            required = [
                'LICENSE', 'THIRD_PARTY_NOTICES.md', 'config/product.json',
                '.github/workflows/build-artifacts.yml',
                '.github/workflows/package-arch.yml',
                '.github/workflows/release.yml',
                'third_party/blackhole/LICENSE',
                'third_party/blackhole/upstream/BlackHole/BlackHole.c',
                'third_party/blackhole/tapsay-identity.patch',
                'Tools/BuildIcon.swift', 'Tools/Transaction/main.swift',
                'Tools/Transaction/Uninstaller.swift',
                'third_party/blackhole/plugin-properties.patch',
                'third_party/blackhole/control-list-properties.patch',
                'third_party/blackhole/SOURCE-SHA256.json',
                'scripts/driver_sources.py', 'scripts/prepare-driver-source.py',
                'scripts/check-reference-source.py', 'scripts/prepare-build-metadata.py',
                'scripts/test-hal-contract.sh', 'scripts/build-driver.sh',
                'scripts/build-native-tools.sh', 'scripts/product.py',
                'scripts/build-packages.py', 'scripts/check-dmg.py',
                'scripts/assemble-release.py', 'scripts/release_checks.py',
                'scripts/publish-artifacts.py', 'scripts/publish-github-release.py',
                'Tests/DriverContract.c',
                'Tests/DriverSourceTests.py', 'Tests/ReleaseToolsTests.py',
                'BUILD-PROVENANCE.json', 'SOURCE-REVISION.txt',
                'docs/plan/2026-11-16-github-actions-packaging.md',
                'docs/implementation/2026-11-16-github-actions-packaging.md',
            ]
            for relative in required:
                if relative not in entries:
                    errors.append('源码归档缺少 ' + relative)
            for relative, member in entries.items():
                data = bundle.extractfile(member).read(4)
                if data in (
                    b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf',
                    b'\xca\xfe\xba\xbe', b'\xbf\xba\xfe\xca',
                ):
                    errors.append('源码归档夹带二进制：' + relative)
            provenance_member = entries.get('BUILD-PROVENANCE.json')
            if provenance_member is not None:
                provenance = json.loads(bundle.extractfile(provenance_member).read())
                if provenance.get('version') != metadata['product']['version']:
                    errors.append('源码归档版本与产品配置不一致')
                if provenance.get('build_number') != metadata['product']['build_number']:
                    errors.append('源码归档构建号与产品配置不一致')
                if re.fullmatch(r'[0-9a-f]{40}', str(provenance.get('source_sha', ''))) is None:
                    errors.append('源码归档缺少有效源码提交')
    except (OSError, tarfile.TarError, json.JSONDecodeError) as error:
        errors.append('源码归档不可读：' + str(error))


def audit(directory, metadata, run=command, formal=False, unverified=False):
    if formal and unverified:
        raise ValueError('认证模式不能使用未认证文件名')
    directory = Path(directory)
    version = metadata['product']['version']
    prefix = 'TapSayAudio-2ch-' + version
    names = [
        prefix + '-arm64' + ('-Unverified' if unverified else '') + '.dmg',
        prefix + '-x86_64' + ('-Unverified' if unverified else '') + '.dmg',
    ]
    errors, pending, rows = [], [], []
    if {path.name for path in directory.iterdir()} != set(names) | {'SHA256SUMS.txt'}:
        errors.append('公开资产集合错误')
    checksums = {}
    try:
        for line in (directory / 'SHA256SUMS.txt').read_text().splitlines():
            fields = line.split()
            if len(fields) != 2:
                raise ValueError('校验文件格式错误')
            value, name = fields
            name = name.lstrip('*')
            if name in checksums:
                raise ValueError('校验文件包含重复项')
            checksums[name] = value
        if set(checksums) != set(names):
            raise ValueError('校验文件资产集合错误')
    except (OSError, ValueError) as error:
        errors.append('无法读取校验文件：' + str(error))
    for name in names:
        path = directory / name
        if not path.is_file() or path.stat().st_size == 0:
            errors.append('缺少非空资产：' + name)
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if checksums.get(name) != digest:
            errors.append(name + ' 的散列不一致')
        rows.append({'name': name, 'bytes': path.stat().st_size, 'sha256': digest})

    for architecture, name in (
        ('arm64', names[0]),
        ('x86_64', names[1]),
    ):
        image = directory / name
        if image.is_file():
            command = [
                sys.executable, str(Path(__file__).with_name('check-dmg.py')),
                str(image), architecture,
            ]
            if formal:
                command.extend(['--signing-mode', 'developer-id'])
            if unverified:
                command.append('--unverified-name')
            result = run(command)
            if result.returncode != 0:
                errors.append(name + ' 的内容或架构检查失败')
            if formal:
                for signature_command in (
                    ['/usr/bin/codesign', '--verify', '--strict', str(image)],
                    ['/usr/bin/xcrun', 'stapler', 'validate', str(image)],
                    ['/usr/sbin/spctl', '--assess', '--type', 'open',
                     '--context', 'context:primary-signature', '-v', str(image)],
                ):
                    if run(signature_command).returncode != 0:
                        errors.append(name + ' 的签名、公证或系统策略检查失败')
                        break

    if not formal:
        pending.append('签名、公证、staple 与系统策略检查尚未执行')
    return {
        'content_errors': errors,
        'publication_pending': pending,
        'assets': rows,
    }


def exit_code(result, formal=False):
    if result['content_errors']:
        return 1
    return 2 if formal and result['publication_pending'] else 0
