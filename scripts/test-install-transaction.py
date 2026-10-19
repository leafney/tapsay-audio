#!/usr/bin/env python3
import json, os, shutil, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run(*args, ok=True):
 r=subprocess.run(args,text=True,capture_output=True)
 assert (r.returncode==0)==ok, (args,r.stdout,r.stderr)
 return r

def main():
 with tempfile.TemporaryDirectory() as d:
  d=Path(d); payload=d/'payload.driver'; (payload/'Contents/MacOS').mkdir(parents=True); (payload/'Contents/Info.plist').write_text('')
  # Use a real built bundle so lipo and identity checks are meaningful.
  built=ROOT/'.build/driver/arm64/Build/Products/Release/TapSayAudio.driver'; assert built.exists(), '先运行构建'
  shutil.copytree(built,payload,dirs_exist_ok=True)
  target=d/'HAL/TapSayAudio.driver'; state=d/'state.json'
  run('python3',str(ROOT/'scripts/install.py'),str(payload),'--target',str(target),'--state',str(state),'--arch','arm64')
  first=target/'Contents/MacOS/TapSayAudio'; before=first.read_bytes()
  run('python3',str(ROOT/'scripts/install.py'),str(payload),'--target',str(target),'--state',str(state),'--arch','x86_64',ok=False)
  assert first.read_bytes()==before
  run('python3',str(ROOT/'scripts/install.py'),str(payload),'--target',str(target),'--state',str(state),'--arch','arm64','--inject-failure-after-copy',ok=False)
  assert first.read_bytes()==before
  run('python3',str(ROOT/'scripts/uninstall.py'),'--target',str(target),'--state',str(state),ok=False)
  run('python3',str(ROOT/'scripts/uninstall.py'),'--target',str(target),'--state',str(state),'--yes')
  assert not target.exists()
 print('安装事务测试通过')
if __name__=='__main__': main()
