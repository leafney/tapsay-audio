#!/usr/bin/env python3
"""Archive the fixed reference, reviewed fixes and complete build/test tooling."""
import argparse
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
META = json.loads((ROOT / 'config/product.json').read_text())
VERSION = META['product']['version']
OUT = Path(os.environ.get('OUT', str(ROOT / 'dist')))
PREFIX = 'TapSayAudio-2ch-' + VERSION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-metadata', type=Path)
    args = parser.parse_args()
    files = {ROOT / p for p in ('README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md',
        '.gitignore', '.gitattributes', 'config/product.json',
        'Uninstaller.app/Contents/Info.plist',
        'Uninstaller.app/Contents/MacOS/TapSayAudioUninstaller',
        'third_party/blackhole/LICENSE', 'third_party/blackhole/UPSTREAM.md',
        'third_party/blackhole/UPSTREAM-VERSION', 'third_party/blackhole/SOURCE-SHA256.json',
        'third_party/blackhole/blackhole-device-usb.patch', 'third_party/blackhole/tapsay-identity.patch',
        'third_party/blackhole/plugin-properties.patch',
        'third_party/blackhole/control-list-properties.patch',
        'docs/plan/2026-10-22-driver-property-fixes.md',
        'docs/discuss/2026-10-22-driver-property-fixes.md',
        'docs/plan/2026-10-21-reference-driver-cleanup.md',
        'docs/discuss/2026-10-21-reference-driver-cleanup.md',
        'docs/plan/2026-10-22-peripheral-improvements.md',
        'docs/discuss/2026-10-22-stable-version-review.md',
        'docs/discuss/2026-11-16-github-actions-packaging.md',
        'docs/plan/2026-11-16-github-actions-packaging.md',
        'docs/implementation/2026-11-16-github-actions-packaging.md')}
    for folder, suffixes in [('Tools', {'.swift'}), ('Tests', {'.swift', '.c', '.py'}),
                             ('packaging', None), ('third_party/blackhole/upstream', None)]:
        files.update(p for p in (ROOT / folder).rglob('*')
                     if p.is_file() and (suffixes is None or p.suffix in suffixes)
                     and p.name != '.DS_Store')
    scripts = ['build-driver.sh', 'prepare-build-metadata.py',
        'prepare-driver-source.py', 'check-reference-source.py',
        'build-native-tools.sh', 'build-packages.sh', 'check-package.py', 'check-metadata.py',
        'check-dmg.py', 'assemble-release.py',
        'check-uninstaller.py', 'check-release-readiness.py', 'build-source-archive.sh',
        'build-source-archive.py', 'test-native-transaction.py', 'product.py', 'release_checks.py',
        'publish-artifacts.py', 'build-packages.py', 'driver_sources.py', 'run-driver-contract-tests.sh',
        'run-driver-contract-tests.py', 'test-hal-contract.sh', 'check-driver-artifact.py',
        'publish-github-release.py', 'release-signing-mode.py']
    files.update(ROOT / 'scripts' / name for name in scripts)
    files.update((ROOT / '.github/workflows').glob('*.yml'))
    for path in files:
        if not path.is_file() or path.is_symlink():
            raise RuntimeError('源码缺失或不是普通文件：' + str(path))
    OUT.mkdir(parents=True, exist_ok=True)
    archive = OUT / (PREFIX + '-source.tar.gz')
    temporary = archive.with_suffix('.tmp')
    revision = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],
                              capture_output=True, text=True)
    existing = ROOT / 'SOURCE-REVISION.txt'
    provenance = revision.stdout.strip() if revision.returncode == 0 else (
        existing.read_text().strip() if existing.exists() else 'source archive rebuild')
    build_metadata_path = args.build_metadata
    if build_metadata_path is None and os.environ.get('TAPSAY_BUILD_METADATA'):
        build_metadata_path = Path(os.environ['TAPSAY_BUILD_METADATA'])
    if build_metadata_path is None:
        build_metadata = {
            'version': VERSION,
            'build_number': META['product']['build_number'],
            'tag': '',
            'source_sha': provenance.splitlines()[0],
        }
    else:
        build_metadata = json.loads(build_metadata_path.read_text())
        if (build_metadata.get('version') != VERSION
                or build_metadata.get('build_number') != META['product']['build_number']):
            raise RuntimeError('构建来源信息与有效产品配置不一致')
    if re.fullmatch(r'[0-9a-f]{40}', str(build_metadata.get('source_sha', ''))) is None:
        raise RuntimeError('构建来源信息缺少有效源码提交')
    if revision.returncode == 0:
        dirty = subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'], text=True)
        provenance += '\nworking_tree=' + ('dirty' if dirty else 'clean')
    provenance += (
        '\ntag=' + str(build_metadata.get('tag', ''))
        + '\nversion=' + VERSION
        + '\nbuild_number=' + META['product']['build_number']
    )
    with tarfile.open(temporary, 'w:gz') as bundle:
        for path in sorted(files):
            bundle.add(path, arcname=PREFIX + '/' + str(path.relative_to(ROOT)), recursive=False)
        data = (provenance + '\n').encode()
        entry = tarfile.TarInfo(PREFIX + '/SOURCE-REVISION.txt')
        entry.size = len(data)
        bundle.addfile(entry, io.BytesIO(data))
        provenance_data = (
            json.dumps(build_metadata, ensure_ascii=False, indent=2) + '\n'
        ).encode()
        entry = tarfile.TarInfo(PREFIX + '/BUILD-PROVENANCE.json')
        entry.size = len(provenance_data)
        bundle.addfile(entry, io.BytesIO(provenance_data))
    temporary.replace(archive)
    print('源码归档：' + str(archive))


if __name__ == '__main__':
    main()
