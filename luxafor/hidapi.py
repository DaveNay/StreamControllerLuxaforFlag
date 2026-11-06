"""
Minimal ctypes bindings to the system's libhidapi shared library.

This is the whole USB transport for the plugin: it loads libhidapi (a small,
widely-packaged C library that talks to the OS's HID subsystem -- hidraw on
Linux) and calls straight into it with ctypes, which is part of the Python
standard library. There is no Luxafor-specific code here, no dependency on
any of the pre-built Luxafor client libraries, and no network/cloud API --
just raw HID reports going out over USB.

Only the handful of libhidapi functions this plugin needs are bound
(hid_init, hid_open, hid_write, hid_close, hid_error, hid_exit). The
function signatures come from libhidapi's public, stable C header
(hidapi.h) at https://github.com/libusb/hidapi -- they are part of that
library's documented ABI, not anything copied from a Luxafor project.

Requires libhidapi to be installed on the system:
    Fedora:        sudo dnf install hidapi
    Debian/Ubuntu: sudo apt install libhidapi-hidraw0
    Arch:          sudo pacman -S hidapi
"""
import ctypes
import ctypes.util
import threading

# Different distros/backends ship libhidapi under different sonames
# depending on whether it talks to the kernel via hidraw or via libusb.
# Try them in a sensible order; either backend works fine for our purposes.
_CANDIDATE_LIBRARY_NAMES = ("hidapi-hidraw", "hidapi-libusb", "hidapi")
_CANDIDATE_SONAMES = (
    "libhidapi-hidraw.so.0", "libhidapi-hidraw.so",
    "libhidapi-libusb.so.0", "libhidapi-libusb.so",
    "libhidapi.so.0", "libhidapi.so",
    "libhidapi.dylib",
)


class HidApiError(RuntimeError):
    """Raised when libhidapi can't be found/loaded, or a HID call fails."""


class _Lib:
    """Lazily loads libhidapi once per process and exposes the C ABI we use."""

    _lock = threading.Lock()
    _handle = None

    @classmethod
    def get(cls) -> ctypes.CDLL:
        with cls._lock:
            if cls._handle is None:
                cls._handle = cls._load()
            return cls._handle

    @staticmethod
    def _load() -> ctypes.CDLL:
        lib = None

        for name in _CANDIDATE_LIBRARY_NAMES:
            path = ctypes.util.find_library(name)
            if path is None:
                continue
            try:
                lib = ctypes.CDLL(path)
                break
            except OSError:
                continue

        if lib is None:
            # find_library() depends on ldconfig/dev symlinks that aren't
            # always present; fall back to loading well-known sonames
            # directly, which works as long as the runtime linker can find
            # them on the standard library search path.
            for soname in _CANDIDATE_SONAMES:
                try:
                    lib = ctypes.CDLL(soname)
                    break
                except OSError:
                    continue

        if lib is None:
            raise HidApiError(
                "Could not load libhidapi. Install it via your package manager, "
                "e.g. 'sudo dnf install hidapi' (Fedora), "
                "'sudo apt install libhidapi-hidraw0' (Debian/Ubuntu), or "
                "'sudo pacman -S hidapi' (Arch)."
            )

        lib.hid_init.argtypes = []
        lib.hid_init.restype = ctypes.c_int
        lib.hid_exit.argtypes = []
        lib.hid_exit.restype = ctypes.c_int
        lib.hid_open.argtypes = [ctypes.c_ushort, ctypes.c_ushort, ctypes.c_wchar_p]
        lib.hid_open.restype = ctypes.c_void_p
        lib.hid_write.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
        lib.hid_write.restype = ctypes.c_int
        lib.hid_close.argtypes = [ctypes.c_void_p]
        lib.hid_close.restype = None
        lib.hid_error.argtypes = [ctypes.c_void_p]
        lib.hid_error.restype = ctypes.c_wchar_p

        if lib.hid_init() != 0:
            raise HidApiError("hid_init() failed")

        return lib


class HidDevice:
    """An open connection to a single HID device, identified by VID/PID."""

    def __init__(self, vendor_id: int, product_id: int):
        self._vendor_id = vendor_id
        self._product_id = product_id
        self._lib = _Lib.get()
        self._handle = self._lib.hid_open(vendor_id, product_id, None)
        if not self._handle:
            raise HidApiError(
                f"No HID device found for VID=0x{vendor_id:04X} PID=0x{product_id:04X}. "
                "Is it plugged in, and do you have permission to access it? "
                "See udev/70-luxafor.rules for the required udev rule."
            )

    def write(self, report: bytes) -> None:
        if not self._handle:
            raise HidApiError("HID device is closed")
        result = self._lib.hid_write(self._handle, report, len(report))
        if result < 0:
            message = self._lib.hid_error(self._handle) or "unknown error"
            raise HidApiError(f"hid_write failed: {message}")

    def close(self) -> None:
        if self._handle:
            self._lib.hid_close(self._handle)
            self._handle = None

    def __enter__(self) -> "HidDevice":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
