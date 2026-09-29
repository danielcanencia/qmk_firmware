#!/usr/bin/env python3
"""
hexcore_iap.py - talk to the Hexcore/Obins "DISCOVERY" IAP bootloader over USB HID.

Developed for the Hexcore ANNE PRO 2D (USB 0311:a298 normal, 0311:a293 in IAP mode).
The bootloader itself identifies as "ANNEPRO 2 DISCOVERY IAP", the same bootloader
family used by the Anne Pro 2, so the wire protocol implemented here was taken from
OpenAnnePro/AnnePro2-Tools (Rust, GPL-3.0) and re-implemented dependency-free on top
of Linux hidraw.

Wire format (64-byte output report, report id 0):

    7b 10 (target << 4 | 01) 10 len 00 00 7d <payload...>   zero padded to 64

Payloads for firmware (L2) commands start with 0x02 (L2Command::FW) followed by a
key command byte:

    0x02  IapMode          (boot the target)
    0x02  IapGetMode       (read only)
    0x03  IapGetFwVersion  (read only)
    0x31  IapWriteMemory   [addr:u32le][data]
    0x32  IapWriteApFlag   [flag:u8]
    0x43  IapEraseMemory   [addr:u32le]

Targets: 1=UsbHost 2=BleHost 3=McuMain 4=McuLed 5=McuBle

Subcommands:

    info    read-only queries (bootloader mode / firmware versions)
    flash   erase + write + boot  ** DESTROYS the keyboard's firmware **

To enter IAP mode: turn the wireless switch off, unplug USB, hold Esc, plug USB back
in, and release Esc once a device containing "IAP" appears.
"""

import argparse
import ctypes
import os
import select
import struct
import sys
import time

# ---------------------------------------------------------------- constants ---

HID_GET_REPORT = 0x80044801   # _IOR('H', 0x01, struct hidraw_report_descriptor)
HID_SET_REPORT = 0x40044802   # _IOW('H', 0x02, struct hidraw_report_descriptor)

HEXCORE_VID = 0x0311
IAP_PID = 0xA293

TARGETS = {"usb": 1, "ble": 2, "main": 3, "led": 4, "blemcu": 5}
L2_FW = 0x02

CMD_IAP_MODE = 0x02
CMD_GET_MODE = 0x02
CMD_GET_FW_VERSION = 0x03
CMD_WRITE_MEMORY = 0x31
CMD_WRITE_AP_FLAG = 0x32
CMD_ERASE_MEMORY = 0x43

CHUNK_SIZE = {3: 48, 4: 48, 5: 32}   # payload bytes per chunk, per target
DEFAULT_BASE = 0x4000                # Obins bootloaders occupy the first 16 KiB

LIBC = ctypes.CDLL("libc.so.6", use_errno=True)


# ------------------------------------------------------------------- hid io ---

def _ioctl(fd, request, buf, length):
    if LIBC.ioctl(fd, request, buf, length) < 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))


def find_iap_hidraw():
    """Return (path, product_name) of the IAP device, or (None, None)."""
    try:
        nodes = sorted(os.listdir("/sys/class/hidraw"))
    except FileNotFoundError:
        return None, None
    for node in nodes:
        uevent = f"/sys/class/hidraw/{node}/device/uevent"
        try:
            with open(uevent) as fh:
                name = next((l.split("=", 1)[1].strip() for l in fh
                             if l.startswith("HID_NAME=")), "")
        except OSError:
            continue
        if "IAP" in name.upper():
            return f"/dev/{node}", name
    return None, None


def wait_for_iap(seconds=300):
    print("Waiting for IAP device (hold ESC and replug the USB cable)...")
    for remaining in range(seconds, 0, -5):
        path, name = find_iap_hidraw()
        if path:
            return path, name
        mins, secs = divmod(remaining, 60)
        print(f"  still waiting... {mins}:{secs:02d} left", end="\r", flush=True)
        time.sleep(5)
    return None, None


def build_frame(target, payload):
    frame = bytearray([0x7B, 0x10, ((target & 0xF) << 4) | 0x01, 0x10,
                       len(payload), 0x00, 0x00, 0x7D])
    frame.extend(payload)
    if len(frame) > 64:
        raise ValueError(f"frame too long ({len(frame)} > 64)")
    frame.extend(b"\x00" * (64 - len(frame)))
    return bytes(frame)


class IapDevice:
    def __init__(self, path, timeout_ms=800):
        self.path = path
        self.fd = os.open(path, os.O_RDWR)
        self.timeout = timeout_ms / 1000
        print(f"Opened {path}")

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def command(self, target, payload, raw=False, report=True):
        """Send one command; return the 64-byte reply (or None)."""
        frame = payload if raw else build_frame(target, payload)
        buf = bytearray(65)
        buf[0] = 65
        buf[1] = 0                      # report id: the device declares none
        buf[2:66] = frame
        _ioctl(self.fd, HID_SET_REPORT, buf, 65)

        if not report:
            return None

        ready, _, _ = select.select([self.fd], [], [], self.timeout)
        if not ready:
            return None
        inbuf = bytearray(65)
        inbuf[0] = 65
        inbuf[1] = 0
        _ioctl(self.fd, HID_GET_REPORT, inbuf, 65)
        return bytes(inbuf[2:66])


# ------------------------------------------------------------------ helpers ---

def fmt(reply, limit=24):
    if reply is None:
        return "<no reply>"
    body = " ".join(f"{b:02x}" for b in reply[:limit])
    return body + (" ..." if len(reply) > limit else "")


def resolve_device(args):
    if args.device:
        return args.device, None
    path, name = find_iap_hidraw()
    if path:
        return path, name
    if args.wait:
        path, name = wait_for_iap(args.wait)
        if path:
            return path, name
    sys.exit("No IAP device found. Enter IAP mode (hold ESC while replugging USB) "
             "or pass --device /dev/hidrawN, or use --wait.")


# ---------------------------------------------------------------- commands ---

def cmd_info(args, dev):
    print(f"\nUSB: {HEXCORE_VID:04x}:{IAP_PID:04x}  report=64B\n")
    print("Read-only queries (no writes are issued):\n")
    for tname in ("main", "ble", "led", "usb"):
        target = TARGETS[tname]
        for keycmd, kname in ((CMD_GET_MODE, "IapGetMode"),
                              (CMD_GET_FW_VERSION, "IapGetFwVersion")):
            reply = dev.command(target, bytes([L2_FW, keycmd]))
            print(f"  [{tname:4s}] {kname:16s} -> {fmt(reply)}")
    print("\nVersion bytes are little-endian; the first two bytes of an "
          "IapGetFwVersion reply are usually the firmware version (major.minor).")


def cmd_flash(args, dev):
    target = TARGETS[args.target]
    chunk_size = CHUNK_SIZE.get(target, 48)
    with open(args.file, "rb") as fh:
        image = fh.read()
    if not image:
        sys.exit(f"{args.file} is empty")
    base = args.base

    print(f"Target      : {args.target} (id {target})")
    print(f"Image       : {args.file} ({len(image)} bytes, "
          f"{len(image) / chunk_size:.0f} chunks of {chunk_size} B)")
    print(f"Base address: 0x{base:08x} -> ends at 0x{base + len(image):08x}")

    if args.dry_run:
        print("\nDry run: would erase the main MCU firmware from 0x"
              f"{base:08x} and write the image above, then boot.")
        print("Re-run without --dry-run (and with --yes) to actually flash.")
        return

    if not args.yes:
        sys.exit("Refusing to erase the keyboard's firmware without --yes.")

    print("\nErasing...")
    if dev.command(target, bytes([L2_FW, CMD_ERASE_MEMORY]) +
                   struct.pack("<I", base)) is None:
        print("Warning: no reply to erase command; continuing.")

    addr = base
    written = 0
    errors = 0
    while written < len(image):
        chunk = image[written:written + chunk_size]
        payload = (bytes([L2_FW, CMD_WRITE_MEMORY]) + struct.pack("<I", addr) + chunk)
        if dev.command(target, payload) is None:
            errors += 1
            print(f"  [warn] no ack writing 0x{addr:08x}")
        addr += len(chunk)
        written += len(chunk)
        pct = 100 * written / len(image)
        print(f"\r  writing... {pct:5.1f}% (0x{addr:08x})", end="", flush=True)
    print()

    if errors:
        print(f"{errors} chunk(s) got no acknowledgement - do NOT reboot, retry the flash.")

    print("Writing AP flag (2)...")
    dev.command(target, bytes([L2_FW, CMD_WRITE_AP_FLAG, 0x02]))

    print("Booting the keyboard...")
    # Boot frame is sent unpadded, straight into the bootloader.
    dev.command(target, bytes([0x7B, 0x10, ((target & 0xF) << 4) | 0x01, 0x10,
                               0x03, 0x00, 0x00, 0x7D, L2_FW, CMD_IAP_MODE, 0x02]),
                raw=False, report=False)
    print("Done. Unplug and replug the keyboard.")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_info = sub.add_parser("info", help="read-only bootloader/firmware queries")
    p_info.set_defaults(func=cmd_info)

    p_flash = sub.add_parser("flash", help="erase and write firmware (DESTRUCTIVE)")
    p_flash.add_argument("file", help="firmware binary to write")
    p_flash.add_argument("-t", "--target", choices=TARGETS, default="main")
    p_flash.add_argument("-b", "--base", type=lambda s: int(s, 0), default=DEFAULT_BASE,
                         help="flash offset of the image (default 0x4000)")
    p_flash.add_argument("--dry-run", action="store_true",
                         help="print the plan without touching the device")
    p_flash.add_argument("--yes", action="store_true",
                         help="confirm that you really want to erase the firmware")
    p_flash.set_defaults(func=cmd_flash)

    for p in (p_info, p_flash):
        p.add_argument("-d", "--device", help="hidraw node, e.g. /dev/hidraw0")
        p.add_argument("--wait", nargs="?", type=int, const=300, default=0,
                       metavar="SECONDS",
                       help="wait for IAP mode to be entered (default 300s)")

    args = parser.parse_args()
    path, name = resolve_device(args)
    if name:
        print(f"IAP device: {name}")
    with IapDevice(path) as dev:
        args.func(args, dev)


if __name__ == "__main__":
    main()
