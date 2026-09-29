import argparse
from pathlib import Path
import re
import subprocess
import tempfile


def build_fixture(root):
    source = (root / "Sandboxie/core/dll/file_junction.c").read_text(encoding="utf-8")
    structure = re.search(r"typedef struct _FILE_JUNCTION_ENTRY \{.*?\} FILE_JUNCTION_ENTRY;", source, re.S)
    if structure is None:
        raise RuntimeError("Junction entry definition not found")
    names = ["File_Junction_GetSuffix", "File_Junction_IsBoundary", "File_Junction_FindForward", "File_Junction_FindReverse",
             "File_Junction_BlockRawAccessPath", "File_Junction_IsMappedSrc",
             "File_ApplyJunctionMap", "File_ApplyJunctionMapReverse", "File_ApplyJunctionMapReverseInPlace"]
    definitions = []
    for name in names:
        matches = re.findall(r"^[\w *]+\b" + name + r"\([^;{]*\)\n\{.*?^\}", source, re.M | re.S)
        if len(matches) != 1:
            raise RuntimeError(f"Expected one definition of {name}")
        definitions.append(matches[0])
    prefix = r'''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
typedef wchar_t WCHAR;
typedef uint32_t ULONG;
typedef uint8_t BOOLEAN;
typedef int THREAD_DATA;
#define _FX
#define TRUE 1
#define FALSE 0
static int allocationFailure;
static size_t test_len(const WCHAR* p) { size_t n = 0; while (p[n]) ++n; return n; }
static int test_ncmp(const WCHAR* a, const WCHAR* b, size_t n) {
    for (size_t i = 0; i < n; ++i) {
        WCHAR x = a[i], y = b[i];
        if (x >= L'A' && x <= L'Z') x += 32;
        if (y >= L'A' && y <= L'Z') y += 32;
        if (x != y) return x - y;
        if (!x) return 0;
    }
    return 0;
}
#define wcslen test_len
#define _wcsnicmp test_ncmp
#define wmemcpy(d,s,n) memcpy((d),(s),(n)*sizeof(WCHAR))
#define wmemmove(d,s,n) memmove((d),(s),(n)*sizeof(WCHAR))
static void* Dll_AllocTemp(size_t count) { return allocationFailure ? NULL : malloc(count); }
'''
    globals_source = "\n".join(re.findall(r"^static (?:FILE_JUNCTION_ENTRY|ULONG|BOOLEAN) [^\n]* = [^\n]*;", source, re.M))
    tests = r'''
static int failures;
static void check(int ok, const char* name) { if (!ok) { printf("FAIL: %s\n", name); ++failures; } }
static void setup(FILE_JUNCTION_ENTRY* entry, const WCHAR* src, const WCHAR* dst) {
    memset(entry, 0, sizeof(*entry));
    entry->src = (WCHAR*)src; entry->src_len = wcslen(src);
    entry->dst = (WCHAR*)dst; entry->dst_len = wcslen(dst);
}
static int equal(const WCHAR* a, const WCHAR* b) {
    return a && b && wcslen(a) == wcslen(b) && _wcsnicmp(a, b, wcslen(a)) == 0;
}
static void forward(const WCHAR* input, const WCHAR* expected, const char* name) {
    WCHAR* result = File_ApplyJunctionMap(NULL, (WCHAR*)input);
    check(equal(result, expected), name);
    if (result != input) free(result);
}
static void reverse(const WCHAR* input, const WCHAR* expected, const char* name) {
    WCHAR* result = File_ApplyJunctionMapReverse(NULL, (WCHAR*)input, wcslen(input));
    check(equal(result, expected), name);
    free(result);
}
int main(void) {
    check(sizeof(WCHAR) == 2, "Windows WCHAR width");
    FILE_JUNCTION_ENTRY entries[2];
    File_JunctionEntries = entries; File_JunctionCount = 1;
    setup(&entries[0], L"C:\\virtual", L"D:\\target");
    forward(L"c:\\VIRTUAL\\file", L"D:\\target\\file", "Case-insensitive mapping");
    forward(L"C:\\virtuality\\file", L"C:\\virtuality\\file", "Prefix boundary");
    reverse(L"D:\\target\\file", L"C:\\virtual\\file", "Reverse mapping");
    check(!File_Junction_BlockRawAccessPath(L"D:\\target", 9), "Raw blocking opt-in default");
    File_Junction_BlockRawAccess = TRUE;
    check(File_Junction_BlockRawAccessPath(L"D:\\target", 9), "Raw blocking enabled");
    check(File_Junction_IsMappedSrc(L"C:\\virtual", 10), "Source lookup");
    setup(&entries[1], L"C:\\virtual\\nested", L"E:\\specific");
    File_JunctionCount = 2;
    forward(L"C:\\virtual\\nested\\file", L"E:\\specific\\file", "Longest prefix");
    File_JunctionCount = 1;
    setup(&entries[0], L"C:\\", L"D:\\target");
    forward(L"C:\\file", L"D:\\target\\file", "Source drive-root separator");
    reverse(L"D:\\target\\file", L"C:\\file", "Reverse drive-root separator");
    WCHAR inplace[64];
    wmemcpy(inplace, L"D:\\target\\file", 15);
    File_ApplyJunctionMapReverseInPlace(inplace, wcslen(inplace), 64);
    check(equal(inplace, L"C:\\file"), "In-place drive-root separator");
    setup(&entries[0], L"C:\\virtual", L"D:\\");
    forward(L"C:\\virtual\\file", L"D:\\file", "Target drive-root separator");
    reverse(L"D:\\file", L"C:\\virtual\\file", "Reverse target-root separator");
    wmemcpy(inplace, L"D:\\file", 8);
    ULONG required = File_ApplyJunctionMapReverseInPlace(inplace, wcslen(inplace), 8);
    check(required == wcslen(L"C:\\virtual\\file") + 1, "Required capacity on short buffer");
    check(equal(inplace, L"D:\\file"), "Short buffer stays untouched");
    allocationFailure = 1;
    check(File_ApplyJunctionMap(NULL, L"C:\\virtual\\file") == NULL, "Allocation failure must not access original path");
    return failures ? 1 : 0;
}
'''
    return prefix + structure.group(0) + "\n" + globals_source + "\n" + "\n".join(definitions) + "\n" + tests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit-only", type=Path)
    args = parser.parse_args()
    fixture = build_fixture(Path(__file__).resolve().parents[3])
    if args.emit_only:
        args.emit_only.write_text(fixture, encoding="utf-8")
        return
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "junction_test.c"
        binary = Path(directory) / "junction_test"
        source.write_text(fixture, encoding="utf-8")
        subprocess.run(["cc", "-std=c11", "-fshort-wchar", "-Wall", "-Wextra", "-Werror",
                        "-Wno-unused-parameter", "-Wno-unused-but-set-variable",
                        "-fsanitize=address,undefined", "-g", str(source), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
