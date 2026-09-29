# Portable sandbox INI tests

With CMake, a C++17 compiler, and Qt 6 Core installed:

```sh
cmake -S SandboxiePlus/tests/portable-box -B build/portable-box
cmake --build build/portable-box
ctest --test-dir build/portable-box --output-on-failure
```

The test calls the production INI writer and verifies successful creation,
existing-file preservation, missing-parent failure, and directory preservation.
Wizard import/reload rollback still requires a running Windows Sandboxie service.
