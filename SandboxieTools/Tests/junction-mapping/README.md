# Junction mapping tests

Run `python SandboxieTools/Tests/junction-mapping/run_tests.py` with GCC available
as `cc`. The test extracts the production prefix and mapping functions, compiles
them with Windows-width wide characters and address/undefined-behavior sanitizers,
and checks boundaries, case folding, longest-prefix selection, drive roots,
reverse mapping, buffer sizing, raw-access opt-in, and allocation failure.
Use `--emit-only path.c` to generate the fixture without compiling it.

The allocator is stubbed. Configuration loading, TLS allocation lifetime, live
file operations, and driver enforcement still require Windows runtime testing.
