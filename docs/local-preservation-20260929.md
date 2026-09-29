# Local workspace preservation

The `main` branch consolidates the source changes that were present in the
Windows checkout on September 29, 2026. The previous `master` branch and
existing contribution branches remain available. This is a fork maintenance
integration, not a combined upstream contribution.

## Source changes

- Track a running executable's path through successful renames and retain
  DELETE access for internal rename handles in SbieDll.
- Bring in the deferred identity-profile checkbox fix already published in
  upstream PR [#5594](https://github.com/sandboxie-plus/Sandboxie/pull/5594).
- Bring in the stale uninstall-key and offline removal fixes already included
  in upstream PR [#5596](https://github.com/sandboxie-plus/Sandboxie/pull/5596).
- Preserve the Classic copyright formatting correction from upstream PR
  [#5599](https://github.com/sandboxie-plus/Sandboxie/pull/5599).
- Resolve common runtime libraries relative to the property-sheet directory
  for Win32 and x64 builds.
- Preserve the six local PowerShell maintenance scripts at the repository
  root, where their existing relative paths continue to work.

The maintenance scripts modify the local Sandboxie installation and system
configuration when explicitly run. `Install-CompiledSandboxie.ps1` also
enables Windows test signing; it is not a production installer. These scripts
were preserved and syntax-checked, not executed during this migration.

## Binary and configuration snapshot

The release [local-snapshot-20260929](https://github.com/Kizuno18/sbxie/releases/tag/local-snapshot-20260929)
contains `sbxie-local-files-20260929.zip` and `local-files-manifest.csv`.
The archive preserves every pre-existing untracked or ignored file in the
checkout: 1,302 files totaling 867,583,779 bytes, including all 171 files in
`Compiled-Sandboxie/`, 1,125 compiler outputs under `Sandboxie/`, and the six
maintenance scripts. Each archive entry was checked against its original
SHA-256 and byte length. The CSV records repository-relative paths, sizes,
and hashes.

Archive SHA-256:

```text
e95e760de901ecd16a86d70b699a6d24b4b47a7dfa1ef6fb617e7dcf1eec2b10
```

Extract the ZIP at a clone's root to restore the original relative paths.
`Compiled-Sandboxie/` is now ignored because the complete snapshot is a
release asset rather than source history. The binaries are historical local
outputs and are not claimed to have been rebuilt from the final merge commit.
Temporary audit files created during this migration are not part of the
original snapshot.

## Verification

`git diff --check`, PowerShell parser checks, and XML parsing of both changed
property sheets are the local static checks. The identity-profile workflow
[passed all 32 CTest cases](https://github.com/Kizuno18/sbxie/actions/runs/36623917613)
against Qt 6 on Linux at source revision `0e0236e2`. These tests exercise the profile
model and simulated storage, not Windows hooks or the installed service.

A fresh local Win32 build was attempted with:

```powershell
MSBuild.exe Sandboxie/SandboxDll.sln /t:SboxDll /p:Configuration=SbieRelease /p:Platform=Win32 /m:4
```

It stops before compilation with MSB4019 because the installed Visual Studio
instance lacks `Microsoft.Cpp.Default.props` and its C++ toolchain. A local
Qt development installation was also unavailable. No driver or service was
replaced or restarted during preservation. Windows runtime validation remains
necessary before proposing the image-rename change upstream.

The existing Windows CI and CodeQL branch filters include `main` as well as
`master`; build entry points remain documented in `AGENTS.md` and
`.github/workflows/main.yml`.

See [the upstream assessment](upstream-assessment-20260929.md) for existing
PRs and the remaining contribution candidates.
