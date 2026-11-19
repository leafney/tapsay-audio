"""Create release notes from complete, locally available Git history."""
from collections import deque
import re
import subprocess

TAG = re.compile(r'v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z')


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True,
                          text=True, capture_output=True).stdout.strip()


def commit_subjects(repo, tag):
    if not TAG.fullmatch(tag):
        raise ValueError('发布标签格式无效')
    if git(repo, 'rev-parse', '--is-shallow-repository') != 'false':
        raise ValueError('发布需要完整的 Git 历史')
    current = git(repo, 'rev-parse', '--verify', f'refs/tags/{tag}^{{commit}}')
    if current != git(repo, 'rev-parse', 'HEAD^{commit}'):
        raise ValueError('发布标签与当前提交不一致')
    tags = {}
    for name in git(repo, 'tag', '--list', 'v*').splitlines():
        if name != tag and TAG.fullmatch(name):
            commit = git(repo, 'rev-parse', '--verify', f'refs/tags/{name}^{{commit}}')
            tags.setdefault(commit, []).append(name)
    graph = {}
    for line in git(repo, 'rev-list', '--parents', current).splitlines():
        commit, *parents = line.split()
        graph[commit] = parents
    queue = deque((parent, 1) for parent in graph[current])
    seen = {current}
    candidates = []
    distance = None
    while queue:
        commit, depth = queue.popleft()
        if distance is not None and depth > distance:
            break
        if commit in seen:
            continue
        seen.add(commit)
        if commit in tags:
            distance = depth
            candidates.extend(tags[commit])
        queue.extend((parent, depth + 1) for parent in graph[commit])
    previous = max(candidates, key=lambda name: tuple(map(int, TAG.fullmatch(name).groups()))) if candidates else None
    revision = f'{previous}..{tag}' if previous else tag
    return git(repo, 'log', '--no-merges', '--format=%s', revision).splitlines()


def release_notes(repo, tag, signing_mode):
    subjects = commit_subjects(repo, tag)
    status = ('未经过苹果开发者签名及公证，macOS 可能阻止打开。'
              if signing_mode == 'adhoc' else '已通过开发者签名及苹果公证验证。')
    return status + '\n\n## 更新内容\n\n' + ('\n'.join('- ' + s for s in subjects) if subjects else '无普通提交。') + '\n'
