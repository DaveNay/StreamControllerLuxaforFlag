# Luxafor Flag plugin for StreamController

Control a [Luxafor Flag](https://luxafor.com/product/flag/) USB status light
from [StreamController](https://github.com/StreamController/StreamController)
with **direct USB HID communication** -- no Luxafor SDK/client library, and
no Luxafor cloud/web API.

## What it does

Adds one action, **Set Color**. Assign it to a button and pick a color
(Off, Red, Green, Blue, Cyan, Magenta, Yellow, or White). Pressing the
button lights the Flag that color.

Every Set Color button on your deck shares one picture of "what color is the
Flag currently showing":

- The button whose configured color matches the Flag's current color is
  drawn **active** -- a bold, glowing, fully saturated dot.
- Every other Set Color button is drawn **inactive** -- a dim, outline-only
  dot -- automatically, the instant a different button is pressed.

So a Red button, a Green button, and an Off button placed next to each other
behave like a set of radio buttons: press Green, and Red/Off immediately
flip to inactive, with no extra configuration required. This works across
different pages/profiles too, since the "current color" is tracked once for
the whole plugin, not per button.

## How it talks to the device

The plugin binds directly to the system's `libhidapi` C library with
[`ctypes`](https://docs.python.org/3/library/ctypes.html) (Python's
standard-library FFI -- no extra Python packages required) and sends the
Flag's documented 9-byte "static color" HID report itself:

```
byte 0: report number = 0x00
byte 1: command mode  = 0x01 (static color)
byte 2: target LED    = 0xFF (front + back)
byte 3: red   (0-255)
byte 4: green (0-255)
byte 5: blue  (0-255)
bytes 6-8: unused (0x00)
```

The device is identified by USB VID `0x04D8` / PID `0xF372`. See
[`luxafor/hidapi.py`](luxafor/hidapi.py) and
[`luxafor/device.py`](luxafor/device.py) for the full implementation.

## Requirements

- **libhidapi**, the C library the plugin talks to over ctypes. It's a
  common, small, permissively-licensed library that most distros package:
  - Fedora: `sudo dnf install hidapi`
  - Debian/Ubuntu: `sudo apt install libhidapi-hidraw0`
  - Arch: `sudo pacman -S hidapi`
- **USB permission** to access the Flag as your normal user. Install the
  provided udev rule:

  ```sh
  sudo cp udev/70-luxafor.rules /etc/udev/rules.d/
  sudo udevadm control --reload-rules
  sudo udevadm trigger
  ```

  Then unplug and replug the Flag (or reboot). Without this, HID writes
  will fail with a permission error unless StreamController is run as root
  (not recommended).

- **Flatpak installs of StreamController**: no extra setup needed. The
  Flathub build already has `--device=all` (it needs it for the Stream Deck
  itself) and bundles its own libhidapi, so the plugin can enumerate and
  open HID devices from inside the sandbox. You still need the udev rule
  above, since that controls permissions on the host's device nodes.

## Installation

1. Copy (or clone) this folder into StreamController's plugins directory,
   **named `com_davenay_LuxaforFlag`** (StreamController imports plugins as
   `plugins.<folder>.main`). The plugins directory is
   `~/.var/app/com.core447.StreamController/data/plugins/` for both Flatpak
   and native installs, unless overridden with `--data`, a `data-path` in
   `~/.var/app/com.core447.StreamController/static/settings.json`, or the
   `PLUGIN_DIR` environment variable.
2. Install `libhidapi` and the udev rule as described above.
3. Restart StreamController. If it was started in the background
   (`--daemon-only`, the default autostart), plugins that aren't on any page
   yet only load once you open the main window.
4. Add the **Set Color** action to a button, pick a color in its
   configuration, and press it.

No `pip install` step is needed -- everything the plugin uses beyond
StreamController itself (`ctypes`, `threading`) is in the Python standard
library.

## Testing

```sh
python3 tests/test_device_protocol.py     # HID protocol + icon logic, no hardware needed
python3 tools/manual_hardware_test.py     # cycles a real Flag through every color
```

Validated end to end on 2026-10-23 with a real Luxafor Flag and a Stream
Deck Original V2 under StreamController 1.5.0-beta.16 (Flatpak) on Fedora
44. If the Flag doesn't show up in `lsusb` at all, see the USB enumeration
notes in [`DEVELOPMENT.md`](DEVELOPMENT.md). See that file too for the full
validation checklist, known-untested areas, and design rationale before
continuing development.

## Project layout

```
main.py                    Plugin entry point; registers the action and
                            tracks/broadcasts the Flag's current color.
manifest.json               Plugin metadata (name, id, versions, store text).
attribution.json            License/copyright shown in the store.
about.json                  Author/support shown in the app's Plugin About.
actions.json                Action/settings description for the app's assistant.
store/Thumbnail.png         Store card image (1000x360).
actions/SetColor/SetColor.py   The "Set Color" action.
icon_renderer.py            Draws the active/inactive status dot per color.
luxafor/hidapi.py           ctypes bindings to libhidapi (the USB transport).
luxafor/device.py           Luxafor Flag HID protocol (colors, report format).
udev/70-luxafor.rules       udev rule for non-root USB access.
locales.csv                 UI strings (key;en_US;...).
tests/test_device_protocol.py   Automated regression tests (no hardware needed).
tools/manual_hardware_test.py   Manual real-hardware smoke test.
DEVELOPMENT.md              Handoff notes: validation checklist, design
                            rationale, and what's NOT yet verified.
```
