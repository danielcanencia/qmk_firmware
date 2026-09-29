#!/usr/bin/env python3
"""
extract_matrix.py - recover the ANNE PRO 2D key matrix from the stock firmware.

The stock main-MCU firmware is a bare RT-Thread image for the Holtek HT32F52352.
Nothing in it is encrypted (per-4 KiB entropy sits around 6.5 bits/byte, normal
for ARM code with literal pools), so the pin assignments can be read straight out
of the binary without running anything.

Three data structures are needed, all of them at fixed offsets in a firmware
image whose load address is 0x4000:

  1. A 20-byte pin descriptor table.  Record layout is:

         u32 id;        // 1-based pin id used by every other table
         u32 base;      // GPIO base address (0x400B0000/2000/4000/6000)
         u32 mask;      // 1 << bit index within the port
         u32 port;      // 0=A 1=B 2=C 3=D
         u32 flat;      // port * 256 + bit, i.e. a "Pxy" name

  2. The row pin table: MATRIX_ROWS bytes of pin ids, read back as inputs.

  3. The column pin table: MATRIX_COLS bytes of pin ids, driven as outputs.

The pin ids are resolved to "Pxy" names through the descriptor table, which
self-validates: every record's `flat` field must equal port * 256 + bit.

Usage:
    extract_matrix.py <KEY_APP.bin> [--base 0x4000]
"""

import argparse
import struct
import sys

# Offsets below are absolute flash addresses for the v3.08 stock image
# (annepro2_discovery_KEY_APP.bin, 64116 bytes, sha256 recorded in readme.md).
PIN_TABLE = 0x05BC0      # 20-byte pin descriptor records, indexed by id - 1
ROW_TABLE = 0x13904      # MATRIX_ROWS pin ids
COL_TABLE = 0x1390C      # MATRIX_COLS pin ids

GPIO_BASE = {0x400B0000: "A", 0x400B2000: "B", 0x400B4000: "C", 0x400B6000: "D"}


def load_pin_table(blob, base):
    """Return {pin id: "Pxy"} from the descriptor table."""
    pins, anomalies = {}, []
    off = PIN_TABLE - base
    while off + 20 <= len(blob):
        pid, base, mask, port, flat = struct.unpack_from("<IIIII", blob, off)
        letter = GPIO_BASE.get(base)
        if letter is None or pid == 255 or pid == 0:
            off += 20
            if pid == 0 and off > PIN_TABLE + 20 * 256:
                break
            continue
        if mask == 0 or (mask & (mask - 1)):
            anomalies.append((pid, "mask is not a single bit: 0x%x" % mask))
            off += 20
            continue
        bit = mask.bit_length() - 1
        if flat != port * 256 + bit:
            anomalies.append((pid, "flat %d != %d*256+%d" % (flat, port, bit)))
        if pid in pins:
            anomalies.append((pid, "duplicate id"))
        pins[pid] = "%s%d" % (letter, bit)
        off += 20
    return pins, anomalies


def read_ids(blob, addr, count, base):
    return list(blob[addr - base:addr - base + count])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("firmware", help="stock KEY_APP .bin from the vendor CDN")
    ap.add_argument("--base", type=lambda s: int(s, 0), default=0x4000,
                    help="load address of the image (default 0x4000)")
    ap.add_argument("--rows", type=int, default=5)
    ap.add_argument("--cols", type=int, default=14)
    args = ap.parse_args()

    with open(args.firmware, "rb") as fh:
        blob = fh.read()

    pins, anomalies = load_pin_table(blob, args.base)
    if anomalies:
        for pid, why in anomalies:
            print("anomaly: pin id %s: %s" % (pid, why), file=sys.stderr)
    print("pin descriptor table: %d pins (ids %d..%d)"
          % (len(pins), min(pins), max(pins)))

    rows = read_ids(blob, ROW_TABLE, args.rows, args.base)
    cols = read_ids(blob, COL_TABLE, args.cols, args.base)

    unknown = [i for i in rows + cols if i not in pins]
    if unknown:
        print("warning: unmapped pin ids %s" % unknown, file=sys.stderr)

    print("\nrows (%d, sampled as inputs):" % args.rows)
    for i, pid in enumerate(rows):
        print("  row %d: id %3d -> %s" % (i, pid, pins.get(pid, "??")))
    print("\ncols (%d, driven as outputs):" % args.cols)
    for i, pid in enumerate(cols):
        print("  col %2d: id %3d -> %s" % (i, pid, pins.get(pid, "??")))

    print('\n"matrix_pins": {')
    print('    "rows": [%s],' % ", ".join('"%s"' % pins.get(p, "??") for p in rows))
    print('    "cols": [%s]' % ", ".join('"%s"' % pins.get(p, "??") for p in cols))
    print("}")


if __name__ == "__main__":
    main()
