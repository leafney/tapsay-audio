import plistlib, subprocess, sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]; app=root/'Uninstaller.app'; info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
assert info['CFBundleIdentifier']=='com.leafney.tapsay.audio.uninstaller'
assert info['CFBundleExecutable']=='TapSayAudioUninstaller'
assert (app/'Contents/MacOS/TapSayAudioUninstaller').stat().st_mode & 0o111
assert 'osascript' in (app/'Contents/MacOS/TapSayAudioUninstaller').read_text()
print('卸载 APP 结构检查通过')
