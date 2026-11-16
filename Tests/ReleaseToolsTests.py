"""Exercise release failure boundaries without installing or loading audio drivers."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tarfile
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from product import load_product, render_uninstaller
from release_checks import audit, exit_code

spec = importlib.util.spec_from_file_location('publisher', ROOT / 'scripts/publish-artifacts.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)

metadata_spec = importlib.util.spec_from_file_location(
    'prepare_build_metadata', ROOT / 'scripts/prepare-build-metadata.py')
prepare_build_metadata = importlib.util.module_from_spec(metadata_spec)
metadata_spec.loader.exec_module(prepare_build_metadata)

assemble_spec = importlib.util.spec_from_file_location(
    'assemble_release', ROOT / 'scripts/assemble-release.py')
assemble_release = importlib.util.module_from_spec(assemble_spec)
assemble_spec.loader.exec_module(assemble_release)


class ReleaseToolsTests(unittest.TestCase):
    def test_version_and_rendering(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            metadata = copy.deepcopy(load_product())
            metadata['product'].update(version='0.1.1', build_number='2')
            config = base / 'product.json'
            config.write_text(json.dumps(metadata))
            self.assertEqual(load_product(config)['product']['version'], '0.1.1')
            native = base / 'native'; native.mkdir()
            for name in ['TapSayAudioUninstaller', 'TapSayAudioTransaction']:
                (native / name).write_text('test executable')
            app = base / 'app'
            render_uninstaller(app, metadata, native, 'arm64')
            info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
            self.assertEqual((info['CFBundleShortVersionString'], info['CFBundleVersion']), ('0.1.1', '2'))
            self.assertEqual(json.loads((app / 'Contents/Resources/product.json').read_text()), metadata)
            self.assertTrue((app / 'Contents/MacOS/TapSayAudioUninstaller-arm64').is_file())
            self.assertTrue((app / 'Contents/MacOS/TapSayAudioTransaction-arm64').is_file())
            self.assertFalse((app / 'Contents/MacOS/TapSayAudioTransaction-x86_64').exists())
            for bad in ['../release', '0.1.1\n', '01.1.0', '0.1', '']:
                metadata['product']['version'] = bad
                config.write_text(json.dumps(metadata))
                with self.assertRaises(ValueError): load_product(config)

    def test_architecture_configuration_contract(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            metadata = copy.deepcopy(load_product())
            config = base / 'product.json'
            for invalid in ([], ['arm64'], ['x86_64', 'arm64'],
                            ['arm64', 'arm64'], ['arm64', 'universal2']):
                candidate = copy.deepcopy(metadata)
                candidate['product']['architectures'] = invalid
                config.write_text(json.dumps(candidate))
                with self.assertRaises(ValueError):
                    load_product(config)

    def test_manual_build_metadata_preserves_configuration_version(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            config = base / 'product.json'
            output = base / 'build-metadata.json'
            github_output = base / 'github-output.txt'
            config.write_bytes((ROOT / 'config/product.json').read_bytes())
            environment = dict(os.environ, GITHUB_OUTPUT=str(github_output))
            subprocess.run([
                sys.executable,
                str(ROOT / 'scripts/prepare-build-metadata.py'),
                '--mode', 'manual',
                '--build-number', '73',
                '--config', str(config),
                '--output-json', str(output),
            ], check=True, env=environment)
            effective = load_product(config)
            metadata = json.loads(output.read_text())
            self.assertEqual(effective['product']['version'], '0.1.1')
            self.assertEqual(effective['product']['build_number'], '73')
            self.assertEqual(metadata['version'], '0.1.1')
            self.assertEqual(metadata['build_number'], '73')
            self.assertEqual(metadata['tag'], '')
            self.assertRegex(metadata['source_sha'], r'^[0-9a-f]{40}$')
            self.assertEqual(github_output.read_text().splitlines(), [
                'version=0.1.1', 'build_number=73', 'tag='])

    def test_tag_build_metadata_uses_strict_tag_version(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            config = base / 'product.json'
            output = base / 'build-metadata.json'
            config.write_bytes((ROOT / 'config/product.json').read_bytes())
            subprocess.run([
                sys.executable,
                str(ROOT / 'scripts/prepare-build-metadata.py'),
                '--mode', 'tag',
                '--tag', 'v2.30.4',
                '--build-number', '91',
                '--config', str(config),
                '--output-json', str(output),
            ], check=True)
            effective = load_product(config)
            metadata = json.loads(output.read_text())
            self.assertEqual(effective['product']['version'], '2.30.4')
            self.assertEqual(effective['product']['build_number'], '91')
            self.assertEqual(metadata['version'], '2.30.4')
            self.assertEqual(metadata['build_number'], '91')
            self.assertEqual(metadata['tag'], 'v2.30.4')
            self.assertRegex(metadata['source_sha'], r'^[0-9a-f]{40}$')

    def test_invalid_build_input_leaves_configuration_unchanged(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            config = base / 'product.json'
            output = base / 'build-metadata.json'
            config.write_bytes((ROOT / 'config/product.json').read_bytes())
            original = config.read_bytes()
            invalid_tags = [
                '2.30.4', 'v02.30.4', 'v2.3', 'v2.3.4-beta.1',
                'v2.3.4.1', 'vv2.3.4', 'v2.03.4', '']
            for tag in invalid_tags:
                result = subprocess.run([
                    sys.executable,
                    str(ROOT / 'scripts/prepare-build-metadata.py'),
                    '--mode', 'tag',
                    '--tag', tag,
                    '--build-number', '91',
                    '--config', str(config),
                    '--output-json', str(output),
                ], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0, tag)
                self.assertEqual(config.read_bytes(), original)
                self.assertFalse(output.exists())
            for build_number in ['0', '-1', '01', 'abc', '']:
                result = subprocess.run([
                    sys.executable,
                    str(ROOT / 'scripts/prepare-build-metadata.py'),
                    '--mode', 'manual',
                    '--build-number', build_number,
                    '--config', str(config),
                    '--output-json', str(output),
                ], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0, build_number)
                self.assertEqual(config.read_bytes(), original)
                self.assertFalse(output.exists())

    def test_metadata_prepare_failure_does_not_replace_configuration(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            config = base / 'product.json'
            output = base / 'build-metadata.json'
            config.write_bytes((ROOT / 'config/product.json').read_bytes())
            original = config.read_bytes()
            real_write_temporary = prepare_build_metadata.write_temporary
            calls = 0

            def fail_second_write(path, content):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError('injected output failure')
                return real_write_temporary(path, content)

            with mock.patch.object(
                    prepare_build_metadata, 'write_temporary',
                    side_effect=fail_second_write):
                with self.assertRaises(OSError):
                    prepare_build_metadata.prepare(
                        'tag', 'v1.2.3', '42', config, output)
            self.assertEqual(config.read_bytes(), original)
            self.assertFalse(output.exists())

    def test_architecture_build_interfaces_reject_invalid_values(self):
        commands = [
            [str(ROOT / 'scripts/build-driver.sh')],
            [str(ROOT / 'scripts/build-driver.sh'), '--arch', 'universal2'],
            [str(ROOT / 'scripts/build-native-tools.sh')],
            [str(ROOT / 'scripts/build-native-tools.sh'), '--arch', 'arm64e'],
            [sys.executable, str(ROOT / 'scripts/check-driver-artifact.py'),
             '/missing/driver', 'universal2'],
        ]
        for command in commands:
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0, command)

    def test_assemble_release_contains_only_public_assets(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            arm64 = base / 'arm64'
            x86_64 = base / 'x86_64'
            output = base / 'release'
            arm64.mkdir()
            x86_64.mkdir()
            metadata = load_product()
            version = metadata['product']['version']
            for directory, architecture in ((arm64, 'arm64'), (x86_64, 'x86_64')):
                prefix = f'TapSayAudio-2ch-{version}-{architecture}'
                names = [prefix + '.pkg', prefix + '.dmg']
                for name in names:
                    (directory / name).write_bytes(architecture.encode() + b'-' + name.encode())
                (directory / 'SHA256SUMS.txt').write_text(''.join(
                    hashlib.sha256((directory / name).read_bytes()).hexdigest()
                    + '  ' + name + '\n' for name in names))

            def make_source_archive(directory, build_metadata):
                del build_metadata
                (directory / f'TapSayAudio-2ch-{version}-source.tar.gz').write_bytes(b'source')

            with mock.patch.object(assemble_release.subprocess, 'run'), \
                    mock.patch.object(
                        assemble_release, 'build_source_archive',
                        side_effect=make_source_archive):
                assemble_release.assemble(
                    arm64, x86_64, output, version, '14.0')

            public_names = {
                f'TapSayAudio-2ch-{version}-arm64.dmg',
                f'TapSayAudio-2ch-{version}-x86_64.dmg',
                f'TapSayAudio-2ch-{version}-source.tar.gz',
                'SHA256SUMS.txt',
            }
            self.assertEqual({path.name for path in output.iterdir()}, public_names)
            checksums = {
                line.split()[1]: line.split()[0]
                for line in (output / 'SHA256SUMS.txt').read_text().splitlines()
            }
            self.assertEqual(
                set(checksums),
                public_names - {'SHA256SUMS.txt'},
            )
            for name, checksum in checksums.items():
                self.assertEqual(
                    hashlib.sha256((output / name).read_bytes()).hexdigest(),
                    checksum,
                )

    def test_assemble_release_rejects_bad_input_hash(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            arm64 = base / 'arm64'
            x86_64 = base / 'x86_64'
            output = base / 'release'
            arm64.mkdir()
            x86_64.mkdir()
            metadata = load_product()
            version = metadata['product']['version']
            for directory, architecture in ((arm64, 'arm64'), (x86_64, 'x86_64')):
                prefix = f'TapSayAudio-2ch-{version}-{architecture}'
                for suffix in ('.pkg', '.dmg'):
                    (directory / (prefix + suffix)).write_bytes(b'asset')
                (directory / 'SHA256SUMS.txt').write_text(
                    hashlib.sha256(b'asset').hexdigest() + '  ' + prefix + '.pkg\n'
                    + hashlib.sha256(b'asset').hexdigest() + '  ' + prefix + '.dmg\n')
            (arm64 / f'TapSayAudio-2ch-{version}-arm64.dmg').write_bytes(b'corrupted')
            with self.assertRaises(ValueError):
                assemble_release.assemble(
                    arm64, x86_64, output, version, '14.0')
            self.assertFalse(output.exists())

    def test_release_failures_have_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            metadata = load_product(); prefix = 'TapSayAudio-2ch-' + metadata['product']['version']
            subprocess.run(['bash', str(ROOT/'scripts/build-source-archive.sh')], check=True,
                           env=dict(os.environ, OUT=t), stdout=subprocess.DEVNULL)
            for suffix in ['.pkg', '-arm64.dmg']:
                (base / (prefix + suffix)).write_bytes(b'fixture')
            names = [prefix + suffix for suffix in ['.pkg', '-arm64.dmg', '-source.tar.gz']]
            sums = ''.join(hashlib.sha256((base/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in names)
            (base / 'SHA256SUMS.txt').write_text(sums)
            ok = lambda args: types.SimpleNamespace(returncode=0, stdout='', stderr='')
            self.assertEqual(exit_code(audit(base, metadata, ok)), 0)
            self.assertEqual(exit_code(audit(base, metadata, ok), True), 2)
            (base/names[0]).write_bytes(b'corrupted')
            self.assertEqual(exit_code(audit(base, metadata, ok)), 1)
            (base/names[0]).write_bytes(b'fixture')
            bad_image = lambda args: types.SimpleNamespace(
                returncode=1 if 'hdiutil' in args[0] else 0, stdout='', stderr='')
            self.assertEqual(exit_code(audit(base, metadata, bad_image)), 1)
            (base/'SHA256SUMS.txt').unlink()
            self.assertEqual(exit_code(audit(base, metadata, ok)), 1)
            (base/'SHA256SUMS.txt').write_text(sums)
            with tarfile.open(base/names[2], 'w:gz'): pass
            (base/'SHA256SUMS.txt').write_text(''.join(
                hashlib.sha256((base/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in names))
            result = audit(base, metadata, ok)
            self.assertEqual(exit_code(result), 1)
            self.assertTrue(any('源码归档缺少' in e for e in result['content_errors']))

    def test_build_failure_preserves_existing_release(self):
        spec = importlib.util.spec_from_file_location('builder', ROOT / 'scripts/build-packages.py')
        builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as t:
            output = Path(t)/'dist'; output.mkdir()
            (output/'old.pkg').write_bytes(b'previous package')
            (output/'SHA256SUMS.txt').write_bytes(b'previous checksums')
            with mock.patch.object(builder.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'injected')):
                with self.assertRaises(subprocess.CalledProcessError):
                    builder.build('arm64', output)
            self.assertEqual((output/'old.pkg').read_bytes(), b'previous package')
            self.assertEqual((output/'SHA256SUMS.txt').read_bytes(), b'previous checksums')
            self.assertFalse(list(Path(t).glob('.tapsay-package-*')))

    def test_publish_is_all_or_nothing(self):
        with tempfile.TemporaryDirectory() as t:
            old, new = Path(t)/'dist', Path(t)/'stage'
            old.mkdir(); new.mkdir()
            (old/'package').write_bytes(b'old'); (old/'SHA256SUMS.txt').write_bytes(b'old sums')
            (new/'package').write_bytes(b'new'); (new/'SHA256SUMS.txt').write_bytes(b'new sums')
            with mock.patch.object(publisher.ctypes, 'CDLL', side_effect=OSError('injected failure')):
                with self.assertRaises(OSError): publisher.publish(new, old)
            self.assertEqual((old/'package').read_bytes(), b'old')
            self.assertEqual((old/'SHA256SUMS.txt').read_bytes(), b'old sums')
            publisher.publish(new, old)
            self.assertEqual((old/'package').read_bytes(), b'new')
            self.assertEqual((old/'SHA256SUMS.txt').read_bytes(), b'new sums')
            self.assertEqual((new/'package').read_bytes(), b'old')


if __name__ == '__main__':
    unittest.main()
