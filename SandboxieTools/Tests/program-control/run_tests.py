import argparse
from pathlib import Path
import re
import subprocess
import tempfile


def definition(source, name):
    matches = re.findall(r"^static [\w *]+\b" + name + r"\([^;{]*\)\n\{.*?^\}", source, re.M | re.S)
    if len(matches) != 1:
        raise RuntimeError(f"Expected one definition of {name}")
    return matches[0]


def build_fixture(root):
    server = (root / "Sandboxie/core/svc/UserServer.cpp").read_text(encoding="utf-8")
    wire = (root / "Sandboxie/core/svc/UserWire.h").read_text(encoding="utf-8")
    request = re.search(r"struct tagUSER_SHELL_EXEC_REQ\s*\{.*?\};", wire, re.S)
    if request is None:
        raise RuntimeError("Document request structure not found")
    prefix = r'''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
typedef wchar_t WCHAR;
typedef uint32_t ULONG;
typedef unsigned char UCHAR;
typedef int BOOLEAN;
#define TRUE 1
#define FALSE 0
static size_t test_len(const WCHAR* p) { size_t n = 0; while (p[n]) ++n; return n; }
static WCHAR lower(WCHAR c) { return c >= L'A' && c <= L'Z' ? c + 32 : c; }
static int test_ncmp(const WCHAR* a, const WCHAR* b, size_t n) {
    for (size_t i = 0; i < n; ++i) {
        if (lower(a[i]) != lower(b[i])) return lower(a[i]) - lower(b[i]);
        if (!a[i]) return 0;
    }
    return 0;
}
static int test_cmp(const WCHAR* a, const WCHAR* b) { return test_ncmp(a, b, test_len(a) + 1); }
static WCHAR* test_chr(const WCHAR* a, WCHAR c) {
    for (;;) { if (*a == c) return (WCHAR*)a; if (!*a) return NULL; ++a; }
}
#define wcslen test_len
#define wcschr test_chr
#define _wcsicmp test_cmp
#define _wcsnicmp test_ncmp
#define PROGRAM_CONTROL_RULE_NO_CRT
#define PROGRAM_CONTROL_RULE_NO_QUERY_HELPERS
#include "program_control_rule.h"
'''
    tests = r'''
static int failures;
static void check(int ok, const char* name) { if (!ok) { printf("FAIL: %s\n", name); ++failures; } }
static void test_rules(void) {
    SBIE_NORMALIZED_RULE rule;
    WCHAR value[] = L"C:\\Apps|Priority=4|Recursive=1-2|TargetBox=Work";
    check(ProgramControl_ParseRuleExtensionsInPlace(value, &rule, 1), "Parse extensions");
    check(rule.has_priority && rule.priority == 4, "Priority value");
    check(rule.has_target_box && !test_cmp(rule.target_box, L"Work"), "Target box");
    check(rule.has_recursive && rule.recursive_min_depth == 1 && rule.recursive_depth == 2, "Depth range");
    check(!ProgramControl_MatchFolderRuleNormalized(&rule, L"C:\\Apps", 7), "Minimum depth");
    check(ProgramControl_MatchFolderRuleNormalized(&rule, L"C:\\Apps\\One", 11), "One level");
    check(!ProgramControl_MatchFolderRuleNormalized(&rule, L"C:\\Apps\\One\\Two\\Three", 21), "Maximum depth");
    WCHAR disabled[] = L"app.exe|Priority=3|TargetBox=Work";
    check(ProgramControl_ParseRuleExtensionsInPlace(disabled, &rule, 0), "Disabled extensions");
    check(!test_cmp(rule.base_rule, L"app.exe") && !rule.has_priority && !rule.has_target_box, "Legacy base rule");
    long number;
    check(!ProgramControl_ParseLong(L"2147483648", &number), "Windows long overflow");
    check(!ProgramControl_ParseLong(L"1x", &number), "Invalid number");
    check(ProgramControl_MatchProcessRule(L"Editor?.exe", L"editor1.exe", L"C:\\editor1.exe", 14), "Image wildcard");
    check(!ProgramControl_MatchFolderRule(L"C:\\Apps", L"C:\\AppsExtra", 12), "Folder boundary");
    check(ProgramControl_WildcardMatchNI(L"A?*Z", L"abcZ", 4), "Case-insensitive wildcard");
    check(!ProgramControl_WildcardMatchNI(L"A?*Z", L"abcZ", 3), "Bounded wildcard");
    check(ProgramControl_WildcardMatchNI(L"***", L"", 0), "Empty wildcard");
    check(ProgramControl_MatchDocumentRule(L"*.txt", L"C:\\a.txt trailing", 8), "Bounded document path");
    check(ProgramControl_ShouldReplacePriorityWinner(1, 1, 9, 1, 3), "Lower priority wins");
    check(!ProgramControl_ShouldReplacePriorityWinner(1, 1, 3, 0, -1), "Explicit priority retained");
    check(!ProgramControl_ShouldReplacePriorityWinner(1, 1, 3, 1, 3), "Stable ties");
}
static void test_policy(void) {
    SBIE_POLICY_INPUT in = {0};
    SBIE_RULE_MATCH_SET matches = {0};
    in.context_kind = SBIE_CTX_SANDBOXED_PROCESS_START;
    in.source_equals_candidate_box = 1;
    matches.breakout_document_match = 1;
    check(SbiePolicy_ResolveDecision(&in, &matches) == SBIE_DECISION_NO_MATCH, "Process and document contexts");
    in.context_kind = SBIE_CTX_SANDBOXED_DOCUMENT_OPEN;
    check(SbiePolicy_ResolveDecision(&in, &matches) == SBIE_DECISION_BREAKOUT_UNBOXED, "Document context");
    matches.force_process_match = 1;
    check(SbiePolicy_ResolveWithPriorities(&in, &matches, 0, 0, -1, 0, -1) == SBIE_DECISION_FORCE_SAME_BOX, "Default force precedence");
    check(SbiePolicy_ResolveWithPriorities(&in, &matches, 0, 1, 8, 1, 3) == SBIE_DECISION_BREAKOUT_UNBOXED, "Explicit breakout priority");
    matches.breakout_has_target = 1;
    check(SbiePolicy_ResolveWithPriorities(&in, &matches, 0, 1, 8, 1, 3) == SBIE_DECISION_BREAKOUT_TARGET_BOX, "Target routing");
    in.context_kind = SBIE_CTX_SANDBOXED_PROCESS_START;
    in.caller_forced_by_children = 1;
    matches.breakout_document_match = 0;
    matches.breakout_process_match = 1;
    check(SbiePolicy_ResolveDecision(&in, &matches) == SBIE_DECISION_FORCE_SAME_BOX, "Forced child stays boxed");
}
static void test_wire(void) {
    ULONG storage[64] = {0};
    USER_SHELL_EXEC_REQ* req = (USER_SHELL_EXEC_REQ*)storage;
    WCHAR* path;
    const WCHAR* image;
    const WCHAR* launch;
    req->FileNameOffset = 8;
    memcpy((char*)req + 8, L"C:\\a.txt", 18);
    check(UserServer_ParseDocumentRequest(req, 26, &path, &image, &launch), "Legacy request");
    check(!image && !launch, "Legacy fields are not offsets");
    memset(storage, 0, sizeof(storage));
    req->FileNameOffset = sizeof(*req);
    memcpy((char*)req + sizeof(*req), L"C:\\a.txt", 18);
    check(UserServer_ParseDocumentRequest(req, sizeof(*req) + 18, &path, &image, &launch), "New request");
    check(!UserServer_ParseDocumentRequest(req, sizeof(*req) + 16, &path, &image, &launch), "Missing terminator");
    req->ImageNameOffset = 2;
    check(!UserServer_ParseDocumentRequest(req, sizeof(storage), &path, &image, &launch), "Header offset");
    req->ImageNameOffset = sizeof(storage) + 2;
    check(!UserServer_ParseDocumentRequest(req, sizeof(storage), &path, &image, &launch), "Outside request");
    req->ImageNameOffset = 17;
    check(!UserServer_ParseDocumentRequest(req, sizeof(storage), &path, &image, &launch), "Misaligned offset");
    req->ImageNameOffset = 0;
    req->LaunchPathOffset = sizeof(*req);
    check(!UserServer_ParseDocumentRequest(req, sizeof(storage), &path, &image, &launch), "Launch requires image");
    check(!UserServer_ParseDocumentRequest(req, 4, &path, &image, &launch), "Short header");
    req->LaunchPathOffset = 0;
    memcpy((char*)req + sizeof(*req), L"a\"b", 8);
    check(!UserServer_ParseDocumentRequest(req, sizeof(storage), &path, &image, &launch), "Invalid path quoting");
}
static void test_wildcard_stress(void) {
    WCHAR pattern[100], text[100];
    for (int i = 0; i < 40; ++i) { pattern[2*i] = L'*'; pattern[2*i+1] = L'a'; text[i] = L'a'; }
    pattern[80] = L'b'; pattern[81] = 0; text[40] = 0;
    check(!ProgramControl_WildcardMatchNI(pattern, text, 40), "Repeated wildcard failure");
}
static int reference_match(const WCHAR* p, const WCHAR* t) {
    if (!*p) return !*t;
    if (*p == L'*') return reference_match(p + 1, t) || (*t && reference_match(p, t + 1));
    return *t && (*p == L'?' || lower(*p) == lower(*t)) && reference_match(p + 1, t + 1);
}
static void test_wildcard_equivalence(void) {
    const WCHAR alphabet[] = L"aB?*";
    WCHAR pattern[6], text[5];
    for (unsigned n = 0; n <= 5; ++n) {
        for (unsigned p = 0; p < (1u << (2 * n)); ++p) {
            for (unsigned i = 0; i < n; ++i) pattern[i] = alphabet[(p >> (2 * i)) & 3];
            pattern[n] = 0;
            for (unsigned m = 0; m <= 4; ++m) {
                for (unsigned t = 0; t < (1u << m); ++t) {
                    for (unsigned i = 0; i < m; ++i) text[i] = ((t >> i) & 1) ? L'b' : L'A';
                    text[m] = 0;
                    check(ProgramControl_WildcardMatchNI(pattern, text, m) == reference_match(pattern, text), "Wildcard equivalence");
                }
            }
        }
    }
}
int main(int argc, char** argv) {
    (void)argv;
    check(sizeof(WCHAR) == 2, "Windows WCHAR width");
    if (argc > 1) test_wildcard_stress();
    else { test_rules(); test_policy(); test_wire(); test_wildcard_equivalence(); }
    if (!failures) puts("Program-control checks passed");
    return failures ? 1 : 0;
}
'''
    return (prefix + request.group(0) + "\ntypedef struct tagUSER_SHELL_EXEC_REQ USER_SHELL_EXEC_REQ;\n"
            + definition(server, "UserServer_GetReqStringByOffset") + "\n"
            + definition(server, "UserServer_ParseDocumentRequest") + "\n" + tests)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-sanitize", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "program_control_test.c"
        binary = Path(directory) / "program_control_test"
        source.write_text(build_fixture(root), encoding="utf-8")
        flags = [] if args.no_sanitize else ["-fsanitize=address,undefined"]
        subprocess.run(["cc", "-std=c11", "-fshort-wchar", "-Wall", "-Wextra", "-Werror", "-g",
                        *flags, "-I", str(root / "Sandboxie/common"), str(source), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True, timeout=10)
        subprocess.run([str(binary), "stress"], check=True, timeout=5)


if __name__ == "__main__":
    main()
