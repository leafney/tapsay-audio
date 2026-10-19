#!/usr/bin/env python3
"""Remove only an identity-verified TapSay Audio bundle."""
import argparse, json, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
META=json.loads((ROOT/'config/product.json').read_text())
def main():
 p=argparse.ArgumentParser(); p.add_argument('--target',type=Path,required=True); p.add_argument('--state',type=Path,required=True); p.add_argument('--yes',action='store_true'); a=p.parse_args()
 if not a.state.exists(): print('未安装'); return 0
 state=json.loads(a.state.read_text())
 if Path(state.get('target','')).resolve()!=a.target.resolve(): print('状态目标不匹配，拒绝清理'); return 1
 if not a.yes: print(f'将清理：{a.target}\n请使用 --yes 确认'); return 2
 if a.target.exists(): shutil.rmtree(a.target)
 a.state.unlink()
 print('TapSay Audio 已卸载；系统默认路由未被修改')
 return 0
if __name__=='__main__': raise SystemExit(main())
