import argparse
import ipaddress
import os
from pathlib import Path
import random
import re
import subprocess
import tempfile


def function_source(path, signature):
    source = path.read_text(encoding="utf-8")
    matches = re.findall(r"^" + re.escape(signature) + r"\n\{.*?^\}", source, re.M | re.S)
    if len(matches) != 1:
        raise RuntimeError(f"Expected one definition of {signature}")
    return matches[0]


def build_fixture(root):
    networks = [ipaddress.ip_network(value) for value in (
        "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16",
        "fc00::/7", "fe80::/10",
    )]
    addresses = [ipaddress.ip_address(value) for value in (
        "0.0.0.0", "127.0.0.1", "127.255.255.255", "8.8.8.8",
        "255.255.255.255", "::", "::1", "2001:4860:4860::8888",
        "ff02::1", "::ffff:127.0.0.1", "::ffff:192.168.1.1",
    )]
    for network in networks:
        constructor = ipaddress.IPv4Address if network.version == 4 else ipaddress.IPv6Address
        for value in (int(network.network_address) - 1, int(network.network_address),
                      int(network.network_address) + 1, int(network.broadcast_address) - 1,
                      int(network.broadcast_address), int(network.broadcast_address) + 1):
            addresses.append(constructor(value))
    rng = random.Random(5262)
    for _ in range(256):
        addresses.extend((ipaddress.IPv4Address(rng.getrandbits(32)),
                          ipaddress.IPv6Address(rng.getrandbits(128))))
    vectors = []
    for address in addresses:
        mapped = getattr(address, "ipv4_mapped", None)
        logical = mapped or address
        expected = int(any(logical.version == network.version and logical in network
                           for network in networks))
        packed = address.packed if address.version == 6 else b"\0" * 10 + b"\xff\xff" + address.packed
        vectors.append("{{%s}, %d, %d}" % (",".join(map(str, packed)), address.version, expected))

    prefix = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define _FX
#define TRUE 1
#define FALSE 0
#define AF_INET 2
#define AF_INET6 23
typedef uint8_t BOOLEAN;
typedef uint8_t BYTE;
typedef uint32_t ULONG;
typedef uint32_t UINT32;
typedef union { BYTE Data[16]; UINT32 Data32[4]; } IP_ADDRESS;
typedef struct {
    short family; uint16_t port;
    struct { union { UINT32 S_addr; } S_un; } sin_addr;
    BYTE padding[8];
} SOCKADDR_IN;
typedef struct {
    short family; uint16_t port; UINT32 flow;
    struct { union { BYTE Byte[16]; } u; } sin6_addr;
    UINT32 scope;
} SOCKADDR_IN6_LH;
"""
    definitions = [
        function_source(root / "Sandboxie/core/dll/net.c",
                        "_FX BOOLEAN WSA_GetIP(const short* addr, int addrlen, IP_ADDRESS* pIP)"),
        function_source(root / "Sandboxie/core/dll/net.c",
                        "_FX BOOLEAN WSA_IsPrivateNet(const short *addr, int addrlen)"),
        function_source(root / "Sandboxie/core/drv/wfp.c",
                        "BOOLEAN WFP_isPrivateNet(const IP_ADDRESS* ip)"),
    ]
    main = r"""
int main(void) {
    unsigned checks = 0;
    for (unsigned i = 0; i < sizeof(vectors) / sizeof(vectors[0]); ++i) {
        IP_ADDRESS ip;
        SOCKADDR_IN v4 = {0};
        SOCKADDR_IN6_LH v6 = {0};
        memcpy(ip.Data, vectors[i].bytes, 16);
        v4.family = AF_INET;
        memcpy(&v4.sin_addr.S_un.S_addr, ip.Data + 12, 4);
        v6.family = AF_INET6;
        memcpy(v6.sin6_addr.u.Byte, ip.Data, 16);
        if (WFP_isPrivateNet(&ip) != vectors[i].expected) return 1;
        if (WSA_IsPrivateNet((const short*)&v6, sizeof(v6)) != vectors[i].expected) return 2;
        checks += 2;
        if (vectors[i].version == 4) {
            if (WSA_IsPrivateNet((const short*)&v4, sizeof(v4)) != vectors[i].expected) return 3;
            ++checks;
        }
        for (int length = -1; length < (int)sizeof(v6); ++length) {
            if (WSA_IsPrivateNet((const short*)&v6, length)) return 4;
            ++checks;
        }
        for (int length = -1; length < (int)sizeof(v4); ++length) {
            if (WSA_IsPrivateNet((const short*)&v4, length)) return 5;
            ++checks;
        }
    }
    if (WSA_IsPrivateNet(NULL, 28)) return 6;
    short unknown[16] = {99};
    if (WSA_IsPrivateNet(unknown, sizeof(unknown))) return 7;
    printf("Passed %u production classifier checks\n", checks + 2);
    return 0;
}
"""
    return prefix + "\n".join(definitions) + "\nstatic const struct { BYTE bytes[16]; int version; int expected; } vectors[] = {\n" + ",\n".join(vectors) + "\n};\n" + main


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cc", default=os.environ.get("CC", "cc"))
    parser.add_argument("--emit-only", type=Path)
    args = parser.parse_args()
    fixture = build_fixture(Path(__file__).resolve().parents[3])
    if args.emit_only:
        args.emit_only.write_text(fixture, encoding="utf-8")
        print(f"Generated {args.emit_only}")
        return
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "private_network_test.c"
        binary = Path(directory) / "private_network_test"
        source.write_text(fixture, encoding="utf-8")
        subprocess.run([args.cc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                        "-Wno-sign-compare", "-fsanitize=address,undefined", "-g",
                        str(source), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
