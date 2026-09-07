import subprocess
import sys
from pathlib import Path

EXPECTED = sys.argv[2]


def verify(root):
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD']).decode().strip()
    if head != EXPECTED:
        raise SystemExit('Unexpected source revision ' + head)
    Path('round5-manifest.txt').write_text('commit ' + head + '\n' + subprocess.check_output(['git', '-C', str(root), 'ls-tree', 'HEAD', '--', 'SandboxiePlus/SandMan/Windows/SettingsWindow.cpp', 'SandboxiePlus/SandMan/Windows/SettingsWindow.h', 'SandboxiePlus/tests/ini-write/raw_ini_test.cpp', 'SandboxiePlus/tests/ini-write/CMakeLists.txt']).decode())


def projects(root):
    tests = (root / 'SandboxiePlus/tests/ini-write').resolve()
    for target, generator, source in [('ini_write_test', 'generate_fixture.py', 'ini_write_test.cpp'), ('raw_ini_test', 'generate_raw_fixture.py', 'raw_ini_test.cpp')]:
        out = Path('fixture-' + target)
        out.mkdir(exist_ok=True)
        subprocess.run([sys.executable, str(tests / generator), str(out)], check=True)
        (out / 'fixture.pro').write_text('TEMPLATE = app\nTARGET = ' + target + '\nQT += widgets\nCONFIG += console c++17 release\nCONFIG -= debug debug_and_release app_bundle\nDESTDIR = .\nINCLUDEPATH += .\nSOURCES += ' + (tests / source).as_posix() + '\n')


if __name__ == '__main__':
    verify(Path('source'))
    if sys.argv[1] == 'projects':
        projects(Path('source'))
