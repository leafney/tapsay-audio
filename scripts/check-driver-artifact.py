#!/usr/bin/env python3
"""Inspect the actual driver bundle selected by the build result."""
import plistlib
import subprocess
import sys
from pathlib import Path
from product import load_product

def main():
    if len(sys.argv)!=3 or sys.argv[2]!='arm64':
        raise ValueError('用法：check-driver-artifact.py BUNDLE arm64')
    bundle=Path(sys.argv[1]); m=load_product(); d=m['driver']; p=m['product']
    info=plistlib.loads((bundle/'Contents/Info.plist').read_bytes())
    for key,value in {'CFBundleIdentifier':d['bundle_identifier'],
        'CFBundleExecutable':d['executable_name'], 'CFBundleShortVersionString':p['version'],
        'CFBundleVersion':p['build_number']}.items():
        if info[key]!=value: raise ValueError('产物元数据不一致：'+key)
    if info['CFPlugInFactories']!={d['plugin_factory_uuid']:'TapSayAudio_Create'}:
        raise ValueError('工厂入口不一致')
    binary=bundle/'Contents/MacOS'/d['executable_name']
    if subprocess.check_output(['lipo','-archs',str(binary)],text=True).strip()!='arm64':
        raise ValueError('产物不是 arm64')
    settings=subprocess.check_output(['xcrun','vtool','-show-build',str(binary)],text=True)
    if 'minos '+p['minimum_macos'] not in settings: raise ValueError('最低系统不一致')
    strings=subprocess.check_output(['strings',str(binary)],text=True)
    for value in [d['device_uid'],d['device_name'],d['box_uid'],d['model_uid'],*d['hidden_device_uids']]:
        if value not in strings: raise ValueError('产物身份缺失：'+value)
    subprocess.run(['codesign','--verify','--deep','--strict',str(bundle)],check=True)
    print('驱动实际产物检查通过')
if __name__=='__main__': main()
