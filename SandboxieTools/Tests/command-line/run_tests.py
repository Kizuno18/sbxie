import argparse
from pathlib import Path
import re
import subprocess
import tempfile


def build_fixture(root):
    kernel = (root / "Sandboxie/core/dll/kernel.c").read_text(encoding="utf-8")
    start = kernel.index("\tif (!Kernel_CommandLineW.Buffer) {")
    end = kernel.index('\n\tif (SbieApi_QueryConfBool(NULL, L"BlockInterferePower"', start)
    parser_source = (root / "Sandboxie/core/dll/proc.c").read_text(encoding="utf-8")
    parser = re.search(r"^_FX const WCHAR\* SbieDll_FindArgumentEnd\(const WCHAR\* arguments\)\n\{.*?^\}",
                       parser_source, re.M | re.S)
    if parser is None:
        raise RuntimeError("Command-line parser definition not found")
    prefix = r'''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
typedef wchar_t WCHAR;
typedef uint8_t BOOLEAN;
typedef uint16_t USHORT;
typedef uint32_t ULONG;
typedef size_t SIZE_T;
typedef int NTSTATUS;
typedef struct { USHORT Length, MaximumLength; WCHAR* Buffer; } UNICODE_STRING;
typedef struct { USHORT Length, MaximumLength; char* Buffer; } ANSI_STRING;
typedef struct { UNICODE_STRING CommandLine; } RTL_USER_PROCESS_PARAMETERS;
#define _FX
#define TRUE 1
#define FALSE 0
#define NT_SUCCESS(s) ((s) >= 0)
#define CONF_LINE_LEN 2048
#define ARRAYSIZE(a) (sizeof(a) / sizeof((a)[0]))
#define LMEM_FIXED 0
#define SBIEDLL_HOOK(prefix, name) ((void)name)
static size_t test_len(const WCHAR* p) { size_t n = 0; while (p[n]) ++n; return n; }
static WCHAR* test_chr(const WCHAR* p, WCHAR c) { while (*p && *p != c) ++p; return *p == c ? (WCHAR*)p : NULL; }
static int test_cmp(const WCHAR* a, const WCHAR* b) {
    for (; *a && *b; ++a, ++b) {
        WCHAR x = *a, y = *b;
        if (x >= L'A' && x <= L'Z') x += 32;
        if (y >= L'A' && y <= L'Z') y += 32;
        if (x != y) return x - y;
    }
    return *a - *b;
}
#define wcslen test_len
#define wcschr test_chr
#define _wcsicmp test_cmp
#define wmemcpy(d,s,n) memcpy((d),(s),(n)*sizeof(WCHAR))
static UNICODE_STRING Kernel_CommandLineW;
static ANSI_STRING Kernel_CommandLineA;
static RTL_USER_PROCESS_PARAMETERS parameters;
static const WCHAR* Dll_ImageName = L"app.exe";
static void* Dll_KernelBase;
static void* Dll_Kernel32;
static const WCHAR* rules[4];
static unsigned ruleCount;
static int allocationFailure, conversionFailure, allocations;
static RTL_USER_PROCESS_PARAMETERS* Proc_GetRtlUserProcessParameters(void) { return &parameters; }
static NTSTATUS SbieApi_QueryConfAsIs(void* box, const WCHAR* key, ULONG index, WCHAR* buffer, size_t count) {
    (void)box; (void)key;
    if (index >= ruleCount || wcslen(rules[index]) + 1 > count) return -1;
    wmemcpy(buffer, rules[index], wcslen(rules[index]) + 1);
    return 0;
}
static void* LocalAlloc(int flags, size_t count) {
    (void)flags;
    if (allocationFailure) return NULL;
    void* result = malloc(count);
    if (result) ++allocations;
    return result;
}
static void LocalFree(void* p) { if (p) { free(p); --allocations; } }
static NTSTATUS RtlUnicodeStringToAnsiString(ANSI_STRING* a, const UNICODE_STRING* w, int allocate) {
    (void)allocate;
    if (conversionFailure) return -1;
    a->Length = w->Length / sizeof(WCHAR);
    a->MaximumLength = a->Length + 1;
    a->Buffer = calloc(a->MaximumLength, 1);
    return a->Buffer ? 0 : -1;
}
static void* GetProcAddress(void* module, const char* name) { (void)module; (void)name; return NULL; }
'''
    tests = r'''
static void require(int ok, const char* message) { if (!ok) { fprintf(stderr, "%s\n", message); exit(1); } }
static void clear(void) {
    LocalFree(Kernel_CommandLineW.Buffer);
    free(Kernel_CommandLineA.Buffer);
    memset(&Kernel_CommandLineW, 0, sizeof(Kernel_CommandLineW));
    memset(&Kernel_CommandLineA, 0, sizeof(Kernel_CommandLineA));
    require(allocations == 0, "Allocation leak");
    allocationFailure = conversionFailure = 0;
}
static void check(const WCHAR* input, const WCHAR* rule, const WCHAR* expected) {
    parameters.CommandLine.Buffer = (WCHAR*)input;
    rules[0] = rule; ruleCount = 1;
    run_init();
    if (expected) {
        require(Kernel_CommandLineW.Buffer != NULL, "Missing command line");
        require(test_cmp(Kernel_CommandLineW.Buffer, expected) == 0, "Unexpected arguments");
        require(Kernel_CommandLineW.Length == wcslen(expected) * sizeof(WCHAR), "Incorrect length");
        require(Kernel_CommandLineW.MaximumLength == Kernel_CommandLineW.Length + sizeof(WCHAR), "Incorrect capacity");
    } else require(Kernel_CommandLineW.Buffer == NULL, "Unexpected injection");
    clear();
}
int main(void) {
    require(sizeof(WCHAR) == 2, "Fixture must use Windows-width WCHAR");
    check(L"app.exe", L"app.exe,--flag", L"app.exe --flag");
    check(L"app.exe --existing", L"APP.EXE,--flag", L"app.exe --flag --existing");
    check(L"\"C:\\Program Files\\app.exe\"\targ", L"app.exe,--flag", L"\"C:\\Program Files\\app.exe\" --flag\targ");
    check(L"app.exe arg", L"other.exe,--flag", NULL);
    check(L"app.exe arg", L"app.exe", NULL);
    check(L"app.exe arg", L"app.exe,", NULL);
    allocationFailure = 1;
    check(L"app.exe", L"app.exe,--flag", NULL);
    conversionFailure = 1;
    check(L"app.exe", L"app.exe,--flag", NULL);
    WCHAR* longLine = calloc(32768, sizeof(WCHAR));
    require(longLine != NULL, "Test allocation failed");
    for (int i = 0; i < 32765; ++i) longLine[i] = L'x';
    check(longLine, L"app.exe,a", NULL);
    longLine[32764] = 0;
    parameters.CommandLine.Buffer = longLine;
    rules[0] = L"other.exe,z"; rules[1] = L"app.exe,a"; ruleCount = 2;
    run_init();
    require(Kernel_CommandLineW.Length == 65532, "Largest valid command line rejected");
    clear();
    free(longLine);
    puts("Passed command-line injection checks, including allocation and conversion failures");
    return 0;
}
'''
    return prefix + parser.group(0) + "\nstatic void run_init(void) {\n" + kernel[start:end] + "\n}\n" + tests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit-only", type=Path)
    args = parser.parse_args()
    fixture = build_fixture(Path(__file__).resolve().parents[3])
    if args.emit_only:
        args.emit_only.write_text(fixture, encoding="utf-8")
        return
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "command_line_test.c"
        binary = Path(directory) / "command_line_test"
        source.write_text(fixture, encoding="utf-8")
        subprocess.run(["cc", "-std=c11", "-fshort-wchar", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-g", str(source), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
