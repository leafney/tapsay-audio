#!/usr/bin/env python3
"""Assemble the public two-architecture release from verified inputs."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from product import DISTRIBUTION_APPROVED_STATUS, ROOT, load_product, package_architecture
from release_checks import audit, exit_code

VERSION_PATTERN = r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_single_architecture(directory, architecture, version, signing_mode='developer-id'):
    directory = Path(directory)
    prefix = f'TapSayAudio-2ch-{version}-{package_architecture(architecture)}'
    names = [prefix + '.dmg']
    for name in names:
        path = directory / name
        require(path.is_file() and path.stat().st_size > 0, '缺少非空资产：' + name)
    checksum_path = directory / 'SHA256SUMS.txt'
    require(checksum_path.is_file(), architecture + ' 缺少 SHA256SUMS.txt')
    checksums = {}
    for line in checksum_path.read_text().splitlines():
        fields = line.split()
        require(len(fields) == 2, architecture + ' 校验文件格式错误')
        checksum, name = fields
        name = name.lstrip('*')
        require(name not in checksums, architecture + ' 校验文件包含重复项')
        checksums[name] = checksum
    require(set(checksums) == set(names), architecture + ' 校验文件资产集合错误')
    for name in names:
        require(checksums[name] == digest(directory / name), name + ' 散列不一致')
    subprocess.run([
        'python3', str(ROOT / 'scripts/check-dmg.py'),
        str(directory / names[0]), architecture,
        '--signing-mode', signing_mode,
    ], check=True, cwd=ROOT)


def write_checksums(directory, names):
    rows = []
    for name in names:
        path = directory / name
        require(path.is_file() and path.stat().st_size > 0, '缺少非空公开资产：' + name)
        rows.append(digest(path) + '  ' + name + '\n')
    (directory / 'SHA256SUMS.txt').write_text(''.join(rows))


def verify_formal_release(directory, metadata):
    require(
        metadata['upstream']['source_import_status'] == DISTRIBUTION_APPROVED_STATUS,
        '第三方分发审查尚未完成',
    )
    result = audit(directory, metadata, formal=True)
    code = exit_code(result, formal=True)
    if code != 0:
        errors = result['content_errors'] or result['publication_pending']
        raise ValueError('正式发布验证失败：' + '；'.join(errors))


def assemble(arm64_dir, x86_64_dir, output, version, minimum_macos,
             build_metadata=None, formal=False, signing_mode='developer-id'):
    require(signing_mode in ('adhoc', 'developer-id'), '签名模式无效')
    require(re.fullmatch(VERSION_PATTERN, version) is not None, '版本格式无效')
    metadata = load_product()
    require(metadata['product']['version'] == version, '产品配置版本与发布版本不一致')
    arm64_dir = Path(arm64_dir).absolute()
    x86_64_dir = Path(x86_64_dir).absolute()
    verify_single_architecture(arm64_dir, 'arm64', version, signing_mode)
    verify_single_architecture(x86_64_dir, 'x86_64', version, signing_mode)

    output = Path(output).absolute()
    require(output != ROOT and output not in ROOT.parents and not output.is_symlink(),
            '公开产物目录不能覆盖源码或使用符号链接')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
            prefix='.tapsay-release-', dir=output.parent) as temporary:
        staged = Path(temporary) / 'release'
        staged.mkdir()
        public_names = []
        for directory, architecture in ((arm64_dir, 'arm64'), (x86_64_dir, 'x86_64')):
            prefix = f'TapSayAudio-2ch-{version}-{package_architecture(architecture)}'
            name = prefix + ('-Unverified' if signing_mode == 'adhoc' else '') + '.dmg'
            shutil.copy2(directory / (prefix + '.dmg'), staged / name)
            public_names.append(name)
        write_checksums(staged, public_names)
        require({path.name for path in staged.iterdir()} == {
            *public_names, 'SHA256SUMS.txt',
        }, '公开目录包含未声明资产')
        if formal and signing_mode == 'developer-id':
            verify_formal_release(staged, metadata)
        elif formal:
            require(metadata['upstream']['source_import_status'] == DISTRIBUTION_APPROVED_STATUS,
                    '第三方分发审查尚未完成')
            result = audit(staged, metadata, unverified=True)
            if exit_code(result):
                raise ValueError('公开发布验证失败：' + '；'.join(result['content_errors']))

        spec = importlib.util.spec_from_file_location(
            'publish_artifacts', ROOT / 'scripts/publish-artifacts.py')
        publisher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(publisher)
        publisher.publish(staged, output)
    print('双架构公开发布目录已生成：' + str(output))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--arm64-dir', required=True, type=Path)
    parser.add_argument('--x86_64-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--version', required=True)
    parser.add_argument('--minimum-macos', help='已弃用，版本按架构从配置读取')
    parser.add_argument('--build-metadata', type=Path)
    parser.add_argument('--formal', action='store_true')
    parser.add_argument('--signing-mode', choices=('adhoc', 'developer-id'), default='developer-id')
    args = parser.parse_args()
    assemble(
        args.arm64_dir,
        args.x86_64_dir,
        args.output,
        args.version,
        args.minimum_macos,
        args.build_metadata,
        args.formal,
        args.signing_mode,
    )
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.CalledProcessError) as error:
        print('公开发布汇总失败：' + str(error))
        raise SystemExit(1)
