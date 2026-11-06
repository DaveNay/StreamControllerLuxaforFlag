#!/usr/bin/env python3
"""
Manual hardware smoke test -- NOT part of the StreamController plugin
runtime, and not part of the automated test suite in tests/.

Run this directly on a machine with a real Luxafor Flag plugged in, BEFORE
testing inside StreamController itself. It exercises exactly the same
luxafor/ code the plugin uses, standalone: no StreamController install is
required, only a system install of libhidapi (see README.md) and the udev
rule (see udev/70-luxafor.rules) so the device can be opened as your
regular user.

This is the fastest way to isolate "the USB/HID layer is broken" from "the
plugin's StreamController-side integration is broken" -- if this script
fails, the problem is in luxafor/hidapi.py or luxafor/device.py (or your
system setup); if it succeeds but the plugin still doesn't work inside
StreamController, the problem is on the plugin/action side.

Usage:
    python3 tools/manual_hardware_test.py
"""
import glob
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from luxafor.device import LuxaforDevice, PRODUCT_ID, VENDOR_ID
from luxafor.hidapi import HidApiError, _Lib

COLOR_ORDER = ["red", "green", "blue", "cyan", "magenta", "yellow", "white", "off"]


def _on_usb_bus() -> bool | None:
    """Whether the kernel has enumerated a Flag at all (None if sysfs isn't available)."""
    devices = glob.glob("/sys/bus/usb/devices/*/idVendor")
    if not devices:
        return None
    for vendor_path in devices:
        product_path = os.path.join(os.path.dirname(vendor_path), "idProduct")
        try:
            with open(vendor_path) as v, open(product_path) as p:
                if int(v.read(), 16) == VENDOR_ID and int(p.read(), 16) == PRODUCT_ID:
                    return True
        except (OSError, ValueError):
            continue
    return False


def main() -> int:
    # Check each layer separately so a failure says which one is broken.
    print("Loading libhidapi... ", end="", flush=True)
    try:
        print(f"OK ({_Lib.get()._name})")
    except HidApiError as e:
        print(f"FAILED: {e}")
        return 1

    print("Checking the USB bus for a Luxafor Flag (VID 0x04D8 / PID 0xF372)... ", end="", flush=True)
    on_bus = _on_usb_bus()
    if on_bus is False:
        print("FAILED: the kernel doesn't see one.")
        print("  - Check it's plugged in; try another cable/port (`lsusb` should list 04d8:f372).")
        return 1
    print("OK" if on_bus else "skipped (no sysfs)")

    device = LuxaforDevice()
    print("Opening the Flag... ", end="", flush=True)
    if not device.is_available():
        print("FAILED: it's on the USB bus but hid_open() couldn't open it.")
        print("  - Most likely a permissions problem: install udev/70-luxafor.rules,")
        print("    reload udev, then unplug/replug the device.")
        return 1
    print("OK\n")

    for name in COLOR_ORDER:
        print(f"Setting color: {name:8s} ", end="", flush=True)
        try:
            device.set_color(name)
        except (HidApiError, ValueError) as e:
            print(f"FAILED: {e}")
            return 1
        print("sent -- check the Flag now.")
        time.sleep(1.5)

    print("\nAll colors were sent without a USB/HID error. If the physical LED")
    print("visibly matched each printed color in turn, the transport layer is")
    print("confirmed working end-to-end and any remaining issues are on the")
    print("StreamController/plugin integration side, not the USB layer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
