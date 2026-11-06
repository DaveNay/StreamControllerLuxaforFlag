# Development / handoff notes

Read this first if you're picking up this repo in a new session (Claude or
human). The plugin was written without hardware access, then **fully
validated against a real Flag on 2026-10-23**: every step of the
checklist below passed (see "Status"). The one open hardware question is
whether the Flag needs the `old_scheme_first` USB workaround every time.

## Status as of 2026-10-23 (first session on the hardware machine)

Test machine: Fedora 44 (kernel 7.2), hidapi 0.15.0, StreamController
**1.5.0-beta.16 Flatpak** from Flathub (GNOME Platform 50 runtime, Python
3.13), Stream Deck Original V2.

**The Flag itself was not attached during this session** -- it never
enumerated on the USB bus (`lsusb` had no `04d8:f372`, and the kernel log
had no enumeration attempt or descriptor error for it all boot), so
nothing that needs the physical LED could be tested. Everything else was.

Later that day the owner plugged it in twice -- hub port `1-7.4` (09:58)
and root port `1-4` (11:16) -- and it **failed USB enumeration both
times**: `device descriptor read/64, error -32`/`-71`, then `Device not
responding to setup address` / `device not accepting address, error -71`,
power cycle, `unable to enumerate USB device`. The mouse works fine on
`1-7.4`, so the port isn't the problem. The failure happens below the HID
layer (the kernel never reads a VID/PID), so it's **not** a plugin,
hidapi, or udev problem.

**Workaround that worked:** switching the kernel to the old USB
enumeration scheme, then replugging:
```sh
echo Y | sudo tee /sys/module/usbcore/parameters/old_scheme_first
```
With that set, the Flag enumerated first try on root port `1-4`
(11:24:57) as `04d8:f372 "LUXAFOR FLAG"`, bcdDevice 1.00, one HID
interface -> `/dev/hidraw8`. The sysfs setting resets on reboot; to make it
permanent (usbcore is built in on Fedora, so modprobe.d won't work):
`sudo grubby --update-kernel=ALL --args="usbcore.old_scheme_first=1"`.
Still to confirm: whether the Flag *needs* this every time, or whether
that plug-in just happened to work.

**The kernel's `hid-led` driver also binds to the Flag** (it has built-in
Luxafor support), exposing `/sys/class/leds/luxafor<N>:{red,green,blue}:led{0-5}`.
It coexists with hidraw (the hidraw node is still created, and hidapi
opens that), so it shouldn't interfere with the plugin -- but anything
else writing to those LED class devices would change the color behind the
plugin's back, and `hid-led` may reset the LEDs when it binds on plug-in.
Worth watching for during checklist step 11 (unplug/replug).

After enumeration, `manual_hardware_test.py` passed the libhidapi and
USB-bus checks and failed at `hid_open()` as expected: `/dev/hidraw8` was
`root:root 0600` with no udev rule installed. `sudo udevadm trigger`
applies the rule to an already-attached device, so no replug is needed
after installing it.

After installing `udev/70-luxafor.rules` + `udevadm trigger`:
- `/dev/hidraw8` became `crw-rw-rw-+` with ACL `user:davenay:rw-`, i.e.
  **the `uaccess` tag works now that the file is numbered 70**. The
  `MODE="0666"` fallback is therefore redundant on systemd systems and
  could be dropped (untested without it).
- `manual_hardware_test.py` ran to completion as a normal user:
  `hid_open()` found the Flag by VID/PID and `hid_write()` accepted all 8
  color reports with no error. (Physical LED colors: see below.)

Checklist results (numbering matches the checklist below):

| # | Step | Result |
|---|---|---|
| 1 | System deps | hidapi already installed. **udev rule not installed** (needs sudo; left for the owner). |
| 2 | `manual_hardware_test.py` | libhidapi loads (`libhidapi-hidraw.so.0` via `find_library`); stops at "Flag not on USB bus". |
| 3 | Regression suite | Passes, before and after this session's changes. |
| 4 | App version check | Passes -- see "Version pinning". |
| 5 | Install | Symlinked as `com_davenay_LuxaforFlag` into `~/.var/app/com.core447.StreamController/data/plugins/` (confirmed path, see step 5). |
| 6 | Restart, check logs | **Plugin imports and registers** in the real app: no import errors, no version warning. Startup sync logs a clean `failed to set color 'off': No HID device found` error (expected with no Flag) and doesn't crash. |
| 1 (later) | udev rule | Installed as `70-luxafor.rules`; uaccess ACL confirmed. |
| 2 (later) | `manual_hardware_test.py` | Passes once the Flag enumerated (needed `old_scheme_first`, see below). |
| 7 | Set Color button | ✅ LED changes; key shows the active icon. Config panel shows a single dropdown across reopens (duplicate-dropdown fix confirmed). |
| 8 | Cross-button sync | ✅ Red/Green keys flip active/inactive correctly. |
| 9 | Off | ✅ |
| 10 | Page switching | ✅ Icons correct when a page becomes visible again. |
| 11 | Unplug/replug while running | ✅ Unplugged 11:37:41, replugged 11:37:44; next press worked with no error logged, i.e. `_write_with_reconnect` reopened the device transparently. |
| 12 | Press with Flag unplugged | ✅ Key shows the error state; each press logs one clean `No HID device found` error (red, off, green at 11:37:56-58), no traceback, no crash. |

Verified this session without the Flag:

- libhidapi loads on the host *and* inside the Flatpak sandbox (the Flatpak
  bundles its own `libhidapi-hidraw`/`-libusb`, and `find_library` resolves
  them).
- `hid_enumerate` from inside the sandbox sees the same HID devices as the
  host, via both the hidraw and libusb backends. The Flathub build already
  has `devices=all`, so **no `flatpak override` is needed**.
- Every StreamController API the plugin uses was checked against the
  installed 1.5.0-beta.16 source (`/app/bin/StreamController` in the
  Flatpak): `register()`, `ActionHolder`, `ActionInputSupport`, `Input`,
  `ActionCore` + `EventAssigner` key/dial dispatch, `set_media`,
  `set_bottom_label`, `show_error`/`hide_error`, `get_settings`, the
  `on_ready`/`on_update`/`on_removed_from_cache`/`on_remove` lifecycle, and
  `GtkHelper` `ComboRow`/`SimpleComboRowItem` signatures.
- Page switching: `DeckController` calls `on_update()` on the newly visible
  page's actions, and `set_media`/`set_label` safely no-op for actions on
  hidden pages (`get_is_present()`), so broadcasting to off-page buttons is
  harmless. (Still worth confirming on the real UI in step 10.)

Bugs found and fixed this session:

- **Duplicate color dropdowns.** `SetColor.get_config_rows()` constructed a
  new `GenerativeUI.ComboRow` on every call, but GenerativeUI widgets
  self-register on the action and the config panel
  (`ActionConfigurator.ConfigGroup.load_for_action`) shows every registered
  one *in addition to* `get_config_rows()`. Each reopen of the config panel
  would have added another dropdown. Now built once in `__init__`.
- **Failed write left a stale "active" button.** `_on_color_applied` kept
  the old `current_color` on failure, contradicting its own documented
  "None = last attempt failed" contract; e.g. with the Flag unplugged, the
  last-pressed button kept showing active. Now resets to `None`.
- **udev `uaccess` tag was dead.** The rule was `99-luxafor.rules`, but
  systemd applies `uaccess` ACLs in `73-seat-late.rules`, so tags set later
  are ignored and only the world-writable `MODE="0666"` was doing anything.
  Renamed to `udev/70-luxafor.rules`. `MODE="0666"` was kept as a fallback;
  once uaccess is confirmed working on hardware it could be dropped.
- **Fragile `actions` import.** `main.py` imported `actions.SetColor` as a
  top-level package via `sys.path`, a name any other plugin in the process
  could claim first. Now a relative import (`from .actions...`), matching
  the official plugins. (No live collision with the plugins installed here.)
- `on_removed_from_cache`/`on_remove` overrides didn't chain to `super()`,
  skipping `ActionCore.on_disconnect()`. Harmless today (no backend), fixed
  anyway.
- `tools/manual_hardware_test.py` now checks each layer separately
  (libhidapi load -> device on USB bus via sysfs -> `hid_open`) instead of
  one catch-all message that blamed libhidapi/permissions even when the
  device simply wasn't attached.

**Verified on hardware (2026-10-23):** everything in the original
"not verified" list -- `hid_open()` finds the Flag by VID/PID,
`hid_write()` changes the LED, the udev rule grants non-root access on the
host *and* inside the Flatpak, the plugin loads/registers, the config
dropdown renders once and saves its selection (`pages/Main.json` holds
e.g. `{"color": "red"}`), icons render on physical keys, cross-button sync,
page switching, Off, transparent reconnect after replug, and the error
state with the Flag unplugged. No tracebacks in the log at any point.

**Still open / not covered:**

  - Whether the Flag *needs* `usbcore.old_scheme_first` (see above). With
    it set, it enumerated first try on every plug-in (11:24, 11:37,
    11:38); without it, four plug-ins in a row failed. After a reboot,
    plug it in without the setting to find out, and make it permanent
    with `grubby` if it's needed.
  - Of the eight colors, red, green and off were confirmed through
    StreamController; the rest were only sent by the standalone tool.
  - Dial and touchscreen input (only keys were tested; the Stream Deck
    Original V2 has neither).
  - Native (non-Flatpak) StreamController installs.
  - Known limitation, by design: the Flag is write-only, so the plugin
    can't detect a replug or an external change. After a replug the
    buttons keep showing the last color as active until the next press.

## Validation checklist for the hardware system

Work through these roughly in order -- each isolates a different layer, so
if something fails you'll know which layer without guessing.

1. **System dependencies.** Install `libhidapi` (see README.md for the
   per-distro command) and the udev rule in `udev/70-luxafor.rules`, then
   unplug/replug the Flag.

2. **USB/HID layer, standalone.** Run:
   ```sh
   python3 tools/manual_hardware_test.py
   ```
   This cycles the Flag through every color with no StreamController
   involved at all. If this fails, the problem is in `luxafor/hidapi.py`,
   `luxafor/device.py`, or your system setup (libhidapi/udev) -- fix it
   here before going further. If it succeeds, the USB transport is proven
   working end-to-end.

3. **Regression suite.** Run:
   ```sh
   python3 tests/test_device_protocol.py
   ```
   Should still pass (it's hardware-independent; this just re-confirms
   nothing regressed while you were debugging step 2).

4. **Confirm StreamController's installed app version**, and compare it to
   the `app-version`/`minimum-app-version` pinned in `manifest.json` and
   passed to `self.register()` in `main.py` (see "Version pinning" below).
   Find the installed version with `flatpak list | grep -i stream` (or
   `app_version` in its `globals.py`). If they're incompatible,
   `PluginBase.register()` will silently disable the plugin (it logs a
   warning and puts it in `PluginBase.disabled_plugins`, but doesn't raise)
   -- **if the plugin doesn't show up in StreamController's plugin list at
   all, check its logs for this before assuming something else is wrong.**
   ✅ Confirmed 2026-10-23: registers fine on 1.5.0-beta.16.

5. **Install the plugin.** Copy or symlink this whole directory into
   StreamController's plugins directory, **named `com_davenay_LuxaforFlag`**
   (StreamController imports each plugin as `plugins.<folder>.main` and
   derives nothing else from the folder name, but keep it equal to the
   manifest `id`).
   ✅ Confirmed 2026-10-23 from the installed `globals.py`: the plugins
   directory is `~/.var/app/com.core447.StreamController/data/plugins/` --
   hardcoded under `~/.var/app/...` for **native installs too**, not just
   Flatpak (the old `~/.local/share/streamcontroller` guess was wrong).
   It can be overridden with `--data <path>`, a `data-path` key in
   `~/.var/app/com.core447.StreamController/static/settings.json`, or the
   `PLUGIN_DIR` env var. On the test machine it's installed as a symlink
   to this repo, which works because the Flatpak has `filesystems=home`:
   ```sh
   ln -s "$PWD" ~/.var/app/com.core447.StreamController/data/plugins/com_davenay_LuxaforFlag
   ```

6. **Restart StreamController**, check its logs for import errors or the
   version-mismatch warning from step 4. Logs are in
   `~/.var/app/com.core447.StreamController/data/logs/logs.log`.
   ⚠️ The default autostart launches with `--daemon-only`, which preloads
   only plugins referenced by existing pages; a brand-new plugin isn't
   imported until the main window is opened (e.g. run
   `flatpak run com.core447.StreamController` again). Don't mistake its
   absence from the log before that for a load failure.

7. **Add the "Set Color" action** to a button, pick a color, press it.
   Confirm the physical LED changes and the button's icon shows the
   "active" (bold/glowing) style.

8. **Add a second Set Color button** with a different color. Press it.
   Confirm the *first* button's icon automatically flips to "inactive"
   (dim/outline) -- this is the cross-button sync behavior
   (`LuxaforFlagPlugin.apply_color`/`_broadcast_state` in `main.py`).

9. **Test "Off"** the same way.

10. **Test page switching:** put a Set Color button on page A and another
    on page B, switch between pages, confirm each button's icon is correct
    when its page becomes visible (this exercises `SetColor.on_update`).

11. **Test unplug/replug** while StreamController is running: press a
    button, unplug the Flag, replug it, press the button again -- should
    reconnect transparently (`LuxaforDevice._write_with_reconnect`).

12. **Test with the Flag unplugged entirely:** press a button, confirm it
    shows an error state (`self.show_error()` in `SetColor.on_pressed`)
    instead of crashing the plugin or StreamController.

Please update this file with results/findings as you go -- especially
anything in the "not verified" list above that turns out to be wrong, and
the actual plugins-directory path once you find it.

## Design rationale (the "why" behind less-obvious choices)

- **Direct `ctypes` binding to `libhidapi` instead of a pip package.** The
  project owner explicitly wanted direct USB interaction with no
  Luxafor-specific library and no cloud API. `ctypes` is stdlib, so this
  also means the plugin has **zero pip dependencies** -- no `__install__.py`,
  no per-plugin venv, no `rpyc` backend-process split (contrast with
  StreamController's official OBS plugin, which *does* need all of that
  because it depends on `obs-websocket-py`). If you ever add a real pip
  dependency, you'll need to add that machinery back -- see
  `streamcontroller_plugin_tools.installation_helpers.create_venv` and
  `BackendBase` in the StreamController plugin ecosystem for the pattern.
- **Push-based state sync, not polling.** `LuxaforFlagPlugin` (in
  `main.py`) keeps one `current_color` and a list of registered `SetColor`
  actions; `apply_color()` writes to the device once and then calls
  `refresh_icon()` on every registered action directly. This was chosen
  over a `on_tick()` polling pattern (which StreamController's OBS plugin
  uses for e.g. scene-switch buttons) because the Flag can't be *read*
  back (write-only device) and because push is simpler and instant here --
  there's no external system that can change the device's color out from
  under us the way OBS's scene state can change from other sources.
- **PIL-rendered icons instead of static PNGs.** Avoids shipping/maintaining
  16 hand-made image files (8 colors x 2 states); `icon_renderer.py`
  draws a colored dot procedurally. If the visual design needs to change,
  edit that one file.
- **`GLib.idle_add` around all state-changing device calls
  (`apply_color`).** GTK widgets can only be touched from the main thread.
  `apply_color()` can be called from a background thread (the initial
  startup sync) or the main thread (a button press), so it always
  marshals the actual icon/UI update through `GLib.idle_add` rather than
  having two code paths.

## Protocol reference (Luxafor Flag, static-color HID report)

VID `0x04D8`, PID `0xF372`. 9-byte HID output report, report ID 0:

| byte | meaning |
|---|---|
| 0 | report number, always `0x00` |
| 1 | command mode, `0x01` = static color |
| 2 | target LED, `0xFF` = all (front + back) |
| 3 | red (0-255) |
| 4 | green (0-255) |
| 5 | blue (0-255) |
| 6-8 | unused, `0x00` |

Implemented in `luxafor/device.py`. If you need to extend this (e.g. fade
or strobe modes, which the Flag also supports but this plugin doesn't use),
Luxafor's own protocol documentation covers the other command modes; the
byte layout for static color above is the only one this plugin currently
implements.

## Version pinning

`app-version` (`manifest.json`, and `app_version=` in `main.py`'s
`self.register()`, which takes precedence) is `"1.5.0-beta.16"`, the
version this was tested against on 2026-10-23. `minimum-app-version` stays
`"1.5.0-beta.15"`, the version the plugin was originally written against.

How the check actually works (`PluginBase.is_app_version_matching` in
1.5.0-beta.16): the plugin is enabled if the **major** version of
`app-version` equals the running app's major version, **and** the running
app's *base* version (pre-release suffix stripped, so `1.5.0-beta.16` ->
`1.5.0`) is >= `minimum-app-version`'s base version. So the `-beta.N`
suffixes don't matter at all, and this plugin will keep registering on any
1.x release >= 1.5.0. It only needs touching for a StreamController 2.x.

## Where to find more StreamController API context

On a machine with the Flatpak installed, the best source is the exact
installed version, copied out of the sandbox (this is what the 2026-10-23
session verified against):

```sh
mkdir -p /tmp/sc && flatpak run --command=sh --filesystem=/tmp/sc \
    com.core447.StreamController -c 'cp -r /app/bin/StreamController/. /tmp/sc/'
```

Otherwise, the first session (no local copy of StreamController) cloned it
and two of its official plugins to read the real source rather than
guessing:

```sh
git clone --depth 1 https://github.com/StreamController/StreamController
git clone --depth 1 https://github.com/StreamController/PluginTemplate
git clone --depth 1 https://github.com/StreamController/OBSPlugin
```

Particularly useful files, if something in this plugin needs to change:

- `src/backend/PluginManager/ActionCore.py` -- the full action API
  (`on_ready`, `on_update`, `add_event_assigner`, `set_media`, `set_label`,
  `get_settings`/`set_settings`, `show_error`, etc). `SetColor` extends
  this directly; `ActionBase` is a deprecated wrapper the plugin docs say
  not to use for new actions.
- `src/backend/PluginManager/EventAssigner.py` -- how `SetColor` registers
  its "pressed" trigger (key down + dial down by default, user-remappable).
- `src/backend/PluginManager/PluginBase.py` -- plugin registration,
  settings persistence, version-compatibility checks.
- `GtkHelper/GenerativeUI/ComboRow.py` and `GtkHelper/ComboRow.py` -- the
  config-row dropdown widget used in `SetColor.get_config_rows`.
- `PluginTemplate` -- minimal working example of the overall plugin shape.
- `OBSPlugin` -- a much larger official plugin; useful precedent for
  multi-action state sync (its `SwitchScene` action is the closest analog
  to this plugin's active/inactive button behavior, though it polls via
  `on_tick` against an external source of truth instead of pushing state
  like this plugin does).

## Plugin-docs / store conformance

Checked on 2026-11-06 against the plugin docs
(<https://streamcontroller.github.io/docs/latest/plugin_dev/intro/>), the
`PluginTemplate` repo, the official plugins (Counter, Clocks, MicMute,
OSPlugin), and the installed 1.5.0-beta.16 source. Where the docs and the
app's code disagree, the code is what actually runs:

- **Required root files:** `manifest.json` and `attribution.json`.
  `about.json` is optional and feeds the in-app Plugin About dialog
  (`src/windows/Settings/PluginAbout.py`). `actions.json` isn't in the docs
  at all, but every official plugin ships one; the app's AI assistant reads
  it (`src/backend/AI/ActionDocs.py`), including from the store before
  install.
- **Thumbnail:** `manifest.json` `"thumbnail"` is a repo-relative path;
  `store/Thumbnail.png` at 1000x360 matches the official plugins.
  Regenerate with `tools/render_store_thumbnail.py`.
- **Attribution key spelling:** the docs and every official plugin use
  `"license"`, but `StoreBackend` in 1.5.0-beta.16 reads `"licence"`, so the
  license it parses is always empty, for every plugin. This plugin follows
  the docs.
- **Actions:** `ActionBase` is deprecated; actions extend `ActionCore` and
  register triggers with `add_event_assigner(EventAssigner(...))` (docs:
  "Input Events"). None of the four official plugins checked have migrated
  yet.
- **Locales:** `locales.csv` with `use_legacy_locale=False` (the docs'
  recommendation for new plugins) instead of `locales/en_US.json`. Gotcha:
  the CSV `LocaleManager.get(key, fallback)` returns the *key itself* for a
  missing key, never `fallback`, so every key the code asks for must exist
  in the CSV.
- **`requirements.txt`:** not needed. The plugin only uses the stdlib
  (`ctypes`), Pillow (bundled with StreamController), and the system/Flatpak
  `libhidapi`.
- **Page caching:** the docs' one requirement is that cached actions redraw
  from scratch in `on_ready`; `SetColor` keeps no "already drawn" state and
  redraws in both `on_ready` and `on_update`.
- **Submitting:** the store only takes GitHub repos. Add an entry to
  `Plugins.json` in a fork of `StreamController/StreamController-Store`
  (`url`, `hash`, and `commits: {"<app-version>": "<sha>"}`), then open a PR.
  The `.github/workflows/notify-store.yml` the official plugins carry needs
  an org-only `STORE_AUTOMATION_TOKEN` secret, so it doesn't apply here.

## Repository

The public repo is <https://github.com/DaveNay/StreamControllerLuxaforFlag>,
referenced by `manifest.json`'s `"github"`, `main.py`'s `github_repo=`, and
`about.json`'s `"support"`. The store installs a specific commit from
GitHub, so push there before putting a commit hash in a store submission.
