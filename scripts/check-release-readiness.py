#!/usr/bin/env python3
"""Check content independently of formal publication prerequisites."""
import argparse
import json
from pathlib import Path
from product import ROOT, load_product
from release_checks import audit, exit_code

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dist', type=Path, default=ROOT / 'dist')
    parser.add_argument('--formal', action='store_true')
    args = parser.parse_args()
    result = audit(args.dist, load_product(), formal=args.formal)
    code = exit_code(result, args.formal)
    state = '内容检查失败' if result['content_errors'] else '本地内容检查通过，正式发布条件待完成'
    lines = ['# 本地发行检查', '', state, '', '## 内容错误', '']
    lines += ['- '+e for e in result['content_errors']] or ['无']
    lines += ['', '## 正式发布条件', ''] + ['- '+e for e in result['publication_pending']]
    lines += ['', '支持范围：Apple Silicon arm64 为 macOS 14 及以上；Intel x86_64 为 macOS 13 及以上（macOS 13 真机待验证）。', '']
    (args.dist / 'RELEASE-READINESS.md').write_text('\n'.join(lines))
    (args.dist / 'RELEASE-STATUS.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print('\n'.join(lines))
    return code

if __name__ == '__main__':
    raise SystemExit(main())
