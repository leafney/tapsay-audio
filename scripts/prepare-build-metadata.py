#!/usr/bin/env python3
"""Prepare the effective product configuration for one build."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from product import DISTRIBUTION_APPROVED_STATUS, load_product

ROOT = Path(__file__).resolve().parents[1]
TAG_PATTERN = r'v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'
BUILD_NUMBER_PATTERN = r'[1-9][0-9]*'


def current_source_sha():
    result = subprocess.run(
        ['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],
        capture_output=True,
        text=True,
    )
    source_sha = result.stdout.strip()
    if result.returncode != 0 or re.fullmatch(r'[0-9a-f]{40}', source_sha) is None:
        raise ValueError('无法获取源码提交')
    return source_sha


def write_temporary(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix='.' + path.name + '.',
        suffix='.tmp',
    )
    try:
        with os.fdopen(descriptor, 'w') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return Path(temporary_name)


def prepare(mode, tag, build_number, config_path, output_path):
    if re.fullmatch(BUILD_NUMBER_PATTERN, build_number) is None:
        raise ValueError('构建号必须是正整数')

    config_path = Path(config_path)
    output_path = Path(output_path)
    metadata = load_product(config_path)
    product = metadata['product']

    if mode == 'manual':
        effective_tag = ''
        version = product['version']
    else:
        if tag is None or re.fullmatch(TAG_PATTERN, tag) is None:
            raise ValueError('发布标签必须严格匹配 vX.Y.Z')
        if metadata['upstream']['source_import_status'] != DISTRIBUTION_APPROVED_STATUS:
            raise ValueError('第三方分发审查尚未完成')
        effective_tag = tag
        version = tag.removeprefix('v')

    product['version'] = version
    product['build_number'] = build_number
    build_metadata = {
        'version': version,
        'build_number': build_number,
        'tag': effective_tag,
        'source_sha': current_source_sha(),
    }

    config_content = json.dumps(metadata, ensure_ascii=False, indent=2) + '\n'
    metadata_content = json.dumps(build_metadata, ensure_ascii=False, indent=2) + '\n'

    config_tmp = None
    output_tmp = None
    original_output = output_path.read_bytes() if output_path.exists() else None
    try:
        config_tmp = write_temporary(config_path, config_content)
        output_tmp = write_temporary(output_path, metadata_content)

        load_product(config_tmp)
        output_tmp.replace(output_path)
        try:
            config_tmp.replace(config_path)
        except Exception:
            if original_output is None:
                output_path.unlink(missing_ok=True)
            else:
                restored_output = write_temporary(output_path, original_output.decode())
                restored_output.replace(output_path)
            raise
    finally:
        if config_tmp is not None:
            config_tmp.unlink(missing_ok=True)
        if output_tmp is not None:
            output_tmp.unlink(missing_ok=True)

    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with Path(github_output).open('a') as handle:
            handle.write('version=' + version + '\n')
            handle.write('build_number=' + build_number + '\n')
            handle.write('tag=' + effective_tag + '\n')
    return build_metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', required=True, choices=('manual', 'tag'))
    parser.add_argument('--tag')
    parser.add_argument('--build-number', required=True)
    parser.add_argument('--config', required=True)
    parser.add_argument('--output-json', required=True)
    args = parser.parse_args()
    prepare(
        args.mode,
        args.tag,
        args.build_number,
        args.config,
        args.output_json,
    )
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (KeyError, OSError, TypeError, ValueError) as error:
        print('构建元数据准备失败：' + str(error), file=sys.stderr)
        raise SystemExit(1)
