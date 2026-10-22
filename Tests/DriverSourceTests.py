"""Reject unreviewed source changes without loading a system audio driver."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import driver_sources

spec = importlib.util.spec_from_file_location('prepare', ROOT / 'scripts/prepare-driver-source.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class DriverSourceTests(unittest.TestCase):
    def audit(self, source):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/check-reference-source.py'), str(source)],
                              capture_output=True, text=True)

    def test_reviewed_source_and_unapproved_audio_change(self):
        with tempfile.TemporaryDirectory() as t:
            source = Path(t) / 'source'
            prepare.prepare(source)
            self.assertEqual(self.audit(source).returncode, 0)
            c = source / 'BlackHole/BlackHole.c'
            original = c.read_text()
            self.assertIn('gDevice_SampleRate                  = 48000.0', original)
            c.write_text(original.replace('gDevice_SampleRate                  = 48000.0',
                                          'gDevice_SampleRate                  = 16000.0'))
            self.assertNotEqual(self.audit(source).returncode, 0)

    def test_missing_fix_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            source = Path(t) / 'source'
            prepare.prepare(source)
            subprocess.run(['/usr/bin/patch', '--batch', '-R', '-F', '0', '-p1', '-i',
                            str(driver_sources.BASE / driver_sources.PROPERTY_PATCHES[-1]),
                            '-d', str(source)], check=True, stdout=subprocess.DEVNULL)
            self.assertNotEqual(self.audit(source).returncode, 0)

    def test_changed_or_unpinned_patch_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t) / 'inputs'
            shutil.copytree(driver_sources.BASE, base)
            name = driver_sources.PROPERTY_PATCHES[0]
            with mock.patch.object(driver_sources, 'BASE', base):
                patch = base / name
                patch.write_bytes(patch.read_bytes() + b'\n')
                with self.assertRaises(ValueError): driver_sources.verify_inputs()
                manifest = base / 'SOURCE-SHA256.json'
                hashes = json.loads(manifest.read_text())
                del hashes[name]
                manifest.write_text(json.dumps(hashes))
                with self.assertRaises(ValueError): driver_sources.verify_inputs()


if __name__ == '__main__':
    unittest.main()
