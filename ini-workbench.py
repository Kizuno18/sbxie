import base64
import hashlib
import lzma
from pathlib import Path
import subprocess
import sys

BASE = '487d56309fafe90e2771d4c9004333fe01b77094'
BRANCH = 'fix/ini-write-errors-20260907'
EXPECTED = {
    'CHANGELOG.md': '1a63c346d0544fb5e4e179a49883e6fd7cb31444',
    'SandboxiePlus/QSbieAPI/Sandboxie/SbieIni.cpp': '6d8a4ccc3b760031a0ab5bcd0aefffed1e078fcb',
    'SandboxiePlus/SandMan/Windows/OptionsWindow.cpp': 'cd39db74ea7993b6cfea8fd365ca027e671dfe62',
    'SandboxiePlus/SandMan/Windows/OptionsWindow.h': 'b09eb43ab98af235c6965c99d2575c43b5afcb45',
    'SandboxiePlus/tests/ini-write/CMakeLists.txt': 'c1203cd9d7edea68fcfd314e64fe60ac3d499ee7',
    'SandboxiePlus/tests/ini-write/README.md': 'bf8cd9484db635b4060ed727dfc683170f82209e',
    'SandboxiePlus/tests/ini-write/generate_fixture.py': '5e403b97ec1f9203ab95ca828172b493aa0a66b2',
    'SandboxiePlus/tests/ini-write/ini_write_test.cpp': '1aa747dfacb73dc2d1364c9a8740b5ab35fb4a36',
}

if sys.argv[1:] not in (['source'], ['publish']):
    raise SystemExit('Expected source or publish')
publish = sys.argv[1] == 'publish'
encoded = subprocess.check_output(['git', 'show', 'HEAD:ini-write-errors.patch.xz.b64']).strip()
if len(encoded) > 65536:
    raise SystemExit('Patch transport exceeds limit')
decoder = lzma.LZMADecompressor(memlimit=128 * 1024 * 1024)
patch = decoder.decompress(base64.b64decode(encoded, validate=True), max_length=1024 * 1024)
if not decoder.eof or decoder.unused_data or hashlib.sha256(patch).hexdigest() != '339f8ead968604d8b23215a02c15f90e8b2129fc292370939ac6fe415c4b1ce6':
    raise SystemExit('Patch integrity check failed')
root = '.' if publish else 'source'
def git(*args):
    return subprocess.check_output(['git', '-C', root, *args]).decode().strip()
def check_remote():
    if git('ls-remote', '--heads', 'origin', 'refs/heads/' + BRANCH).split()[0] != BASE:
        raise SystemExit('Contribution branch changed')
if publish:
    check_remote()
    git('fetch', '--no-tags', 'origin', BASE)
    git('switch', '-c', BRANCH, 'FETCH_HEAD')
if git('rev-parse', 'HEAD') != BASE:
    raise SystemExit('Wrong source base')
for args in (['apply', '--check', '-'], ['apply', '-']):
    subprocess.run(['git', '-C', root, *args], input=patch, check=True)
git('add', '-N', 'SandboxiePlus/tests/ini-write')
git('diff', '--check')
if set(git('diff', '--name-only').splitlines()) != set(EXPECTED):
    raise SystemExit('Unexpected contribution paths')
for path, expected in EXPECTED.items():
    if git('hash-object', path) != expected:
        raise SystemExit('Reviewed blob mismatch: ' + path)
print('Verified reviewed patch and all eight contribution files', flush=True)
if publish:
    if git('branch', '--show-current') != BRANCH:
        raise SystemExit('Wrong contribution branch')
    check_remote()
    git('add', '--', *EXPECTED)
    git('diff', '--cached', '--check')
    git('config', 'user.name', 'Kizuno18')
    git('config', 'user.email', '110933270+Kizuno18@users.noreply.github.com')
    git('commit', '-m', 'Fix INI write errors and keep failed options edits')
    git('push', 'origin', 'HEAD:refs/heads/' + BRANCH)
    print('Published commit: ' + git('rev-parse', 'HEAD'))
