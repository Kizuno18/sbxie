# Shared access editor tests

With CMake, a C++17 compiler, and Qt 6 Widgets installed:

```sh
cmake -S SandboxiePlus/tests/shared-access -B build/shared-access
cmake --build build/shared-access
ctest --test-dir build/shared-access --output-on-failure
```

The fixture builds the production widget with an in-memory INI backend, replacing
only the Windows precompiled header and backend include. It verifies raw group
identifiers, negation, disabled entries, template ownership, pending edits, and
save-failure propagation. It does not exercise service authorization or the full
options dialog/wizard lifecycle.
