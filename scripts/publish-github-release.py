#!/usr/bin/env python3
"""Publish verified assets through a draft GitHub release."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

VERSION_PATTERN = r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'


class ReleaseError(RuntimeError):
    pass


def run_gh(arguments, runner=None):
    execute = runner or subprocess.run
    return execute(
        ['gh', *arguments],
        text=True,
        capture_output=True,
    )


def require_success(result, action):
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        raise ReleaseError(action + '失败：' + message)


def release_state(tag, runner=None):
    result = run_gh([
        'release', 'view', tag,
        '--json', 'isDraft,isPrerelease,name,assets',
    ], runner)
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        lowered = message.lower()
        if 'release not found' in lowered or '(http 404)' in lowered:
            return None
        raise ReleaseError('读取 Release 失败：' + message)
    try:
        state = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ReleaseError('Release 状态不是有效 JSON') from error
    if not isinstance(state, dict) or not isinstance(state.get('assets'), list):
        raise ReleaseError('Release 状态结构无效')
    return state


def expected_assets(version, directory):
    directory = Path(directory)
    names = [
        f'TapSayAudio-2ch-{version}-arm64.dmg',
        f'TapSayAudio-2ch-{version}-x86_64.dmg',
        f'TapSayAudio-2ch-{version}-source.tar.gz',
        'SHA256SUMS.txt',
    ]
    actual = {
        path.name for path in directory.iterdir()
        if path.is_file()
    }
    if actual != set(names):
        raise ReleaseError('公开资产集合不匹配')
    return [
        directory / name
        for name in names
    ], {
        name: (directory / name).stat().st_size
        for name in names
    }


def validate_remote_assets(state, expected_sizes, draft):
    if state.get('isDraft') is not draft:
        raise ReleaseError('Release Draft 状态不符合预期')
    actual = {
        asset.get('name'): asset.get('size')
        for asset in state['assets']
        if isinstance(asset, dict)
    }
    if set(actual) != set(expected_sizes):
        raise ReleaseError('Release 远端资产集合不匹配')
    for name, expected_size in expected_sizes.items():
        if actual[name] != expected_size:
            raise ReleaseError('Release 远端资产大小不匹配：' + name)


def cleanup_draft(tag, runner=None):
    result = run_gh(['release', 'delete', tag, '--yes'], runner)
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        print('清理 Draft Release 失败：' + message, file=sys.stderr)


def publish_release(tag, version, directory, runner=None):
    if re.fullmatch(r'v' + VERSION_PATTERN, tag) is None:
        raise ReleaseError('发布标签格式无效')
    if tag[1:] != version or re.fullmatch(VERSION_PATTERN, version) is None:
        raise ReleaseError('发布标签与版本不一致')

    paths, expected_sizes = expected_assets(version, directory)
    if release_state(tag, runner) is not None:
        raise ReleaseError('同名 Release 已存在')

    created_draft = False
    try:
        created = run_gh([
            'release', 'create', tag,
            '--verify-tag',
            '--draft',
            '--title', 'TapSay Audio ' + version,
            '--generate-notes',
        ], runner)
        require_success(created, '创建 Draft Release')
        created_draft = True

        uploaded = run_gh([
            'release', 'upload', tag,
            *map(str, paths),
        ], runner)
        require_success(uploaded, '上传 Release 资产')

        draft_state = release_state(tag, runner)
        if draft_state is None:
            raise ReleaseError('Draft Release 在上传后消失')
        validate_remote_assets(draft_state, expected_sizes, draft=True)

        published = run_gh([
            'release', 'edit', tag,
            '--draft=false',
            '--prerelease',
        ], runner)
        require_success(published, '发布 Pre-release')

        final_state = release_state(tag, runner)
        if final_state is None:
            raise ReleaseError('发布后的 Pre-release 不存在')
        validate_remote_assets(final_state, expected_sizes, draft=False)
        if final_state.get('isPrerelease') is not True:
            raise ReleaseError('Release 未标记为 Pre-release')
    except BaseException:
        if created_draft:
            cleanup_draft(tag, runner)
        raise
    print('GitHub Pre-release 已发布：' + tag)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--directory', required=True, type=Path)
    args = parser.parse_args()
    publish_release(args.tag, args.version, args.directory)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ReleaseError, ValueError) as error:
        print('GitHub Release 发布失败：' + str(error), file=sys.stderr)
        raise SystemExit(1)
