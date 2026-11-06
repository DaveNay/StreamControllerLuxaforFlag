from src.backend.PluginManager.ActionCore import ActionCore
from src.backend.PluginManager.EventAssigner import EventAssigner
from src.backend.DeckManagement.InputIdentifier import Input

from GtkHelper.ComboRow import SimpleComboRowItem
from GtkHelper.GenerativeUI.ComboRow import ComboRow

from luxafor.device import DEFAULT_COLOR
from icon_renderer import render_icon

# Order the colors appear in the configuration dropdown. These match the
# Luxafor Flag's own set of "basic" colors, plus Off.
COLOR_ORDER = ["off", "red", "green", "blue", "cyan", "magenta", "yellow", "white"]


class SetColor(ActionCore):
    """
    Sets the Luxafor Flag to a configured color when pressed.

    Every SetColor button on the deck shares one plugin-wide picture of
    "what color is the Flag currently showing" (kept on the plugin object,
    see LuxaforFlagPlugin.apply_color/_broadcast_state in main.py). Whenever
    any button changes that color, every other SetColor button is asked to
    redraw itself -- so if you have a Red button and a Green button and you
    press Red, the Green button automatically flips to its inactive look,
    and vice versa, without any button having to know about any other one
    directly.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_configuration = True

        # Same default triggers the deprecated ActionBase wired to
        # on_key_down (key press, dial press); users can remap it in the
        # action's settings.
        self.add_event_assigner(EventAssigner(
            id="set_color_pressed",
            ui_label=self.get_translation("actions.set-color.event.pressed"),
            default_events=[Input.Key.Events.DOWN, Input.Dial.Events.DOWN],
            callback=self.on_pressed,
        ))

        # GenerativeUI widgets register themselves on the action when
        # constructed, and StreamController's config panel shows every
        # registered one automatically -- so this must be built exactly once,
        # here, and NOT returned from get_config_rows(). (Building it inside
        # get_config_rows() added another duplicate dropdown every time the
        # config panel was reopened.)
        self.color_combo = ComboRow(
            action_core=self,
            var_name="color",
            default_value=DEFAULT_COLOR,
            items=[
                SimpleComboRowItem(value=name, label=self._color_label(name))
                for name in COLOR_ORDER
            ],
            title=self.get_translation("actions.set-color.color-row.label"),
            on_change=self._on_color_changed,
        )

    def on_ready(self) -> None:
        self.plugin_base.register_action(self)
        self.refresh_icon()

    def on_update(self) -> None:
        # Called whenever the app wants this action to redraw itself (e.g.
        # its page became active again). Re-registering is a no-op if we're
        # already registered; refreshing catches up on any color changes
        # that happened while this button's page wasn't visible.
        self.plugin_base.register_action(self)
        self.refresh_icon()

    def on_removed_from_cache(self) -> None:
        self.plugin_base.unregister_action(self)
        super().on_removed_from_cache()

    def on_remove(self) -> None:
        self.plugin_base.unregister_action(self)
        super().on_remove()

    def _on_color_changed(self, widget, new_item, old_item) -> None:
        # Only updates this button's own preview -- the physical device
        # only changes when the button is actually pressed.
        self.refresh_icon()

    def get_configured_color(self) -> str:
        return self.get_settings().get("color", DEFAULT_COLOR)

    def on_pressed(self, data: dict = None) -> None:
        color = self.get_configured_color()
        success = self.plugin_base.apply_color(color)
        if not success:
            self.show_error()
        else:
            self.hide_error()

    def refresh_icon(self) -> None:
        color = self.get_configured_color()
        active = color == self.plugin_base.current_color

        self.set_media(image=render_icon(color, active), size=0.85)
        self.set_bottom_label(self._color_label(color))

    def _color_label(self, color_name: str) -> str:
        return self.get_translation(f"actions.set-color.color.{color_name}")
