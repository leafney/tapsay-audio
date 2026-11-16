#!/usr/bin/env python3
"""Build and verify a complete release before atomically publishing it."""
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

from product import ROOT, load_product, render_uninstaller


def build(output):
    metadata = load_product()
    architecture = 'arm64'
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
            def run(args, extra=None):
                subprocess.run(args, check=True, cwd=ROOT, env=dict(env, **(extra or {})))
            run(['bash', 'scripts/build-native-tools.sh', '--arch', architecture])
            result_path = work / 'driver-result.json'
            run(['bash', 'scripts/build-driver.sh', '--arch', architecture],
                {'TAPSAY_BUILD_RESULT': str(result_path)})
            result = json.loads(result_path.read_text())
            bundle = Path(result['bundle'])
            binary = bundle / 'Contents/MacOS/TapSayAudio'
            if hashlib.sha256(binary.read_bytes()).hexdigest() != result['driver_sha256']:
                raise ValueError('本次构建结果散列不符')
            run(['bash', 'scripts/run-driver-contract-tests.sh', '--build-result', str(result_path)])
            run(['python3', 'scripts/test-native-transaction.py', '--build-result', str(result_path)])
            version = metadata['product']['version']
            prefix = 'TapSayAudio-2ch-' + version
            scripts, empty, image_root = work / 'scripts', work / 'empty', work / 'image'
            scripts.mkdir(); empty.mkdir(); image_root.mkdir()
            import shutil
            shutil.copytree(bundle, scripts / 'package-payload/TapSayAudio.driver')
            native = ROOT / '.build/native/arm64'
            shutil.copy2(native / 'TapSayAudioTransaction', scripts / 'TapSayAudioTransaction')
            shutil.copy2(ROOT / 'config/product.json', scripts / 'product.json')
            for name in ('preinstall', 'postinstall'):
                shutil.copy2(ROOT / 'packaging/pkg-scripts' / name, scripts / name)
                (scripts / name).chmod(0o755)
            package = release / (prefix + '.pkg')
            run(['/usr/bin/pkgbuild', '--root', str(empty), '--scripts', str(scripts),
                 '--identifier', metadata['driver']['package_receipt_identifier'],
                 '--version', version, '--install-location', '/', '--min-os-version',
                 metadata['product']['minimum_macos'], str(package)])
            run(['python3', 'scripts/check-package.py', str(package), 'arm64'])
            app = image_root / (metadata['uninstaller']['display_name'] + '.app')
            render_uninstaller(app, metadata, native)
            run(['/usr/bin/codesign', '--force', '--deep', '--sign', '-', '--timestamp=none', str(app)])
            run(['python3', 'scripts/check-uninstaller.py', str(app)])
            shutil.copy2(package, image_root / package.name)
            readme = (ROOT / 'packaging/dmg/README.txt').read_text().replace('@VERSION@', version)
            (image_root / '说明.txt').write_text(readme)
            shutil.copy2(ROOT / 'LICENSE', image_root / 'GPL-3.0.txt')
            shutil.copy2(ROOT / 'THIRD_PARTY_NOTICES.md', image_root / '第三方许可说明.md')
            run(['/usr/bin/hdiutil', 'create', '-volname', 'TapSay Audio arm64', '-srcfolder',
                 str(image_root), '-format', 'UDZO', str(release / (prefix + '-arm64.dmg'))])
            run(['bash', 'scripts/build-source-archive.sh'], {'OUT': str(release)})
            assets = [package.name, prefix + '-arm64.dmg', prefix + '-source.tar.gz']
            (release / 'SHA256SUMS.txt').write_text(''.join(
                hashlib.sha256((release / name).read_bytes()).hexdigest() + '  ' + name + '\n'
                for name in assets))
            (release / 'BUILD-RESULT.json').write_text(json.dumps(result, indent=2)+'\n')
            run(['python3', 'scripts/check-release-readiness.py', '--dist', str(release)])
            spec = importlib.util.spec_from_file_location('publish_artifacts', ROOT / 'scripts/publish-artifacts.py')
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            module.publish(release, output)
            print('已发布完整本地产物：' + str(output))


if __name__ == '__main__':
    build(os.environ.get('OUT', str(ROOT / 'dist')))
