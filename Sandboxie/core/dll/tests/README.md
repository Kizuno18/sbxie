# Volume serial cache regression tests

This target extracts the production `Kernel_GetVolumeInformationByHandleW` hook,
its cache initialization, and the existing hexadecimal parser. It compiles them
with the real `common/map.c`. Native volume queries, name resolution, settings,
TLS bookkeeping, and randomness are mocked using synthetic data. It does not
load SbieDll, start Sandboxie, or inspect the host's actual identifiers.

## Build and run

Use an out-of-tree build with Python 3, CMake, and a C11 compiler:

```sh
cmake -S Sandboxie/core/dll/tests -B build/volume-tests -DCMAKE_BUILD_TYPE=Release
cmake --build build/volume-tests --config Release
ctest --test-dir build/volume-tests -C Release --output-on-failure
```

For Visual Studio 2022, configure separate build directories with
`-G "Visual Studio 17 2022" -A x64` and `-A Win32`. ARM64 and ARM64EC builds
need the corresponding compiler components; compilation on an x64 runner is
not evidence that those executables run correctly on ARM hardware.

For GCC or Clang on Linux, AddressSanitizer and UndefinedBehaviorSanitizer can
be enabled with a separate Debug build:

```sh
cmake -S Sandboxie/core/dll/tests -B build/volume-tests-sanitized \
  -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_C_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer"
cmake --build build/volume-tests-sanitized
ctest --test-dir build/volume-tests-sanitized --output-on-failure
```

The eight CTest cases cover distinct volumes with equal original serials;
native failure outputs, last-error preservation, and optional output pointers;
failed/null/oversized name resolution and legacy serial parsing; forced hash
collisions between different-length string keys; a changed original media
serial and handle reuse; and eight threads performing 48,000 cold-cache reads.
Missing TLS uses the unresolved-name fallback without dereferencing a null
context. Allocator fixtures cover node and bucket allocation failures, cleanup,
retry, and the documented loss of random-fallback stability when storage fails.
The checks remain enabled in Release builds.

To reproduce a regression against another revision, pass its `kernel.c` to
`generate_identity_fixture.py OUTPUT --kernel PATH` and compile the fixture
against the generated include files. The generator deliberately reads the
production initialization instead of supplying a separate model of the cache.

## Scope and remaining integration checks

`HideDiskSerialNumber` still controls the existing by-handle hook. No driver,
service protocol, certificate policy, or other identity category is changed.
`DiskSerialNumber` selectors use the native device component, such as
`HarddiskVolume1`, without the `\Device\` prefix. Existing parser behavior is
preserved; this change does not introduce a stricter setting format.

The cache key combines that component and the original volume serial. This
separates resolvable native volumes with equal serials and avoids reusing an
entry when the original serial changes at the same device name. It is not a
physical-device identity or a universal storage-topology key. Unresolved names
still fall back to the original serial as the distinguishing input; network
redirectors and replacement media with the same device name and serial are not
uniquely identified. Cache allocation failures do not provide a persistence
guarantee. Random fallback values remain process-local, not persistent profiles.

These fixtures do not validate actual hooks, the Sandboxie allocator, Windows
API buffer behavior, or differences between UTF-16 Windows and Linux `wchar_t`.
Before treating this as runtime-validated, build the real SbieDll projects and
check covered/excluded processes in two disposable sandboxes, repeated queries
and process restarts, unchanged results outside the boxes, file and root handles,
Unicode paths, hot-plug media, failures, and small or null output buffers.
Compare `GetVolumeInformationA`, `GetVolumeInformationW`, the by-handle query,
and relevant native/storage/WMI queries independently. This patch does not add
identity substitution to the other paths, change reported capacity, or hide a
physical storage-device serial.

## Read-only Windows probe

`volume_identity_probe` is a separate executable built only on Windows. It calls
real APIs rather than the fixture mocks: `GetVolumeInformationByHandleW`,
`GetVolumeInformationW`, `GetVolumeInformationA`,
`NtQueryVolumeInformationFile(FileFsVolumeInformation)`, and
`GetFileInformationByHandle`. It opens an existing path for attributes, repeats
each query 32 times, and checks duplicated and reopened handles. It does not
install or load Sandboxie, change configuration, write files, or query physical
storage serials. It is deliberately not an automatic CTest target.

From its build directory, run a host smoke check against the current directory:

```powershell
.\Release\volume_identity_probe.exe --path . --require-coherent
```

For a disposable box already configured with a synthetic `DiskSerialNumber`,
launch the same probe through the normal Sandboxie launcher:

```text
volume_identity_probe.exe --path . --require-sandbox --expect-by-handle 1234-ABCD
```

`--require-sandbox` rejects an absent `SbieDll.dll`; a loaded module alone is not
proof that this hook is active or that the intended box was selected.
`--expect-by-handle` requires the observed value to match the supplied test value.
No supplied or observed serial, path, volume label, device name, or identifier
hash is printed. Output is JSON containing booleans, availability and numeric
error codes. Treat reports from sensitive environments as diagnostic data even
though identifiers are suppressed. Use synthetic expected values only.

A `null` comparison means unavailable or failed, not equality. By default,
`requestedChecksPassed` covers the by-handle stability/handle checks and any
explicit expected value; it does not mean all mechanisms are protected.
`--require-coherent` additionally requires all five mechanisms to succeed, remain
stable, and agree. A/W or native divergence in a protected box is reported, not
silently hidden. Unrepresentable ANSI paths and native responses exceeding the
fixed 4096-byte buffer are reported as unavailable/failed.

Exit codes are 0 for satisfied requested checks, 1 for a failed requested check,
and 2 for invalid input, preparation failure, or a missing required sandbox
module. The probe has no persistent comparison store: run it in two boxes with
different synthetic expected values, repeat in fresh processes and after
restarts, and compare host baselines separately. A host smoke check is not a
sandbox runtime result. Keep real identifiers private when collecting any
additional local evidence for host noninterference.

API contracts: [by-handle query](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getvolumeinformationbyhandlew),
[native query](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-ntqueryvolumeinformationfile),
[native volume structure](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddk/ns-ntddk-_file_fs_volume_information),
and [file information](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfileinformationbyhandle).
