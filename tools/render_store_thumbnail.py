#!/usr/bin/env python3
"""
Regenerates store/Thumbnail.png -- NOT part of the StreamController plugin
runtime. The store shows this image on the plugin's card; official plugins
use 1000x360.

Draws the same status dots the buttons show (icon_renderer.render_icon), so
re-run it whenever the colors or icon style change. Needs Pillow and the
Cantarell font (installed by default on GNOME/Fedora).

Usage:
    python3 tools/render_store_thumbnail.py
"""
import os
import sys

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PLUGIN_DIR)

from PIL import Image, ImageDraw, ImageFont

from icon_renderer import render_icon

WIDTH, HEIGHT = 1000, 360
FONT = "/usr/share/fonts/abattis-cantarell-vf-fonts/Cantarell-VF.otf"
COLOR_ORDER = ["off", "red", "green", "blue", "cyan", "magenta", "yellow", "white"]


def main() -> None:
    image = Image.new("RGBA", (WIDTH, HEIGHT), (24, 26, 31, 255))
    draw = ImageDraw.Draw(image)

    title_font = ImageFont.truetype(FONT, 72)
    title_font.set_variation_by_name("Bold")
    subtitle_font = ImageFont.truetype(FONT, 30)

    draw.text((WIDTH / 2, 92), "Luxafor Flag", font=title_font,
              fill=(240, 240, 240), anchor="mm")
    draw.text((WIDTH / 2, 156), "Set your status light over direct USB HID",
              font=subtitle_font, fill=(165, 168, 176), anchor="mm")

    dot, gap = 104, 12
    x0 = (WIDTH - (len(COLOR_ORDER) * dot + (len(COLOR_ORDER) - 1) * gap)) // 2
    for i, name in enumerate(COLOR_ORDER):
        icon = render_icon(name, active=(name == "red")).resize((dot, dot), Image.LANCZOS)
        image.alpha_composite(icon, (x0 + i * (dot + gap), 214))

    out_path = os.path.join(PLUGIN_DIR, "store", "Thumbnail.png")
    image.save(out_path)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
