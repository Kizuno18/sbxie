# SPDX-License-Identifier: GPL-3.0-or-later
"""Extract production code for a mocked test, not a Windows runtime test."""
import argparse
import re
from pathlib import Path


def function(source: str, signature: str) -> str:
    match = re.search(r"^" + re.escape(signature) + r".*?^}", source, re.M | re.S)
    if not match:
        raise ValueError(f"Production function not found: {signature}")
    return match.group(0)


parser = argparse.ArgumentParser()
parser.add_argument("output", type=Path)
parser.add_argument("--kernel", type=Path)
args = parser.parse_args()
dll = Path(__file__).resolve().parent.parent
custom = (dll / "custom.c").read_text(encoding="utf-8-sig")
kernel = (args.kernel or dll / "kernel.c").read_text(encoding="utf-8-sig")
args.output.mkdir(parents=True, exist_ok=True)
(args.output / "kernel_identity_under_test.inc").write_text("\n\n".join([
    function(custom, "int hex_digit_value("),
    function(custom, "BOOL hex_string_to_uint8_array("),
    function(kernel, "_FX BOOL Kernel_GetVolumeInformationByHandleW("),
]) + "\n", encoding="utf-8")
start = kernel.index("InitializeCriticalSection(&Kernel_DiskSN_CritSec);")
end = kernel.index("void* GetVolumeInformationByHandleW", start)
(args.output / "kernel_identity_init.inc").write_text(kernel[start:end], encoding="utf-8")
