import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

BASE = 'ebaeaa84d7e1ef1623f663fdd5beb9f22ea7b619'
UPSTREAM = '487d56309fafe90e2771d4c9004333fe01b77094'
BRANCH = 'fix/ini-write-errors-20260907'
PATCH_HASH = 'd0556aaa1b51384d94b57d3bbfeabb4832b5d131007c7ffb229356d3e112c9c9'
EXPECTED = {
    'SandboxiePlus/SandMan/Windows/OptionsWindow.cpp': '1a7437d0c1eeceff6965cd3c53c7c07987aff613',
    'SandboxiePlus/tests/ini-write/CMakeLists.txt': '30b33496ae80fae724c1deca005fb904171393d2',
    'SandboxiePlus/tests/ini-write/README.md': '03406ab6152beee37b748d0a50da41668e87dcd2',
    'SandboxiePlus/tests/ini-write/generate_raw_fixture.py': '570dea481804ba910e42158966a6d1028ba5140e',
    'SandboxiePlus/tests/ini-write/raw_ini_test.cpp': '2106db0725cc84a573cba793d926b11dbcada989',
}


def output(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args]).decode().strip()


def run(root, *args):
    subprocess.run(['git', '-C', str(root), *args], check=True)


def apply(root, patch):
    if output(root, 'rev-parse', 'HEAD') != BASE:
        raise SystemExit('Unexpected source revision')
    if hashlib.sha256(patch).hexdigest() != PATCH_HASH:
        raise SystemExit('Patch bytes do not match the reviewed diff')
    for args in [('apply', '--check', '-'), ('apply', '-')]:
        subprocess.run(['git', '-C', str(root), *args], input=patch, check=True)
    if set(output(root, 'diff', '--name-only').splitlines()) != set(EXPECTED):
        raise SystemExit('Unexpected changed paths')
    for path, sha in EXPECTED.items():
        if output(root, 'hash-object', path) != sha:
            raise SystemExit('Unexpected reviewed blob: ' + path)
    run(root, 'diff', '--check')
    Path('cancel-save-manifest.json').write_text(json.dumps({'base': BASE, 'patch_sha256': PATCH_HASH, 'files': EXPECTED}, indent=2))


def publish(patch):
    root = Path('.')
    def check_remote():
        line = output(root, 'ls-remote', '--heads', 'origin', 'refs/heads/' + BRANCH)
        if not line or line.split()[0] != BASE:
            raise SystemExit('Contribution branch moved; existing work was not overwritten')
    check_remote()
    run(root, 'fetch', '--no-tags', '--depth=5', 'origin', BASE)
    run(root, 'switch', '-c', BRANCH, 'FETCH_HEAD')
    apply(root, patch)
    run(root, 'add', '--', *EXPECTED)
    run(root, 'diff', '--cached', '--check')
    check_remote()
    if output(root, 'branch', '--show-current') != BRANCH:
        raise SystemExit('Unexpected commit branch')
    run(root, 'config', 'user.name', 'Kizuno18')
    run(root, 'config', 'user.email', '110933270+Kizuno18@users.noreply.github.com')
    run(root, 'commit', '-m', 'Invalidate structured options after failed raw writes')
    run(root, 'push', 'origin', 'HEAD:refs/heads/' + BRANCH)
    commit = output(root, 'rev-parse', 'HEAD')
    paths = output(root, 'diff', '--name-only', UPSTREAM, 'HEAD').splitlines()
    with ZipFile('ini-round4-published.zip', 'w', ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, path)
        archive.writestr('ini-write-complete.patch', subprocess.check_output(['git', 'diff', '--full-index', UPSTREAM, 'HEAD']))
        archive.writestr('cancel-review.patch', patch)
        archive.writestr('published-commit.txt', commit + '\n')
        archive.writestr('source-manifest.json', json.dumps({'commit': commit, 'base': UPSTREAM, 'files': {path: output(root, 'rev-parse', 'HEAD:' + path) for path in paths}}, indent=2))
        archive.write('cancel-save-manifest.json')
    print('Published reviewed commit ' + commit)


if __name__ == '__main__':
    patch = subprocess.check_output(['git', 'show', 'HEAD:cancel-save-review.patch'])
    if sys.argv[1] == 'publish':
        publish(patch)
    else:
        apply(Path(sys.argv[1]), patch)
