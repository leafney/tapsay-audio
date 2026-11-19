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
from product import load_product, render_uninstaller, minimum_macos
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

publish_release_spec = importlib.util.spec_from_file_location(
    'publish_github_release', ROOT / 'scripts/publish-github-release.py')
publish_github_release = importlib.util.module_from_spec(publish_release_spec)
publish_release_spec.loader.exec_module(publish_github_release)

build_packages_spec = importlib.util.spec_from_file_location(
    'build_packages', ROOT / 'scripts/build-packages.py')
build_packages = importlib.util.module_from_spec(build_packages_spec)
build_packages_spec.loader.exec_module(build_packages)


class ReleaseToolsTests(unittest.TestCase):
    def test_minimum_system_versions_by_architecture(self):
        metadata = load_product()
        self.assertEqual(minimum_macos(metadata, 'arm64'), '14.0')
        self.assertEqual(minimum_macos(metadata, 'x86_64'), '13.0')
        with self.assertRaises(ValueError):
            minimum_macos(metadata, 'unknown')
        metadata['product']['minimum_macos_by_architecture'].pop('arm64')
        with self.assertRaises(ValueError):
            minimum_macos(metadata, 'x86_64')

    def test_signing_mode_requires_all_or_no_credentials(self):
        spec = importlib.util.spec_from_file_location('signing_mode', ROOT / 'scripts/release-signing-mode.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.select({}), 'adhoc')
        self.assertEqual(module.select(dict.fromkeys(module.NAMES, '  ')), 'adhoc')
        self.assertEqual(module.select(dict.fromkeys(module.NAMES, 'secret')), 'developer-id')
        for name in module.NAMES:
            with self.assertRaises(ValueError):
                module.select({name: 'secret'})
            almost = dict.fromkeys(module.NAMES, 'secret')
            almost[name] = ' '
            with self.assertRaises(ValueError):
                module.select(almost)

    def test_unverified_release_asset_names(self):
        with tempfile.TemporaryDirectory() as t:
            directory = Path(t)
            names = ('TapSayAudio-2ch-1.2.3-arm64-Unverified.dmg',
                     'TapSayAudio-2ch-1.2.3-x86_64-Unverified.dmg',
                     'TapSayAudio-2ch-1.2.3-source.tar.gz', 'SHA256SUMS.txt')
            for name in names:
                (directory / name).write_bytes(b'x')
            paths, _ = publish_github_release.expected_assets('1.2.3', directory, 'adhoc')
            self.assertEqual({p.name for p in paths}, set(names))
            with self.assertRaises(publish_github_release.ReleaseError):
                publish_github_release.expected_assets('1.2.3', directory, 'developer-id')

    def test_unverified_assembly_checks_and_renames_both_architectures(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            version = load_product()['product']['version']
            inputs = []
            for arch in ('arm64', 'x86_64'):
                directory = base / arch
                directory.mkdir()
                name = f'TapSayAudio-2ch-{version}-{arch}.dmg'
                (directory / name).write_bytes(arch.encode())
                (directory / 'SHA256SUMS.txt').write_text(
                    hashlib.sha256(arch.encode()).hexdigest() + '  ' + name + '\n')
                inputs.append(directory)

            def source(directory, metadata):
                (directory / f'TapSayAudio-2ch-{version}-source.tar.gz').write_bytes(b'source')

            result = {'content_errors': [], 'publication_pending': ['未公证'], 'assets': []}
            with mock.patch.object(assemble_release.subprocess, 'run') as run, \
                    mock.patch.object(assemble_release, 'build_source_archive', side_effect=source), \
                    mock.patch.object(assemble_release, 'audit', return_value=result) as audit_mock:
                assemble_release.assemble(*inputs, base / 'out', version, '14.0',
                                          formal=True, signing_mode='adhoc')
            self.assertEqual(run.call_count, 2)
            self.assertTrue(all('adhoc' in call.args[0] for call in run.call_args_list))
            self.assertTrue(audit_mock.call_args.kwargs['unverified'])
            names = {path.name for path in (base / 'out').iterdir()}
            self.assertIn(f'TapSayAudio-2ch-{version}-arm64-Unverified.dmg', names)
            self.assertIn(f'TapSayAudio-2ch-{version}-x86_64-Unverified.dmg', names)

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
            icon = base / 'TapSayAudioUninstaller.icns'
            icon.write_bytes(b'icns' + b'test')
            app = base / 'app'
            render_uninstaller(app, metadata, native, 'arm64', icon_path=icon)
            info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
            self.assertEqual((info['CFBundleShortVersionString'], info['CFBundleVersion']), ('0.1.1', '2'))
            self.assertEqual(info['CFBundleExecutable'], 'TapSayAudioUninstaller-arm64')
            self.assertEqual(info['CFBundleIconFile'], 'TapSayAudioUninstaller.icns')
            self.assertEqual(json.loads((app / 'Contents/Resources/product.json').read_text()), metadata)
            self.assertEqual(
                (app / 'Contents/Resources/TapSayAudioUninstaller.icns').read_bytes(),
                icon.read_bytes(),
            )
            self.assertTrue((app / 'Contents/MacOS/TapSayAudioUninstaller-arm64').is_file())
            self.assertTrue((app / 'Contents/MacOS/TapSayAudioTransaction-arm64').is_file())
            self.assertFalse((app / 'Contents/MacOS/TapSayAudioUninstaller').exists())
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
            source_metadata = copy.deepcopy(load_product())
            source_metadata['product']['version'] = '9.9.9'
            config.write_text(json.dumps(source_metadata))
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
            build_metadata = json.loads(output.read_text())
            self.assertEqual(effective['product']['version'], '9.9.9')
            self.assertEqual(effective['product']['build_number'], '73')
            self.assertEqual(build_metadata['version'], '9.9.9')
            self.assertEqual(build_metadata['build_number'], '73')
            self.assertEqual(build_metadata['tag'], '')
            self.assertRegex(build_metadata['source_sha'], r'^[0-9a-f]{40}$')
            self.assertEqual(github_output.read_text().splitlines(), [
                'version=9.9.9', 'build_number=73', 'tag='])

    def test_tag_build_metadata_uses_strict_tag_version(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            config = base / 'product.json'
            output = base / 'build-metadata.json'
            metadata = copy.deepcopy(load_product())
            metadata['upstream']['source_import_status'] = 'approved for distribution'
            config.write_text(json.dumps(metadata))
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
            metadata = copy.deepcopy(load_product())
            metadata['upstream']['source_import_status'] = 'approved for distribution'
            config.write_text(json.dumps(metadata))
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
            metadata = copy.deepcopy(load_product())
            metadata['upstream']['source_import_status'] = 'approved for distribution'
            config.write_text(json.dumps(metadata))
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

    def test_tag_build_metadata_requires_distribution_review(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            config = base / 'product.json'
            output = base / 'build-metadata.json'
            metadata = load_product()
            metadata['upstream']['source_import_status'] = 'integrated from fixed upstream commit; final distribution review pending'
            config.write_text(json.dumps(metadata))
            original = config.read_bytes()
            result = subprocess.run([
                sys.executable,
                str(ROOT / 'scripts/prepare-build-metadata.py'),
                '--mode', 'tag',
                '--tag', 'v1.2.3',
                '--build-number', '42',
                '--config', str(config),
                '--output-json', str(output),
            ], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('第三方分发审查尚未完成', result.stderr)
            self.assertEqual(config.read_bytes(), original)
            self.assertFalse(output.exists())

    def test_architecture_build_interfaces_reject_invalid_values(self):
        commands = [
            [str(ROOT / 'scripts/build-driver.sh')],
            [str(ROOT / 'scripts/build-driver.sh'), '--arch', 'universal2'],
            [str(ROOT / 'scripts/build-driver.sh'),
             '--arch', 'arm64', '--signing-mode', 'developer-id'],
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
                names = [prefix + '.dmg']
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
                (directory / (prefix + '.dmg')).write_bytes(b'asset')
                (directory / 'SHA256SUMS.txt').write_text(
                    hashlib.sha256(b'asset').hexdigest() + '  ' + prefix + '.dmg\n')
            (arm64 / f'TapSayAudio-2ch-{version}-arm64.dmg').write_bytes(b'corrupted')
            with self.assertRaises(ValueError):
                assemble_release.assemble(
                    arm64, x86_64, output, version, '14.0')
            self.assertFalse(output.exists())

    def test_formal_release_rechecks_signature_and_notarization(self):
        metadata = copy.deepcopy(load_product())
        metadata['upstream']['source_import_status'] = 'approved for distribution'
        failed = {
            'content_errors': ['DMG 签名无效'],
            'publication_pending': [],
            'assets': [],
        }
        with mock.patch.object(assemble_release, 'audit', return_value=failed) as audit:
            with self.assertRaisesRegex(ValueError, 'DMG 签名无效'):
                assemble_release.verify_formal_release(Path('/tmp/release'), metadata)
        audit.assert_called_once()
        self.assertTrue(audit.call_args.kwargs['formal'])

    def test_manual_workflow_only_uploads_internal_artifacts(self):
        manual = (ROOT / '.github/workflows/build-artifacts.yml').read_text()
        shared = (ROOT / '.github/workflows/package-arch.yml').read_text()
        self.assertIn('workflow_dispatch:', manual)
        self.assertNotIn('push:', manual)
        self.assertNotIn('pull_request:', manual)
        self.assertNotIn('gh release create', manual)
        self.assertNotIn('gh release upload', manual)
        self.assertIn('architecture: arm64', manual)
        self.assertIn('architecture: x86_64', manual)
        self.assertIn('signing_mode: adhoc', manual)
        self.assertIn('workflow_call:', shared)
        self.assertIn('actions/upload-artifact@v7', shared)
        self.assertIn('*.dmg', shared)
        self.assertNotIn('*.pkg', shared)
        self.assertIn('if-no-files-found: error', shared)
        self.assertIn('retention-days: 14', shared)
        self.assertIn('overwrite: true', shared)

    def test_tag_release_workflow_requires_developer_id(self):
        release = (ROOT / '.github/workflows/release.yml').read_text()
        shared = (ROOT / '.github/workflows/package-arch.yml').read_text()
        publisher = (ROOT / 'scripts/publish-github-release.py').read_text()
        self.assertIn('tags:', release)
        self.assertIn('v*', release)
        self.assertNotIn('workflow_dispatch:', release)
        self.assertNotIn('pull_request:', release)
        self.assertEqual(release.count('signing_mode: ${{ needs.prepare.outputs.signing_mode }}'), 2)
        self.assertIn('--formal', release)
        self.assertIn('publish-github-release.py', release)
        self.assertNotIn('gh release create', release)
        self.assertEqual(release.count('actions/download-artifact@v8'), 2)
        self.assertIn('--draft', publisher)
        self.assertIn('--prerelease', publisher)
        self.assertIn('--verify-tag', publisher)
        self.assertIn('signing_mode', shared)
        self.assertNotIn('BUILD-RESULT.json', release)
        self.assertNotIn('*.pkg', release)
        for secret in (
            'DEVELOPER_ID_APPLICATION_P12_BASE64',
            'DEVELOPER_ID_APPLICATION_P12_PASSWORD',
            'DEVELOPER_ID_INSTALLER_P12_BASE64',
            'DEVELOPER_ID_INSTALLER_P12_PASSWORD',
            'APPLE_TEAM_ID',
            'APP_STORE_CONNECT_ISSUER_ID',
            'APP_STORE_CONNECT_KEY_ID',
            'APP_STORE_CONNECT_PRIVATE_KEY_P8_BASE64',
        ):
            self.assertIn(secret, shared)

    def test_developer_id_build_rejects_missing_credentials(self):
        with tempfile.TemporaryDirectory() as t:
            with mock.patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(ValueError):
                    build_packages.build(
                        'arm64', Path(t) / 'output', 'developer-id')

    def test_developer_id_identity_lookup_uses_full_name_and_team(self):
        environment = {
            'APPLE_TEAM_ID': 'ABCDE12345',
            'DEVELOPER_ID_APPLICATION_IDENTITY':
                'Developer ID Application: Example Corp (ABCDE12345)',
            'DEVELOPER_ID_INSTALLER_IDENTITY':
                'Developer ID Installer: Example Corp (ABCDE12345)',
        }
        output = (
            '  1) ABCDEF "Developer ID Application: Example Corp (ABCDE12345)"\n'
            '  1) 123456 "Developer ID Installer: Example Corp (ABCDE12345)"\n'
        )
        result = subprocess.CompletedProcess([], 0, output, '')
        with mock.patch.object(build_packages.subprocess, 'run', return_value=result):
            build_packages.verify_developer_identities(environment)

        environment['APPLE_TEAM_ID'] = 'ZZZZZ99999'
        with self.assertRaisesRegex(ValueError, 'APPLE_TEAM_ID'):
            build_packages.verify_developer_identities(environment)

    def test_notarization_requires_accepted_status(self):
        environment = {
            'APP_STORE_CONNECT_PRIVATE_KEY_PATH': '/tmp/AuthKey.p8',
            'APP_STORE_CONNECT_KEY_ID': 'ABCDE12345',
            'APP_STORE_CONNECT_ISSUER_ID': '00000000-0000-0000-0000-000000000000',
        }
        accepted = subprocess.CompletedProcess(
            [], 0, json.dumps({'id': 'submission-id', 'status': 'Accepted'}), '')
        with mock.patch.object(build_packages.subprocess, 'run', return_value=accepted):
            self.assertEqual(
                build_packages.notarize(Path('/tmp/image.dmg'), environment),
                'submission-id',
            )

        invalid = subprocess.CompletedProcess(
            [], 0, json.dumps({'id': 'submission-id', 'status': 'Invalid'}), '')
        log = subprocess.CompletedProcess([], 0, '{"issues": []}', '')
        with mock.patch.object(
                build_packages.subprocess, 'run', side_effect=[invalid, log]):
            with self.assertRaisesRegex(ValueError, 'Apple 公证未通过：Invalid'):
                build_packages.notarize(Path('/tmp/image.dmg'), environment)

    def test_github_release_uses_draft_and_verifies_assets(self):
        with tempfile.TemporaryDirectory() as t:
            directory = Path(t)
            version = '9.9.9'
            names = [
                f'TapSayAudio-2ch-{version}-arm64.dmg',
                f'TapSayAudio-2ch-{version}-x86_64.dmg',
                f'TapSayAudio-2ch-{version}-source.tar.gz',
                'SHA256SUMS.txt',
            ]
            for index, name in enumerate(names):
                (directory / name).write_bytes(str(index).encode())

            class FakeGh:
                def __init__(self):
                    self.calls = []
                    self.created = False
                    self.published = False

                def state(self):
                    return json.dumps({
                        'isDraft': self.created and not self.published,
                        'isPrerelease': self.published,
                        'name': 'TapSay Audio ' + version,
                        'assets': [
                            {'name': name, 'size': (directory / name).stat().st_size}
                            for name in names
                        ],
                    })

                def __call__(self, args, **kwargs):
                    self.calls.append(args)
                    command = args[1:3]
                    if command == ['release', 'view']:
                        if not self.created:
                            return subprocess.CompletedProcess(
                                args, 1, '', 'release not found')
                        return subprocess.CompletedProcess(args, 0, self.state(), '')
                    if command == ['release', 'create']:
                        self.created = True
                        return subprocess.CompletedProcess(args, 0, '', '')
                    if command == ['release', 'upload']:
                        return subprocess.CompletedProcess(args, 0, '', '')
                    if command == ['release', 'edit']:
                        self.published = True
                        return subprocess.CompletedProcess(args, 0, '', '')
                    raise AssertionError('unexpected command: ' + ' '.join(args))

            runner = FakeGh()
            publish_github_release.publish_release(
                'v' + version, version, directory, runner)
            self.assertEqual(runner.calls[0][1:3], ['release', 'view'])
            create_call = next(call for call in runner.calls if call[1:3] == ['release', 'create'])
            self.assertIn('--draft', create_call)
            edit_call = next(call for call in runner.calls if call[1:3] == ['release', 'edit'])
            self.assertIn('--draft=false', edit_call)
            self.assertIn('--prerelease', edit_call)

    def test_github_release_upload_failure_removes_only_draft(self):
        with tempfile.TemporaryDirectory() as t:
            directory = Path(t)
            version = '9.9.9'
            for name in (
                f'TapSayAudio-2ch-{version}-arm64.dmg',
                f'TapSayAudio-2ch-{version}-x86_64.dmg',
                f'TapSayAudio-2ch-{version}-source.tar.gz',
                'SHA256SUMS.txt',
            ):
                (directory / name).write_bytes(name.encode())

            class FailingGh:
                def __init__(self):
                    self.calls = []
                    self.created = False

                def __call__(self, args, **kwargs):
                    self.calls.append(args)
                    command = args[1:3]
                    if command == ['release', 'view']:
                        if not self.created:
                            return subprocess.CompletedProcess(
                                args, 1, '', 'release not found')
                        raise AssertionError('draft state is not expected after upload failure')
                    if command == ['release', 'create']:
                        self.created = True
                        return subprocess.CompletedProcess(args, 0, '', '')
                    if command == ['release', 'upload']:
                        return subprocess.CompletedProcess(args, 1, '', 'upload failed')
                    if command == ['release', 'delete']:
                        return subprocess.CompletedProcess(args, 0, '', '')
                    raise AssertionError('unexpected command: ' + ' '.join(args))

            runner = FailingGh()
            with self.assertRaisesRegex(
                    publish_github_release.ReleaseError, 'upload failed'):
                publish_github_release.publish_release(
                    'v' + version, version, directory, runner)
            delete_call = next(call for call in runner.calls if call[1:3] == ['release', 'delete'])
            self.assertIn('--yes', delete_call)
            self.assertNotIn('--cleanup-tag', delete_call)

    def test_release_failures_have_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            metadata = load_product(); prefix = 'TapSayAudio-2ch-' + metadata['product']['version']
            source_sha = subprocess.check_output(
                ['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
            build_metadata = base / 'build-metadata.json'
            build_metadata.write_text(json.dumps({
                'version': metadata['product']['version'],
                'build_number': metadata['product']['build_number'],
                'tag': 'v' + metadata['product']['version'],
                'source_sha': source_sha,
            }))
            subprocess.run(['bash', str(ROOT/'scripts/build-source-archive.sh')], check=True,
                           env=dict(
                               os.environ,
                               OUT=t,
                               TAPSAY_BUILD_METADATA=str(build_metadata),
                           ), stdout=subprocess.DEVNULL)
            for suffix in ['-arm64.dmg', '-x86_64.dmg']:
                (base / (prefix + suffix)).write_bytes(b'fixture')
            names = [
                prefix + '-arm64.dmg',
                prefix + '-x86_64.dmg',
                prefix + '-source.tar.gz',
            ]
            sums = ''.join(hashlib.sha256((base/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in names)
            (base / 'SHA256SUMS.txt').write_text(sums)
            ok = lambda args: types.SimpleNamespace(returncode=0, stdout='', stderr='')
            self.assertEqual(exit_code(audit(base, metadata, ok)), 0)
            self.assertEqual(exit_code(audit(base, metadata, ok, formal=True), True), 0)
            (base/names[0]).write_bytes(b'corrupted')
            self.assertEqual(exit_code(audit(base, metadata, ok)), 1)
            (base/names[0]).write_bytes(b'fixture')
            bad_image = lambda args: types.SimpleNamespace(
                returncode=1 if 'check-dmg.py' in ' '.join(args) else 0,
                stdout='', stderr='')
            self.assertEqual(exit_code(audit(base, metadata, bad_image)), 1)
            bad_signature = lambda args: types.SimpleNamespace(
                returncode=1 if 'stapler' in args else 0, stdout='', stderr='')
            self.assertEqual(
                exit_code(audit(base, metadata, bad_signature, formal=True), True), 1)
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
            (output/'old.dmg').write_bytes(b'previous image')
            (output/'SHA256SUMS.txt').write_bytes(b'previous checksums')
            with mock.patch.object(builder.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'injected')):
                with self.assertRaises(subprocess.CalledProcessError):
                    builder.build('arm64', output)
            self.assertEqual((output/'old.dmg').read_bytes(), b'previous image')
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
