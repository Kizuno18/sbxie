# Command-line injection tests

Run `python SandboxieTools/Tests/command-line/run_tests.py` on a system with GCC
available as `cc`. The fixture extracts the production injection block and argument
parser, uses 16-bit wide characters, and stubs allocation, configuration, ANSI
conversion, and hook installation. It checks quoting, existing arguments, process
matching, empty flags, length limits, and allocation/conversion failure cleanup.
The generated C source can be inspected using `--emit-only path.c`.

This is not a live process-hook test. Native builds and Windows runtime checks are
still required before deployment.
