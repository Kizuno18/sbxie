# Program-control regressions

Run from the repository root on Linux with Python 3 and a C compiler:

```sh
python3 SandboxieTools/Tests/program-control/run_tests.py
```

The fixture includes the production rule header and extracts the document
request parser from the service. It uses 16-bit `WCHAR` and address/undefined
behavior sanitizers. `--no-sanitize` is available for hosts without sanitizer
libraries; CI runs with sanitizers enabled.

Coverage includes extension parsing, recursion limits, path boundaries,
priority ordering, separate process/document policy contexts, old and new wire
requests, malformed offsets, wildcard equivalence, and repeated-wildcard input.

These checks do not exercise the Windows driver, process tokens, file
associations, or installed sandbox lifecycle. Before deploying a build, test
sandbox start/stop, child creation, file recovery, and Force/Breakout routing
with extensions both disabled and enabled on an isolated Windows system.
