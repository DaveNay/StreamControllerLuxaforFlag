"""
Renders the status icon shown on each Luxafor Flag color button.

Icons are drawn on the fly with Pillow instead of being shipped as static
PNGs, so every color gets a correctly colored, correctly styled icon in both
of its states:

  * active   -- this button's color is the one currently applied to the
                physical device: a bold, fully saturated, glowing dot.
  * inactive -- some other color is currently active: a dim, outline-only
                dot, showing this color is available but not applied.

The button's color name is shown separately as a bottom label (see
actions/SetColor/SetColor.py), so the icon itself only needs to communicate
color + active/inactive state.
"""
from PIL import Image, ImageDraw

from luxafor.device import COLORS

_SIZE = 256  # Rendered large; StreamController scales it down via `size=`.

_OFF_FILL = (40, 40, 40)
_OFF_RING = (235, 235, 235)

_INACTIVE_FILL_ALPHA = 110
_INACTIVE_RING_ALPHA = 160


def render_icon(color_name: str, active: bool) -> Image.Image:
    """
    Build an RGBA status icon for `color_name` (a key of luxafor.device.COLORS,
    e.g. "red" or "off") in its active or inactive style.
    """
    rgb = COLORS.get(color_name, (128, 128, 128))
    is_off = color_name == "off"
    fill = _OFF_FILL if is_off else rgb
    ring = _OFF_RING if is_off else rgb

    image = Image.new("RGBA", (_SIZE, _SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    margin = _SIZE * 0.12
    bbox = (margin, margin, _SIZE - margin, _SIZE - margin)

    if active:
        ring_width = round(_SIZE * 0.045)
        draw.ellipse(bbox, fill=(*fill, 255), outline=(*ring, 255), width=ring_width)

        # Soft outer glow ring for extra "this one is live" emphasis.
        glow_margin = margin - _SIZE * 0.04
        glow_bbox = (glow_margin, glow_margin, _SIZE - glow_margin, _SIZE - glow_margin)
        draw.ellipse(glow_bbox, outline=(*ring, 90), width=round(_SIZE * 0.02))
    else:
        ring_width = round(_SIZE * 0.03)
        draw.ellipse(
            bbox,
            fill=(*fill, _INACTIVE_FILL_ALPHA),
            outline=(*ring, _INACTIVE_RING_ALPHA),
            width=ring_width,
        )

    return image
