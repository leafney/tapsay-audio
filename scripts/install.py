#!/usr/bin/env python3
"""TapSay Audio installation transaction; safe sandbox root by default."""
import argparse, json, os, shutil, subprocess, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
META = json.loads((ROOT / 'config/product.json').read_text())
DRIVER = META['driver']

class InstallError(Exception): pass

def arch():
    return subprocess.check_output(['/usr/bin/arch'], text=True).strip()

def validate_payload(bundle: Path, expected: str):
    if not bundle.is_dir(): raise InstallError('载荷驱动不存在')
    info = bundle / 'Contents/Info.plist'
    exe = bundle / 'Contents/MacOS' / DRIVER['executable_name']
    if not info.is_file() or not exe.is_file(): raise InstallError('载荷结构不完整')
    import plistlib
    data = plistlib.loads(info.read_bytes())
    if data.get('CFBundleIdentifier') != DRIVER['bundle_identifier']: raise InstallError('驱动身份不匹配')
    if data.get('CFBundleShortVersionString') != META['product']['version']: raise InstallError('驱动版本不匹配')
    actual = subprocess.check_output(['/usr/bin/lipo', '-archs', str(exe)], text=True).split()
    if actual != [expected]: raise InstallError(f'架构不匹配：主机/目标 {expected}，载荷 {actual}')

def install(payload: Path, target: Path, state: Path, expected: str, failure_after_copy=False):
    validate_payload(payload, expected)
    target.parent.mkdir(parents=True, exist_ok=True)
    state.parent.mkdir(parents=True, exist_ok=True)
    lock = state.with_suffix('.lock')
    try:
        lock.mkdir()
    except FileExistsError: raise InstallError('已有安装事务正在运行')
    backup = None
    try:
        if target.exists():
            backup = state.parent / f'backup-{json.loads(state.read_text()) .get("version", "unknown") if state.exists() else "unknown"}'
            if backup.exists(): shutil.rmtree(backup)
            shutil.copytree(target, backup)
        temp = Path(tempfile.mkdtemp(prefix='tapsay-install-', dir=state.parent))
        staged = temp / target.name
        shutil.copytree(payload, staged)
        if failure_after_copy: raise InstallError('注入部署失败')
        if target.exists(): shutil.rmtree(target)
        os.replace(staged, target)
        state.write_text(json.dumps({'version': META['product']['version'], 'arch': expected, 'target': str(target), 'backup': str(backup) if backup else None}, indent=2) + '\n')
        shutil.rmtree(temp, ignore_errors=True)
        print('驱动已部署；真实 CoreAudio 枚举和音频链路仍需独立验证')
    except Exception:
        if target.exists(): shutil.rmtree(target)
        if backup and backup.exists(): shutil.copytree(backup, target)
        raise
    finally:
        if lock.exists(): lock.rmdir()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('payload', type=Path); p.add_argument('--target', type=Path, required=True); p.add_argument('--state', type=Path, required=True)
    p.add_argument('--arch', default=arch()); p.add_argument('--inject-failure-after-copy', action='store_true')
    a=p.parse_args()
    try: install(a.payload, a.target, a.state, a.arch, a.inject_failure_after_copy)
    except InstallError as e: print(f'安装失败：{e}'); return 1
    return 0
if __name__ == '__main__': raise SystemExit(main())
