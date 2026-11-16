#!/usr/bin/env python3
"""Inspect the generated application rather than its unbuilt template."""
import argparse
import json
from pathlib import Path
import plistlib
import subprocess
from product import load_product

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('app', type=Path)
    args=parser.parse_args()
    metadata=load_product()
    app=args.app
    info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
    assert info['CFBundleIdentifier']==metadata['uninstaller']['bundle_identifier'], '卸载标识不一致'
    assert info['CFBundleShortVersionString']==metadata['product']['version'], '卸载版本不一致'
    assert info['CFBundleVersion']==metadata['product']['build_number'], '卸载构建号不一致'
    assert json.loads((app/'Contents/Resources/product.json').read_text())==metadata, '内置配置不一致'
    for name in ['TapSayAudioUninstaller','TapSayAudioTransaction-arm64']:
        binary=app/'Contents/MacOS'/name
        assert subprocess.check_output(['lipo','-archs',str(binary)],text=True).strip()=='arm64'
    subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
    print('卸载 APP 产物检查通过')
if __name__=='__main__':
    main()
