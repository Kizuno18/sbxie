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

The six CTest cases cover distinct volumes with equal original serials;
native failure outputs, last-error preservation, and optional output pointers;
failed/null/oversized name resolution and legacy serial parsing; forced hash
collisions between different-length string keys; a changed original media
serial and handle reuse; and eight threads performing 48,000 cold-cache reads.
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
