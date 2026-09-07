import hashlib
import json
import subprocess
import sys
from pathlib import Path

BASE = 'b594a279e7303d4a33b8e1adba8d6c9fa59ba8e1'
EXPECTED = {
    'SandboxiePlus/tests/ini-write/raw_ini_test.cpp': '23beaa4bd637e2142976fc7d6ba2e8567e55b7ed',
    'SandboxiePlus/tests/ini-write/CMakeLists.txt': 'fcade09e44caa6e0d9ab2846cc1c8f16db2ea2b2',
}

ADDITION = r'''
template<class T> static void PartialFailureRetry(bool tree)
{
	for (const auto& Action : {"save", "apply", "ok"}) {
		T Window(tree);
		Window.SetIniEdit(true);
		const QString Pending = Window.Code.GetCode();
		const QString Before = Window.Storage.Persisted;
		Window.Storage.Fail = true;
		Window.Storage.PartialWrite = true;
		Invoke(Window, Action);
		CHECK(Window.Storage.Writes == 1 && Window.Storage.Persisted != Before);
		CHECK(Window.Storage.Persisted != Pending && Window.Code.GetCode() == Pending);
		CHECK(Window.Loads == 0 && Window.IniLoads == 0 && Window.Closed == 0);
		CHECK(Window.StructuredSaves == 0 && Gui.Errors.size() == 1);
		CHECK(Gui.Errors[0].Code == -123 && Gui.ErrorParent == &Window);
		CheckEditing(Window);
		Window.Storage.Fail = false;
		Window.Storage.PartialWrite = false;
		Invoke(Window, Action);
		CHECK(Window.Storage.Writes == 2 && Window.Storage.Persisted == Pending);
		CHECK(Window.Code.GetCode() == Pending && Gui.Errors.size() == 1);
		CHECK(Window.StructuredSaves == 0 && Window.Closed == (QString(Action) == "ok" ? 1 : 0));
	}
}
'''


def run(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args]).decode().strip()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise SystemExit('Unexpected source fragment count')
    return text.replace(old, new, 1)


def apply(root):
    if run(root, 'rev-parse', 'HEAD') != BASE:
        raise SystemExit('Unexpected source revision')
    for path, sha in EXPECTED.items():
        if run(root, 'hash-object', path) != sha:
            raise SystemExit('Unexpected source blob: ' + path)
    p = root / 'SandboxiePlus/tests/ini-write/raw_ini_test.cpp'
    text = p.read_text(encoding='utf-8')
    text = replace_once(text, '\tbool Fail = false;', '\tbool Fail = false;\n\tbool PartialWrite = false;')
    text = replace_once(text, '\t\tif (Fail) return {-123, "synthetic_write_failure"};', '\t\tif (Fail) {\n\t\t\tif (PartialWrite) Persisted = "# synthetic partial write\\nEnabled=y\\n";\n\t\t\treturn {-123, "synthetic_write_failure"};\n\t\t}')
    text = replace_once(text, '\nint main(int argc, char** argv)', ADDITION + '\nint main(int argc, char** argv)')
    text = replace_once(text, '\t\t{"global-cancel", Cancel<CSettingsWindow>}, {"global-structured", Structured}', '\t\t{"global-cancel", Cancel<CSettingsWindow>}, {"global-structured", Structured},\n\t\t{"box-partial", PartialFailureRetry<COptionsWindow>}, {"global-partial", PartialFailureRetry<CSettingsWindow>}')
    p.write_bytes(text.encode('utf-8'))
    p = root / 'SandboxiePlus/tests/ini-write/CMakeLists.txt'
    text = p.read_text(encoding='utf-8')
    text = replace_once(text, 'global-empty global-cancel global-structured)', 'global-empty global-cancel global-structured box-partial global-partial)')
    p.write_bytes(text.encode('utf-8'))
    if set(run(root, 'diff', '--name-only').splitlines()) != set(EXPECTED):
        raise SystemExit('Unexpected changed paths')
    subprocess.run(['git', '-C', str(root), 'diff', '--check'], check=True)
    patch = subprocess.check_output(['git', '-C', str(root), 'diff', '--full-index'])
    Path('partial-save-reviewed.patch').write_bytes(patch)
    Path('partial-save-manifest.json').write_text(json.dumps({
        'base': BASE,
        'patch_sha256': hashlib.sha256(patch).hexdigest(),
        'files': {p: run(root, 'hash-object', p) for p in EXPECTED},
    }, indent=2))


def projects():
    root = Path('source/SandboxiePlus/tests/ini-write').resolve()
    for target, generator, source in [('ini_write_test', 'generate_fixture.py', 'ini_write_test.cpp'), ('raw_ini_test', 'generate_raw_fixture.py', 'raw_ini_test.cpp')]:
        out = Path('fixture-' + target)
        out.mkdir(exist_ok=True)
        subprocess.run([sys.executable, str(root / generator), str(out)], check=True)
        text = 'TEMPLATE = app\nTARGET = ' + target + '\nQT += widgets\nCONFIG += console c++17 release\nCONFIG -= debug debug_and_release app_bundle\nDESTDIR = .\nINCLUDEPATH += .\nSOURCES += ' + (root / source).as_posix() + '\n'
        (out / 'fixture.pro').write_text(text)


if __name__ == '__main__':
    if sys.argv[1] == 'projects':
        projects()
    else:
        apply(Path(sys.argv[1]))
