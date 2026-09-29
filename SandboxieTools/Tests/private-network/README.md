# Private network classification tests

Run `python SandboxieTools/Tests/private-network/run_tests.py` with a GCC-compatible
C compiler on PATH, or pass `--cc /path/to/clang`. Only the Python standard library
is required. The runner extracts the production WFP and Winsock classifiers,
compiles a small fixture with address/undefined-behavior sanitizers, and checks
private-range boundaries, mapped IPv4, public/loopback addresses, invalid lengths,
and null input. `--emit-only path.c` generates the fixture without compiling it.

This does not exercise kernel filtering, live sockets, or asynchronous receives.
The fallback is not a replacement for WFP enforcement; asynchronous Winsock
completion is outside its receive-side checks. Driver and DLL changes still need
Windows runtime qualification before deployment.
