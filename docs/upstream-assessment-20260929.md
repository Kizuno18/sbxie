# Upstream contribution assessment

Checked on September 29, 2026 against `sandboxie-plus/Sandboxie` master at
`fe6ed442`, the open PR list, relevant closed/merged PRs, and searches for
rename, self-update, selfupdate, running executable, sharing violation,
NtSetInformationFile, LibraryPath, and NtCRT.

## Existing contributions

| Local change | Upstream status | Recommendation |
| --- | --- | --- |
| Deferred identity-profile checkbox save | [#5594](https://github.com/sandboxie-plus/Sandboxie/pull/5594) is open; its head `57f4f66f` already contains the same five-file fix | Do not open a duplicate |
| Stale uninstall-key detection and offline add-on removal | [#5596](https://github.com/sandboxie-plus/Sandboxie/pull/5596) is open; its current diff contains both local fixes | Keep discussion and fixes in that PR |
| Classic copyright formatting on code page 936 | [#5599](https://github.com/sandboxie-plus/Sandboxie/pull/5599) was merged on September 21 | No new PR needed |
| Native proxy profiles, INI write failures, and redacted stack exports | [#5591](https://github.com/sandboxie-plus/Sandboxie/pull/5591), [#5593](https://github.com/sandboxie-plus/Sandboxie/pull/5593), and [#5597](https://github.com/sandboxie-plus/Sandboxie/pull/5597) are open | Keep each existing contribution separate |

## Image rename handling

This is the strongest new contribution candidate. No matching PR was found
in the searches above. The change tracks the renamed image path instead of
continuing to protect the old filename, and retains DELETE access for
internal rename opens. It belongs in a focused PR containing `file.c`,
`file_init.c`, a changelog entry, and a portable reproduction/test.

Issue [#4490](https://github.com/sandboxie-plus/Sandboxie/issues/4490) reports
Ubisoft Connect failing to replace its executable with ERROR_SHARING_VIOLATION
under both V1 and V2 virtualization. It is potentially related; this patch
has not been tested against that launcher and must not claim to fix it yet.

Before submission, rebuild against current upstream and collect fresh Win32
and x64 runtime evidence for V1/V2, host-origin and sandbox-origin executables,
failed renames, repeated rename/rename-back, hard links, concurrent operations,
and continued write protection of the running image and unchanged host files.
The Qt identity tests do not validate any of these hook behaviors.

## Standalone build library paths

No matching PR was found for the `Sandbox32.props`/`Sandbox64.props` change.
A separate small build PR may be useful if a clean standalone project build
reproduces the missing common-library lookup. Confirm the failing command
and validate clean Win32/x64 builds, library selection without stale outputs,
and unaffected ARM64/ARM64EC builds before proposing it.

The current machine cannot supply that evidence: its Visual Studio C++
toolchain is missing. Successful full-solution CI builds, if available, do
not by themselves reproduce or prove the standalone build issue.

## Fork-only material

The local deployment/configuration scripts, historical compiled files,
snapshot release, and `main` branch policy are maintenance for this fork.
They should not be bundled into either prospective upstream PR. This audit
does not create, update, or comment on upstream contributions.
