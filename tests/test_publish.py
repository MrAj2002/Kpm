"""Exercise publication against an isolated, local bare Git remote."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import publish


class PublishingTests(unittest.TestCase):
    def test_initial_publish_update_and_key_rotation_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            remote, checkout = base/'remote.git', base/'source'
            def git(*arguments, cwd=checkout):
                return subprocess.check_output(['git', *arguments], cwd=cwd, stderr=subprocess.PIPE, text=True).strip()
            git('init', '--bare', str(remote), cwd=base)
            git('init', '-b', 'main', str(checkout), cwd=base)
            git('config', 'user.name', 'Test'); git('config', 'user.email', 'test@example.invalid')
            git('remote', 'add', 'origin', str(remote))
            (checkout/'sources').mkdir()
            (checkout/'sources/sample.json').write_text('{}')
            (checkout/'README.md').write_text('Source project')
            (checkout/'.gitignore').write_text('repo-output/\nsigning/\n')
            git('add', '.'); git('commit', '-m', 'Initial source'); git('push', 'origin', 'main')
            output = checkout/'repo-output'; (output/'apk').mkdir(parents=True)
            metadata = {'meta': {'signingKeyFingerprint': 'a'*64}}
            (output/'repo.json').write_text(json.dumps(metadata))
            (output/'store.json').write_text('{}')
            (output/'apk/test.apk').write_bytes(b'test fixture, not an Android package')
            (checkout/'signing').mkdir(); (checkout/'signing/repo.p12').write_text('PRIVATE TEST KEY')
            # Bootstrap-created code is committed only to main, never the publication branch.
            (checkout/'engine').mkdir(); (checkout/'engine/Parser.kt').write_text('// test engine')
            actual_git = publish.git
            def local_git(*args, **kwargs):
                kwargs.setdefault('cwd', checkout)
                return actual_git(*args, **kwargs)
            with patch.object(publish, 'ROOT', checkout), patch.object(publish, 'git', local_git), patch.dict(os.environ, {'RUNNER_TEMP': str(base)}):
                publish.main()
                files = git('--git-dir='+str(remote), 'ls-tree', '-r', '--name-only', 'repo').splitlines()
                self.assertEqual(files, ['apk/test.apk', 'repo.json', 'store.json'])
                self.assertEqual(git('--git-dir='+str(remote), 'show', 'main:engine/Parser.kt'), '// test engine')
                before = git('--git-dir='+str(remote), 'rev-parse', 'repo')
                (output/'store.json').write_text('{"updated":true}')
                publish.main()
                self.assertNotEqual(before, git('--git-dir='+str(remote), 'rev-parse', 'repo'))
                self.assertEqual(before, git('--git-dir='+str(remote), 'rev-parse', 'repo^'))
                last_good = git('--git-dir='+str(remote), 'rev-parse', 'repo')
                metadata['meta']['signingKeyFingerprint'] = 'b'*64
                (output/'repo.json').write_text(json.dumps(metadata))
                with self.assertRaisesRegex(RuntimeError, 'Signing key changed'):
                    publish.main()
                self.assertEqual(last_good, git('--git-dir='+str(remote), 'rev-parse', 'repo'))


if __name__ == '__main__':
    unittest.main()
