#!/usr/bin/env python3
"""Publish only generated APK/index files; never upload signing material."""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from source import ROOT

def git(*args,cwd=ROOT,check=True):
    result=subprocess.run(['git',*args],cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if check and result.returncode: raise RuntimeError(result.stderr.strip() or 'Git operation failed.')
    return result

def main():
    output=ROOT/'repo-output'
    metadata=json.loads((output/'repo.json').read_text())
    existing=git('ls-remote','--exit-code','--heads','origin','repo',check=False)
    if existing.returncode not in (0,2): raise RuntimeError('Cannot read the remote publishing branch.')
    if existing.returncode==0:
        git('fetch','origin','repo:refs/remotes/origin/repo')
        old=git('show','origin/repo:repo.json',check=False)
        if old.returncode==0 and json.loads(old.stdout)['meta']['signingKeyFingerprint']!=metadata['meta']['signingKeyFingerprint']:
            raise RuntimeError('Signing key changed. Restore the original repository secrets before publishing updates.')
    git('config','user.name','github-actions[bot]')
    git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    public_paths = ['.github', '.gitignore', 'README.md', 'LICENSE', 'NOTICE.md',
                    'dependencies.lock.json', 'sources', 'scripts', 'engine', 'tests', 'docs']
    git('add', '--', *(p for p in public_paths if (ROOT/p).exists()))
    if git('diff','--cached','--quiet',check=False).returncode:
        git('commit','-m','Update configured video sources')
        git('push','origin','HEAD:main')
    work=Path(tempfile.mkdtemp(prefix='aniyomi-publish-',dir=os.getenv('RUNNER_TEMP')))
    work.rmdir()
    try:
        git('worktree','add','--detach',str(work),'origin/repo' if existing.returncode==0 else 'HEAD')
        if existing.returncode!=0: git('switch','--orphan','generated-repository',cwd=work)
        git('rm','-rf','--ignore-unmatch','.',cwd=work)
        for item in output.iterdir():
            if item.is_dir(): shutil.copytree(item,work/item.name,dirs_exist_ok=True)
            else: shutil.copy2(item,work/item.name)
        git('add','.',cwd=work)
        if git('diff','--cached','--quiet',cwd=work,check=False).returncode:
            git('commit','-m','Publish verified Aniyomi extensions',cwd=work)
            git('push','origin','HEAD:refs/heads/repo',cwd=work)
        print('Published the repo branch successfully.')
    finally:
        git('worktree','remove','--force',str(work),check=False)

if __name__=='__main__':main()
