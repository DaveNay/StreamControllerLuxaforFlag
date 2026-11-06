import os
import sys
import threading

# Import StreamController modules
from src.backend.PluginManager.PluginBase import PluginBase
from src.backend.PluginManager.ActionHolder import ActionHolder
from src.backend.PluginManager.ActionInputSupport import ActionInputSupport
from src.backend.DeckManagement.InputIdentifier import Input

from loguru import logger as log

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib

# Make this plugin's own packages (luxafor/, icon_renderer.py) importable as
# plain top-level modules, the same way StreamController's own plugins do.
plugin_dir = os.path.dirname(__file__)
if plugin_dir not in sys.path:
    sys.path.append(plugin_dir)

from luxafor.device import LuxaforDevice, DEFAULT_COLOR
from luxafor.hidapi import HidApiError

# Relative, unlike the imports above: "actions" is a generic top-level name
# that another plugin sharing this process could claim first.
from .actions.SetColor.SetColor import SetColor


class LuxaforFlagPlugin(PluginBase):
    def __init__(self):
        # locales.csv, the format the plugin docs recommend for new plugins.
        super().__init__(use_legacy_locale=False)

        self.device = LuxaforDevice()

        # The plugin's single shared belief about what color the physical
        # Flag is currently showing. None means "unknown" (nothing has set
        # it yet, or the last attempt failed) -- every SetColor button
        # treats "unknown" the same as "some other color is active", i.e.
        # nothing shows as active until a color is actually applied.
        self.current_color: str | None = None

        self._actions_lock = threading.Lock()
        self._registered_actions: list[SetColor] = []

        self.lm = self.locale_manager

        set_color_holder = ActionHolder(
            plugin_base=self,
            action_base=SetColor,
            action_id_suffix="SetColor",
            action_name=self.lm.get("actions.set-color.name"),
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.SUPPORTED,
                Input.Touchscreen: ActionInputSupport.UNTESTED,
            },
        )
        self.add_action_holder(set_color_holder)

        self.register(
            plugin_name="Luxafor Flag",
            github_repo="https://github.com/DaveNay/StreamControllerLuxaforFlag",
            plugin_version="1.0.0",
            app_version="1.5.0-beta.16",
        )

        # Force the device to a known state on startup so button icons can
        # never start out of sync with reality (e.g. a color left on from a
        # previous session, or another app having touched the light). Runs
        # in a background thread since opening the HID device may briefly
        # block, and it's fine if the Flag isn't plugged in yet -- this
        # just quietly fails and leaves current_color as "unknown".
        threading.Thread(
            target=lambda: self.apply_color(DEFAULT_COLOR),
            daemon=True,
            name="luxafor-initial-sync",
        ).start()

    def register_action(self, action: "SetColor") -> None:
        """Called by a SetColor action once it's ready to receive icon updates."""
        with self._actions_lock:
            if action not in self._registered_actions:
                self._registered_actions.append(action)

    def unregister_action(self, action: "SetColor") -> None:
        """Called by a SetColor action when it's removed/evicted."""
        with self._actions_lock:
            if action in self._registered_actions:
                self._registered_actions.remove(action)

    def apply_color(self, color_name: str) -> bool:
        """
        Sets the physical Flag to `color_name` and syncs every registered
        button's icon to match. Safe to call from any thread -- the actual
        icon/UI updates are always marshalled onto the GTK main loop.

        Returns True if the device accepted the color, False if the write
        failed (e.g. the Flag isn't plugged in).
        """
        try:
            self.device.set_color(color_name)
            success = True
        except (HidApiError, ValueError) as e:
            log.error(f"Luxafor Flag: failed to set color '{color_name}': {e}")
            success = False

        GLib.idle_add(self._on_color_applied, color_name, success)
        return success

    def _on_color_applied(self, color_name: str, success: bool) -> bool:
        self.current_color = color_name if success else None
        self._broadcast_state()
        return False  # Don't repeat -- this is a one-shot GLib.idle_add callback.

    def _broadcast_state(self) -> None:
        with self._actions_lock:
            actions = list(self._registered_actions)

        for action in actions:
            try:
                action.refresh_icon()
            except Exception:
                log.exception("Luxafor Flag: failed to refresh a button's icon")
