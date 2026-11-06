"""
Luxafor Flag USB HID protocol.

Talks straight to the device over USB HID reports -- no Luxafor SDK and no
Luxafor cloud/web API. The report layout below comes from Luxafor's own
published HID protocol documentation for the Flag.

"Static color" command (mode 0x01), sent as a 9-byte HID output report:

    byte 0: HID report number -- always 0x00 (the Flag doesn't use report IDs)
    byte 1: command mode      -- 0x01 for "static color"
    byte 2: target LED        -- 0xFF for "all LEDs" (the Flag has a front
                                  and back LED; 0xFF addresses both at once)
    byte 3: red   (0-255)
    byte 4: green (0-255)
    byte 5: blue  (0-255)
    bytes 6-8: unused, must be 0x00

The device identifies itself as VID 0x04D8 (Microchip Technology, the
silicon vendor Luxafor's firmware runs on), PID 0xF372.
"""
import threading

from luxafor.hidapi import HidApiError, HidDevice

VENDOR_ID = 0x04D8
PRODUCT_ID = 0xF372

_MODE_STATIC_COLOR = 0x01
_LED_ALL = 0xFF
_REPORT_LENGTH = 9

# Colors offered in the action's configuration dropdown, in RGB.
# "off" drives the LEDs fully dark.
COLORS: dict[str, tuple[int, int, int]] = {
    "off": (0, 0, 0),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "yellow": (255, 255, 0),
    "white": (255, 255, 255),
}

DEFAULT_COLOR = "off"


class LuxaforDevice:
    """
    Thread-safe handle to a Luxafor Flag.

    The HID connection is opened lazily on first use and transparently
    reopened if the device was unplugged and replugged, so callers don't
    need to worry about connection lifecycle -- just call set_color().
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._handle: HidDevice | None = None

    def set_color(self, color_name: str) -> None:
        """Set all LEDs on the Flag to `color_name`. Raises HidApiError on failure."""
        rgb = COLORS.get(color_name)
        if rgb is None:
            raise ValueError(f"Unknown Luxafor color '{color_name}'. Valid: {sorted(COLORS)}")

        report = bytes([0x00, _MODE_STATIC_COLOR, _LED_ALL, *rgb, 0, 0, 0])
        assert len(report) == _REPORT_LENGTH

        with self._lock:
            self._write_with_reconnect(report)

    def is_available(self) -> bool:
        """Best-effort check for whether a Flag is currently connected."""
        try:
            with HidDevice(VENDOR_ID, PRODUCT_ID):
                return True
        except HidApiError:
            return False

    def close(self) -> None:
        with self._lock:
            self._close_locked()

    def _write_with_reconnect(self, report: bytes) -> None:
        if self._handle is None:
            self._handle = HidDevice(VENDOR_ID, PRODUCT_ID)

        try:
            self._handle.write(report)
            return
        except HidApiError:
            # The device may have been unplugged and replugged since we
            # opened it. Drop the stale handle and retry once with a fresh
            # one before giving up and letting the error propagate.
            self._close_locked()

        self._handle = HidDevice(VENDOR_ID, PRODUCT_ID)
        self._handle.write(report)

    def _close_locked(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None
