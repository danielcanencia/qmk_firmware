# Hexcore ANNE PRO 2D

QMK firmware for the **Hexcore / Obins ANNE PRO 2D** 60% keyboard.

This is a new port. The closely related [Obins Anne Pro 2](../annepro2/README.md)
already has QMK support, but it targets a different USB product (`ac20:8009`) and
a different pinout, so it is used here only as a structural template.

## Hardware

| | |
|---|---|
| Manufacturer | Hexcore / Obins |
| MCU | Holtek **HT32F52352** (Cortex-M0+, 128 KiB flash, 16 KiB SRAM) |
| USB (normal) | `0311:a298`, "HEXCORE AnnePro 2D" |
| USB (bootloader) | `0311:a293`, "ANNEPRO 2 DISCOVERY IAP" |
| Layout | 60% ANSI / ISO, 5 × 14 matrix |
| Stock firmware | RT-Thread based, application linked at `0x4000` |

Not yet supported: the separate LED MCU (per-key RGB) and the Bluetooth MCU.
This port currently covers the key matrix and USB HID only.

## Key matrix

Recovered from the stock firmware — see [`analysis/extract_matrix.py`](analysis/extract_matrix.py).
The stock driver walks the 14 **column** pins as outputs and samples the 5 **row**
pins as inputs, which is a COL2ROW diode arrangement.

```
rows: C2, C1, C15, C14, C3
cols: C4, C5, C8, C0, A10, B1, A8, C13, C12, A15, A14, A11, D1, D2
```

## Keymaps

| Keymap | Description |
|---|---|
| [`default`](keymaps/default/keymap.c) | Plain ANSI QWERTY, unmodified |
| [`colemak_dh_dev`](keymaps/colemak_dh_dev/) | Colemak-DH plus symbol, F-row, and navigation layers, tuned for programming |

## Building

```sh
qmk compile -kb hexcore/annepro2d/rev1 -km default
qmk compile -kb hexcore/annepro2d/rev1 -km colemak_dh_dev
```

## Flashing

The board has no QMK/dfu-util bootloader. Flashing goes through the vendor
`DISCOVERY IAP` HID bootloader with the helper in [`tools/hexcore_iap.py`](tools/hexcore_iap.py).

To enter IAP mode: turn the wireless switch **off**, unplug USB, hold **Esc**,
plug USB back in, and release Esc once a device containing `IAP` appears.

```sh
# read-only: query bootloader state and firmware versions
sudo python3 keyboards/hexcore/annepro2d/tools/hexcore_iap.py info --wait

# read-only: running firmware version, from the USB descriptors.
# Needs no root and no IAP mode - run it with the keyboard in normal mode.
python3 keyboards/hexcore/annepro2d/tools/hexcore_iap.py usb

# preview a flash without touching the device
python3 keyboards/hexcore/annepro2d/tools/hexcore_iap.py flash firmware.bin --dry-run
```

### Reading the firmware version

`usb` is the only command that reports a usable version. `info` does return an
`IapGetFwVersion` payload, but it is a 32-byte blob of a 2-byte header plus
three byte-identical 10-byte records (`00 00 00 40 00 00 00 fe 01 00`) that
the bootloader builds at run time. It holds no version string, so the tool
dumps it rather than guessing at a layout.

The USB device descriptor's `bcdDevice` does carry it, and this port declares
`device_version: 2.0.0`, so a QMK build reports the same `0x0200` the stock
firmware does and enumerates as the same `0311:a298` device.

### Before flashing

Flashing **erases** the main MCU firmware, and the IAP protocol has no
read-back command, so the currently installed firmware cannot be saved. Keep a
copy of the vendor image you want to restore.

`flash` checks the image before erasing anything: it rejects anything that
does not fit the app region, and it requires the vector table to have an
in-RAM initial stack pointer and a Thumb reset vector pointing into flash.

See the tool's docstring for the wire format.
