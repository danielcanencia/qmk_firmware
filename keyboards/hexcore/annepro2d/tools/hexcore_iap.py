#!/usr/bin/env python3
"""
hexcore_iap.py - talk to the Hexcore/Obins "DISCOVERY" IAP bootloader over USB HID.

Developed for the Hexcore ANNE PRO 2D (USB 0311:a298 normal, 0311:a293 in IAP mode).
The bootloader itself identifies as "ANNEPRO 2 DISCOVERY IAP", the same bootloader
family used by the Anne Pro 2, so the wire protocol implemented here was taken from
OpenAnnePro/AnnePro2-Tools (Rust, GPL-3.0) and re-implemented dependency-free on top
of Linux hidraw.

Wire format, a 64-byte output report:

    7b 10 (target << 4 | 01) 10 len 00 00 7d <payload...>   zero padded to 64

The 0x7B opener matters beyond being a magic number: usbhid_output_report()
strips a leading zero byte, so a frame that started with 0x00 would silently
lose its first byte on the way to the keyboard.

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

    info        read-only queries (bootloader mode / firmware versions)
    descriptor  read-only: dump the HID report descriptor
    flash       erase + write + boot  ** DESTROYS the keyboard's firmware **

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

def _ioc(direction, typ, nr, size):
    """Encode an ioctl request number the way <asm-generic/ioctl.h> does."""
    return (direction << 30) | (size << 16) | (typ << 8) | nr


_IOC_NONE, _IOC_WRITE, _IOC_READ = 0, 1, 2
_IOC_RW = _IOC_WRITE | _IOC_READ
_HIDRAW = ord("H")

# The hidraw ioctls, from <linux/hidraw.h>. Note these are *not* the legacy HID
# ioctls of the same-looking 0x01/0x02 numbers, which are GRDESCSIZE and GRDESC.
# A hidraw report buffer starts with the report number; the 4-byte size prefix
# belongs to struct hidraw_report_descriptor ioctls only.
HIDIOCGRDESCSIZE = _ioc(_IOC_READ, _HIDRAW, 0x01, 4)
HIDIOCGRDESC = _ioc(_IOC_READ, _HIDRAW, 0x02, 4 + 4096)   # sizeof(struct hidraw_report_descriptor)
HIDIOCGINPUT = _ioc(_IOC_RW, _HIDRAW, 0x0A, 0)           # patched with the report length below
HIDIOCSOUTPUT = _ioc(_IOC_RW, _HIDRAW, 0x0B, 0)

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
# Without argtypes, ctypes refuses to convert a bytearray and the call raises
# ArgumentError instead of ever reaching the kernel. POINTER(c_ubyte) accepts a
# bytearray (and any ctypes array) directly; c_void_p does not.
LIBC.ioctl.argtypes = [ctypes.c_int, ctypes.c_ulong,
                       ctypes.POINTER(ctypes.c_ubyte), ctypes.c_ulong]
LIBC.ioctl.restype = ctypes.c_int


# ------------------------------------------------------------------- hid io ---

def _ioctl(fd, request, buf, length):
    """Run one ioctl on `buf`, in place if it is a writable bytearray.

    Returns the array the kernel wrote into, so that read-back ioctls can be
    read even when the caller passed immutable bytes.
    """
    if isinstance(buf, (bytes, bytearray)):
        n = max(1, len(buf))
        arr = ((ctypes.c_ubyte * n).from_buffer(buf) if isinstance(buf, bytearray)
               else (ctypes.c_ubyte * n).from_buffer_copy(buf))
    else:
        arr = buf
    rc = LIBC.ioctl(ctypes.c_int(fd), ctypes.c_ulong(request), arr, ctypes.c_ulong(length))
    if rc < 0:
        err = ctypes.get_errno()
        raise OSError(err, f"ioctl 0x{request:08x} failed: {os.strerror(err)}")
    return arr


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


FRAME_MAGIC = 0x7B
FRAME_SIZE = 64


def build_frame(target, payload):
    frame = bytearray([FRAME_MAGIC, 0x10, ((target & 0xF) << 4) | 0x01, 0x10,
                       len(payload), 0x00, 0x00, 0x7D])
    frame.extend(payload)
    if len(frame) > FRAME_SIZE:
        raise ValueError(f"frame too long ({len(frame)} > {FRAME_SIZE})")
    frame.extend(b"\x00" * (FRAME_SIZE - len(frame)))
    return bytes(frame)


class IapDevice:
    def __init__(self, path, timeout_ms=800):
        self.path = path
        self.fd = os.open(path, os.O_RDWR)
        self.timeout = timeout_ms / 1000
        self.last_raw = None
        print(f"Opened {path}")

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def descriptor(self):
        """Return the raw HID report descriptor as bytes, or None."""
        try:
            size = bytearray(4)
            _ioctl(self.fd, HIDIOCGRDESCSIZE, size, 4)
            n = int.from_bytes(size, "little")
            if not 0 < n <= 4096:
                return None
            # The kernel reads struct hidraw_report_descriptor.size as the number
            # of bytes to fetch, then overwrites it with the length it got, so it
            # has to be seeded first or the request comes back empty.
            buf = bytearray(4 + 4096)
            buf[:4] = n.to_bytes(4, "little")
            _ioctl(self.fd, HIDIOCGRDESC, buf, 4 + 4096)
        except OSError as exc:
            print(f"  (report descriptor unavailable: {exc})")
            return None
        n = int.from_bytes(buf[:4], "little")
        return bytes(buf[4:4 + n]) if 0 < n <= 4096 else None

    @staticmethod
    def _strip_report_id(data):
        """hidraw returns input reports with a leading report-number byte when
        the device uses report IDs, and without one when it does not. The frame
        starts with a 0x7B magic byte, so use it to tell the two apart rather
        than assuming."""
        if not data:
            return None
        if data[0] == FRAME_MAGIC:
            return data
        if data[0] == 0x00 and len(data) > 1 and data[1] == FRAME_MAGIC:
            return data[1:]
        return data

    def command(self, target, payload, raw=False, report=True):
        """Send one command; return the reply bytes (or None if silent).

        The transfer goes through read()/write() rather than
        HIDIOCSOUTPUT/HIDIOCGINPUT. Two details of that path matter:

        * hidraw treats the first byte of a written buffer as the report number
          (hidraw_send_report in drivers/hid/hidraw.c), but for a device whose
          report enum is not "numbered" that byte is data, not a header.
        * usbhid_output_report() drops a leading 0x00 byte outright, reading it
          as a report ID that a non-numbered device has no use for.

        A frame starting with the 0x7B magic byte therefore reaches the device
        as exactly the 64 bytes built here, and the 0x7B is also what tells us
        whether a reply came back with a report number in front of it. Run
        `descriptor` to see which convention the device declares.
        """
        frame = payload if raw else build_frame(target, payload)
        assert frame[0] == FRAME_MAGIC, "a leading zero byte would be dropped by usbhid"
        os.write(self.fd, frame)

        if not report:
            return None

        deadline = time.monotonic() + self.timeout
        reply = None
        while time.monotonic() < deadline:
            ready, _, _ = select.select([self.fd], [], [],
                                        max(0.0, deadline - time.monotonic()))
            if not ready:
                break
            data = os.read(self.fd, FRAME_SIZE + 8)
            if not data:
                break
            self.last_raw = data
            reply = self._strip_report_id(data)
            if reply and reply[0] == FRAME_MAGIC:
                break
        return reply


# ------------------------------------------------------------------ helpers ---

def fmt(reply, limit=24):
    if reply is None:
        return "<no reply>"
    body = " ".join(f"{b:02x}" for b in reply[:limit])
    return body + (" ..." if len(reply) > limit else "")


# An HID item is one prefix byte followed by bSize data bytes, where the prefix
# packs bSize in bits 0-1, bType in bits 2-3 and bTag in bits 4-7 (HID 1.11
# 6.2.2). Keying on (bType << 4) | bTag keeps main-type and global-type items
# from colliding.
_MAIN = 0x00
_GLOBAL = 0x10
_REPORT_TYPES = {_MAIN | 0x08: "Input", _MAIN | 0x09: "Output", _MAIN | 0x0B: "Feature"}
_REPORT_ID = _GLOBAL | 0x08
_REPORT_COUNT = _GLOBAL | 0x09
_REPORT_SIZE = _GLOBAL | 0x07


def parse_descriptor(desc):
    """Walk a HID report descriptor and report the report sizes and ID usage."""
    lines = []
    i = 0
    report_id = None
    count = size = 0
    totals = {}
    seen_ids = set()

    while i < len(desc):
        prefix = desc[i]
        bsize, btype, btag = prefix & 0x03, (prefix >> 2) & 0x03, (prefix >> 4) & 0x0F
        i += 1
        if bsize == 3:                       # 3 encodes a 4-byte data field
            bsize = 4
        if i + bsize > len(desc):
            break
        val = int.from_bytes(desc[i:i + bsize], "little") if bsize <= 4 else 0
        i += bsize
        key = (btype << 4) | btag

        if key == _REPORT_ID:
            report_id = val
            seen_ids.add(val)
        elif key == _REPORT_COUNT:
            count = val
        elif key == _REPORT_SIZE:
            size = val
        elif key in _REPORT_TYPES:
            slot = totals.setdefault((_REPORT_TYPES[key], report_id), [0, 0])
            slot[0] = max(slot[0], count)
            slot[1] = max(slot[1], size)

    for (name, rid), (cnt, sz) in sorted(totals.items(),
                                         key=lambda kv: (kv[0][1] is None, kv[0][1] or 0, kv[0][0])):
        label = f"{name} report"
        if rid is not None:
            label += f", id {rid}"
        nbytes = max(0, cnt * sz) // 8
        lines.append(f"{label}: {cnt} x {sz} bit = {nbytes} byte(s)"
                     + ("" if rid is not None else " (no report id byte)"))
    if not totals:
        lines.append("(no report type items found)")
    lines.append("Report IDs used: " + (", ".join(str(v) for v in sorted(seen_ids))
                                        if seen_ids else "no"))
    return lines


def describe_frame(reply):
    """Decode the fixed part of a reply frame, if it looks like one."""
    if reply is None or len(reply) < 8 or reply[0] != FRAME_MAGIC:
        return None
    target = (reply[2] >> 4) & 0xF
    length = reply[4]
    return f"target={target} len={length} trailer={reply[7]:02x}"


def print_descriptor(dev):
    """Dump the HID report descriptor. Read-only; tells us the report size and
    whether the device uses report IDs, which is what the transfer code has to
    agree with."""
    desc = dev.descriptor()
    if desc is None:
        return
    print(f"  report descriptor: {len(desc)} bytes")
    for line in parse_descriptor(desc):
        print(f"    {line}")


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
    print(f"\nUSB: {HEXCORE_VID:04x}:{IAP_PID:04x}  frame=64B\n")
    print_descriptor(dev)

    print("\nRead-only queries (no writes are issued):\n")
    for tname in ("main", "ble", "led", "usb"):
        target = TARGETS[tname]
        for keycmd, kname in ((CMD_GET_MODE, "IapGetMode"),
                              (CMD_GET_FW_VERSION, "IapGetFwVersion")):
            reply = dev.command(target, bytes([L2_FW, keycmd]))
            decoded = describe_frame(reply)
            line = f"  [{tname:4s}] {kname:16s} -> {fmt(reply)}"
            if decoded:
                line += f"   ({decoded})"
            print(line)

    if dev.last_raw is not None:
        print(f"\n  last raw report as read(): {len(dev.last_raw)} bytes, "
              f"first byte 0x{dev.last_raw[0]:02x}")
    print("\nVersion bytes are little-endian; the first two bytes of an "
          "IapGetFwVersion reply are usually the firmware version (major.minor).")


def cmd_descriptor(args, dev):
    """Read-only: report what the HID interface actually looks like."""
    print(f"\nUSB: {HEXCORE_VID:04x}:{IAP_PID:04x}\n")
    print_descriptor(dev)


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
    # build_frame already emits the 7b 10 .. 7d envelope, so wrapping the whole
    # frame again would produce a double header. The bootloader does not answer
    # this one; it just resets into the application.
    dev.command(target, bytes([L2_FW, CMD_IAP_MODE, 0x02]), report=False)
    print("Done. Unplug and replug the keyboard.")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_info = sub.add_parser("info", help="read-only bootloader/firmware queries")
    p_info.set_defaults(func=cmd_info)

    p_desc = sub.add_parser("descriptor", help="read-only: dump the HID report descriptor")
    p_desc.set_defaults(func=cmd_descriptor)

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

    for p in (p_info, p_desc, p_flash):
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
