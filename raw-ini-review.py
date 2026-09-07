"""Validate a pinned raw-INI review patch and publish only after CI succeeds."""
import base64
import hashlib
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys
import tempfile

BASE = '04ce40a9ad4bbfbf164a48ff990813383bfa6ee8'
BRANCH = 'fix/ini-write-errors-20260907'
PATCH_HASH = 'e7740f521f2214c3ac55423cb134618de398e366f4174b4864cbda0bacbd237b'
EXPECTED = {
    'CHANGELOG.md': '3ba58a5d754ddf085d0e50151b5cd3a210f367bd',
    'SandboxiePlus/SandMan/Windows/OptionsWindow.cpp': '00c207331f4f95db5fa786f0a2267cb6e0e96f25',
    'SandboxiePlus/SandMan/Windows/OptionsWindow.h': '2b432d212335c05fdf0707e82af6afa2ba9d7594',
    'SandboxiePlus/SandMan/Windows/SettingsWindow.cpp': '63efeb80d8bc8eefba94c1450bd5e3bdb367ab4e',
    'SandboxiePlus/SandMan/Windows/SettingsWindow.h': 'efc5a7c55f27502c77a5933bb0ad129ac3bb829f',
    'SandboxiePlus/tests/ini-write/CMakeLists.txt': 'fcade09e44caa6e0d9ab2846cc1c8f16db2ea2b2',
    'SandboxiePlus/tests/ini-write/README.md': '023e6ac1841302bd10f3f8babfc84077938019d0',
    'SandboxiePlus/tests/ini-write/generate_raw_fixture.py': '48bb03340244f626669a9f4126130f41cfd0920a',
    'SandboxiePlus/tests/ini-write/ini_write_test.cpp': '9bc0659615f7d663d0008b7de997bca3ba729b11',
    'SandboxiePlus/tests/ini-write/raw_ini_test.cpp': '23beaa4bd637e2142976fc7d6ba2e8567e55b7ed',
}


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args]).decode().strip()


def apply(root, patch):
    if git(root, 'rev-parse', 'HEAD') != BASE:
        raise SystemExit('Unexpected source revision')
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary, 'review.patch')
        path.write_bytes(patch)
        subprocess.run(['git', '-C', str(root), 'apply', '--check', str(path)], check=True)
        subprocess.run(['git', '-C', str(root), 'apply', str(path)], check=True)
    git(root, 'add', '-N', 'SandboxiePlus/tests/ini-write/generate_raw_fixture.py', 'SandboxiePlus/tests/ini-write/raw_ini_test.cpp')
    git(root, 'diff', '--check')
    changed = set(git(root, 'diff', '--name-only').splitlines())
    if changed != set(EXPECTED):
        raise SystemExit('Unexpected changed paths: ' + repr(changed ^ set(EXPECTED)))
    for name, expected in EXPECTED.items():
        data = subprocess.check_output(['git', '-C', str(root), 'hash-object', name]).decode().strip()
        if data != expected:
            raise SystemExit('Reviewed blob mismatch: ' + name)
    print('Verified exact patch and all ten contribution files')


def projects():
    base = Path('source/SandboxiePlus/tests/ini-write')
    for suffix, target in [('ini', 'ini_write_test'), ('raw', 'raw_ini_test')]:
        output = Path('fixture-' + suffix)
        for generator in ['generate_fixture.py', 'generate_raw_fixture.py']:
            subprocess.run([sys.executable, str(base / generator), str(output)], check=True)
        project = 'TEMPLATE = app\nTARGET = ' + target + '\nQT += widgets\nCONFIG += console c++17 release\nCONFIG -= debug debug_and_release app_bundle\nDESTDIR = .\nINCLUDEPATH += .\nSOURCES += ../source/SandboxiePlus/tests/ini-write/' + target + '.cpp\n'
        (output / 'fixture.pro').write_text(project, encoding='utf-8')


def main():
    if sys.argv[1:] == ['projects']:
        projects()
        return
    if len(sys.argv) != 2 or sys.argv[1] not in ['source', 'publish']:
        raise SystemExit('Expected source, projects or publish')
    encoded = subprocess.check_output(['git', 'show', 'HEAD:raw-ini-review.patch.xz.b64'])
    if len(encoded) > 65536:
        raise SystemExit('Oversized patch transport')
    decoder = lzma.LZMADecompressor(memlimit=128 * 1024 * 1024)
    patch = decoder.decompress(base64.b64decode(encoded.strip(), validate=True), max_length=1024 * 1024)
    if not decoder.eof or decoder.unused_data or hashlib.sha256(patch).hexdigest() != PATCH_HASH:
        raise SystemExit('Patch integrity check failed')
    if sys.argv[1] == 'source':
        apply(Path('source'), patch)
        Path('raw-ini-manifest.json').write_text(json.dumps({'base': BASE, 'patch_sha256': PATCH_HASH, 'files': EXPECTED}, indent=2))
        return
    if git('.', 'ls-remote', '--heads', 'origin', 'refs/heads/' + BRANCH).split()[0] != BASE:
        raise SystemExit('Destination changed; refusing to overwrite concurrent work')
    git('.', 'fetch', '--no-tags', 'origin', BASE)
    git('.', 'switch', '-c', BRANCH, 'FETCH_HEAD')
    apply(Path('.'), patch)
    git('.', 'add', '--', *EXPECTED)
    git('.', 'diff', '--cached', '--check')
    git('.', 'config', 'user.name', 'Kizuno18')
    git('.', 'config', 'user.email', '110933270+Kizuno18@users.noreply.github.com')
    if git('.', 'branch', '--show-current') != BRANCH or git('.', 'rev-parse', 'HEAD') != BASE:
        raise SystemExit('Unexpected publication branch')
    if git('.', 'ls-remote', '--heads', 'origin', 'refs/heads/' + BRANCH).split()[0] != BASE:
        raise SystemExit('Destination changed during validation')
    git('.', 'commit', '-m', 'Preserve raw INI edits after failed saves')
    commit = git('.', 'rev-parse', 'HEAD')
    git('.', 'push', 'origin', 'HEAD:refs/heads/' + BRANCH)
    if git('.', 'ls-remote', '--heads', 'origin', 'refs/heads/' + BRANCH).split()[0] != commit:
        raise SystemExit('Remote publication mismatch')
    Path('published-raw-ini.json').write_text(json.dumps({'commit': commit, 'parent': BASE, 'branch': BRANCH, 'patch_sha256': PATCH_HASH, 'files': EXPECTED}, indent=2))
    print('Published and verified ' + commit)


if __name__ == '__main__':
    main()
