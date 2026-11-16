"""Release content errors are independent of formal publication prerequisites."""
import hashlib
from pathlib import Path
import subprocess
import tarfile


def command(arguments):
    return subprocess.run(arguments, text=True, capture_output=True)


def audit(directory, metadata, run=command):
    directory = Path(directory)
    version = metadata['product']['version']
    prefix = 'TapSayAudio-2ch-' + version
    names = [prefix + '.pkg', prefix + '-arm64.dmg', prefix + '-source.tar.gz']
    errors, pending, rows = [], [], []
    checksums = {}
    try:
        for line in (directory / 'SHA256SUMS.txt').read_text().splitlines():
            value, name = line.split()
            name = name.lstrip('*')
            if name in checksums:
                raise ValueError('校验文件包含重复项')
            checksums[name] = value
    except (OSError, ValueError) as error:
        errors.append('无法读取校验文件：' + str(error))
    for name in names:
        path = directory / name
        if not path.is_file():
            errors.append('缺少资产：' + name)
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if checksums.get(name) != digest:
            errors.append(name + ' 的散列不一致')
        rows.append({'name': name, 'bytes': path.stat().st_size, 'sha256': digest})
    package = directory / names[0]
    if package.is_file():
        result = run(['/usr/sbin/pkgutil', '--check-signature', str(package)])
        if result.returncode != 0 or 'no signature' in (result.stdout + result.stderr).lower():
            pending.append('安装包尚未完成正式签名验证')
    image = directory / names[1]
    if image.is_file() and run(['/usr/bin/hdiutil', 'verify', str(image)]).returncode != 0:
        errors.append('DMG 完整性检查失败')
    source = directory / names[2]
    if source.is_file():
        try:
            with tarfile.open(source, 'r:gz') as bundle:
                members = bundle.getmembers()
                entries = {m.name for m in members if m.isfile()}
                required = ['LICENSE', 'THIRD_PARTY_NOTICES.md', 'config/product.json',
                    'third_party/blackhole/LICENSE', 'third_party/blackhole/upstream/BlackHole/BlackHole.c',
                    'third_party/blackhole/tapsay-identity.patch', 'Tools/BuildIcon.swift',
                    'third_party/blackhole/plugin-properties.patch',
                    'third_party/blackhole/control-list-properties.patch',
                    'third_party/blackhole/SOURCE-SHA256.json',
                    'scripts/driver_sources.py', 'Tests/DriverContract.c', 'Tests/DriverSourceTests.py',
                    'scripts/prepare-driver-source.py', 'scripts/check-reference-source.py',
                    'scripts/prepare-build-metadata.py', 'scripts/check-dmg.py',
                    'scripts/assemble-release.py', 'BUILD-PROVENANCE.json',
                    'SOURCE-REVISION.txt',
                    'scripts/test-hal-contract.sh',
                    'Tools/Transaction/main.swift', 'Tools/Transaction/Uninstaller.swift',
                    'scripts/build-driver.sh', 'scripts/build-native-tools.sh', 'scripts/product.py',
                    'scripts/build-packages.py', 'scripts/release_checks.py', 'scripts/publish-artifacts.py']
                for relative in required:
                    if prefix + '/' + relative not in entries:
                        errors.append('源码归档缺少 ' + relative)
                for member in members:
                    if member.isfile() and bundle.extractfile(member).read(4) in (
                            b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xca\xfe\xba\xbe'):
                        errors.append('源码归档夹带二进制：' + member.name)
        except (OSError, tarfile.TarError) as error:
            errors.append('源码归档不可读：' + str(error))
    pending.extend(['签名、公证及公开下载地址尚未完成', '本轮安装卸载与语音链路等待用户人工测试'])
    return {'content_errors': errors, 'publication_pending': pending, 'assets': rows}


def exit_code(result, formal=False):
    if result['content_errors']:
        return 1
    return 2 if formal and result['publication_pending'] else 0
