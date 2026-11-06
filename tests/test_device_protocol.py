"""
Regression tests for the USB HID protocol layer and icon renderer.

These do NOT require real Luxafor hardware or even a real libhidapi
install: they replace luxafor.hidapi's internal `_Lib` with a fake that
records calls instead of touching ctypes. They verify:

  - the exact bytes sent for each color match the documented protocol
  - the device handle is opened lazily and reused (not reopened per write)
  - unknown color names raise ValueError instead of being silently sent
  - a failed write (e.g. device unplugged) triggers exactly one
    close+reopen+retry, not a crash or a silent no-op
  - the icon renderer produces a valid RGBA image for every color in both
    its active and inactive states

Run directly (no pytest required):
    python3 tests/test_device_protocol.py

This is what a prior session used to validate the protocol/logic layer
without access to real hardware -- see DEVELOPMENT.md for what still needs
verifying against a real Luxafor Flag.
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _FakeLib:
    """Stands in for the real ctypes-bound libhidapi handle."""

    def __init__(self, fail_first_write: bool = False):
        self.open_count = 0
        self.write_count = 0
        self.calls = []
        self._fail_first_write = fail_first_write

    def hid_open(self, vid, pid, serial):
        self.open_count += 1
        self.calls.append(("open", self.open_count))
        return 1000 + self.open_count  # fake non-null handle

    def hid_write(self, handle, report, length):
        self.write_count += 1
        payload = bytes(report[:length])
        if self._fail_first_write and self.write_count == 1:
            self.calls.append(("write-fail", payload))
            return -1
        self.calls.append(("write-ok", payload))
        return length

    def hid_close(self, handle):
        self.calls.append(("close",))

    def hid_error(self, handle):
        return "mock error"


def _install_fake_lib(fail_first_write: bool = False):
    import luxafor.hidapi as hidapi_mod

    fake = _FakeLib(fail_first_write=fail_first_write)
    hidapi_mod._Lib._handle = fake
    hidapi_mod._Lib.get = classmethod(lambda cls: cls._handle)

    import luxafor.device as device_mod
    importlib.reload(device_mod)
    return fake, device_mod


def test_report_bytes_match_protocol():
    fake, device_mod = _install_fake_lib()
    dev = device_mod.LuxaforDevice()

    cases = {
        "red": bytes([0x00, 0x01, 0xFF, 255, 0, 0, 0, 0, 0]),
        "green": bytes([0x00, 0x01, 0xFF, 0, 255, 0, 0, 0, 0]),
        "blue": bytes([0x00, 0x01, 0xFF, 0, 0, 255, 0, 0, 0]),
        "cyan": bytes([0x00, 0x01, 0xFF, 0, 255, 255, 0, 0, 0]),
        "magenta": bytes([0x00, 0x01, 0xFF, 255, 0, 255, 0, 0, 0]),
        "yellow": bytes([0x00, 0x01, 0xFF, 255, 255, 0, 0, 0, 0]),
        "white": bytes([0x00, 0x01, 0xFF, 255, 255, 255, 0, 0, 0]),
        "off": bytes([0x00, 0x01, 0xFF, 0, 0, 0, 0, 0, 0]),
    }
    for color, expected_report in cases.items():
        dev.set_color(color)
        assert fake.calls[-1] == ("write-ok", expected_report), (
            f"{color}: expected {expected_report!r}, got {fake.calls[-1]!r}"
        )
    print(f"OK  report_bytes_match_protocol ({len(cases)} colors)")


def test_unknown_color_raises():
    _fake, device_mod = _install_fake_lib()
    dev = device_mod.LuxaforDevice()
    try:
        dev.set_color("chartreuse")
    except ValueError:
        print("OK  unknown_color_raises")
        return
    raise AssertionError("expected ValueError for an unknown color name")


def test_device_opened_once_and_reused():
    fake, device_mod = _install_fake_lib()
    dev = device_mod.LuxaforDevice()
    for color in ("red", "green", "blue", "off"):
        dev.set_color(color)
    assert fake.open_count == 1, f"expected exactly 1 open call, got {fake.open_count}"
    print(f"OK  device_opened_once_and_reused ({fake.write_count} writes, 1 open)")


def test_reconnects_after_write_failure():
    fake, device_mod = _install_fake_lib(fail_first_write=True)
    dev = device_mod.LuxaforDevice()
    dev.set_color("green")  # first write fails -> must close, reopen, retry

    assert fake.calls[0][0] == "open"
    assert fake.calls[1][0] == "write-fail"
    assert fake.calls[2][0] == "close"
    assert fake.calls[3][0] == "open"
    assert fake.calls[4][0] == "write-ok"
    assert fake.open_count == 2
    print("OK  reconnects_after_write_failure")


def test_icon_renderer_covers_all_colors_and_states():
    from icon_renderer import render_icon
    from luxafor.device import COLORS

    count = 0
    for name in COLORS:
        for active in (True, False):
            image = render_icon(name, active)
            assert image.mode == "RGBA", f"{name}/{active}: expected RGBA, got {image.mode}"
            assert image.size == (256, 256), f"{name}/{active}: unexpected size {image.size}"
            count += 1
    print(f"OK  icon_renderer_covers_all_colors_and_states ({count} icons)")


def main():
    tests = [
        test_report_bytes_match_protocol,
        test_unknown_color_raises,
        test_device_opened_once_and_reused,
        test_reconnects_after_write_failure,
        test_icon_renderer_covers_all_colors_and_states,
    ]
    for test in tests:
        test()
    print(f"\nAll {len(tests)} tests passed.")
    print("Reminder: these mock out the HID layer entirely. They do NOT prove")
    print("the plugin works against real hardware -- run")
    print("tools/manual_hardware_test.py on a machine with a Flag plugged in")
    print("for that. See DEVELOPMENT.md.")


if __name__ == "__main__":
    main()
