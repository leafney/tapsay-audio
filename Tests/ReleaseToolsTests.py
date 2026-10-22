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
            render_uninstaller(app, metadata, native)
            info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
            self.assertEqual((info['CFBundleShortVersionString'], info['CFBundleVersion']), ('0.1.1', '2'))
            self.assertEqual(json.loads((app / 'Contents/Resources/product.json').read_text()), metadata)
            for bad in ['../release', '0.1.1\n', '01.1.0', '0.1', '']:
                metadata['product']['version'] = bad
                config.write_text(json.dumps(metadata))
                with self.assertRaises(ValueError): load_product(config)

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
                with self.assertRaises(subprocess.CalledProcessError): builder.build(output)
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
