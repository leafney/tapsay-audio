"""Exercise release notes against real temporary Git histories."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from release_notes import commit_subjects, release_notes


class ReleaseNotesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'test')
        self.git('config', 'user.email', 'test@example.invalid')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              text=True, capture_output=True).stdout.strip()

    def commit(self, message):
        self.git('commit', '--allow-empty', '-qm', message)

    def test_first_and_following_tags(self):
        self.commit('初次提交')
        self.git('tag', 'v1.0.0')
        self.assertEqual(commit_subjects(self.repo, 'v1.0.0'), ['初次提交'])
        self.commit('修复 `特殊字符` $(不会执行)')
        self.git('tag', '-a', 'v1.1.0', '-m', '发布')
        self.assertEqual(commit_subjects(self.repo, 'v1.1.0'), ['修复 `特殊字符` $(不会执行)'])
        self.assertIn('未经过', release_notes(self.repo, 'v1.1.0', 'adhoc'))

    def test_unmerged_tag_merge_commit_and_ties(self):
        self.commit('初始')
        self.git('tag', 'v1.0.0')
        self.git('tag', 'v1.0.1')
        self.git('checkout', '-qb', 'other')
        self.commit('其他分支')
        self.git('tag', 'v9.0.0')
        self.git('checkout', '-q', '-')
        self.commit('主线')
        self.git('merge', '--no-ff', '-qm', '合并提交', 'other')
        self.git('tag', 'v1.1.0')
        self.assertEqual(commit_subjects(self.repo, 'v1.1.0'), ['主线'])

    def test_missing_and_mismatched_tag_fail(self):
        self.commit('初始')
        self.git('tag', 'v1.0.0')
        self.commit('后续')
        with self.assertRaises(ValueError):
            commit_subjects(self.repo, 'v1.0.0')
        with self.assertRaises(subprocess.CalledProcessError):
            commit_subjects(self.repo, 'v2.0.0')


if __name__ == '__main__':
    unittest.main()
