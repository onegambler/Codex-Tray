import math

import gi
gi.require_version("GdkPixbuf", "2.0")

import cairo

from config import ICON_SIZE, COLORS, HIGH_THRESHOLD, MEDIUM_THRESHOLD


def _get_color(remaining_fraction: float) -> tuple:
    if remaining_fraction >= HIGH_THRESHOLD:
        return COLORS["high"]
    elif remaining_fraction >= MEDIUM_THRESHOLD:
        return COLORS["medium"]
    return COLORS["low"]


def render_icon(remaining_fraction: float, show_pct: bool = True, warn: bool = False) -> cairo.ImageSurface:
    size = ICON_SIZE
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surface)
    ctx.set_antialias(cairo.ANTIALIAS_BEST)

    cx = cy = size / 2
    pad = 1.5
    radius = size / 2 - pad

    if warn:
        ctx.arc(cx, cy, radius, 0, 2 * math.pi)
        ctx.set_source_rgba(0.8, 0.2, 0.1, 0.95)
        ctx.fill()
        ctx.set_source_rgba(1, 1, 1, 0.95)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(size * 0.55)
        extents = ctx.text_extents("!")
        tx = cx - extents.width / 2 - extents.x_bearing
        ty = cy - extents.height / 2 - extents.y_bearing
        ctx.move_to(tx, ty)
        ctx.show_text("!")
        ctx.stroke()
        return surface

    ctx.arc(cx, cy, radius, 0, 2 * math.pi)
    ctx.set_source_rgba(0.1, 0.1, 0.1, 0.85)
    ctx.fill_preserve()
    ctx.set_source_rgba(0.5, 0.5, 0.5, 0.25)
    ctx.set_line_width(1.0)
    ctx.stroke()

    color = _get_color(remaining_fraction)
    start_angle = -math.pi / 2
    sweep = 2 * math.pi * remaining_fraction

    ctx.set_line_width(2.5)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.arc(cx, cy, radius, start_angle, start_angle + sweep)
    ctx.set_source_rgba(*color, 0.95)
    ctx.stroke()

    if show_pct:
        pct = int(round(remaining_fraction * 100))
        text = str(pct)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        font_size = size * 0.50
        ctx.set_font_size(font_size)

        extents = ctx.text_extents(text)
        tw = extents.width
        th = extents.height
        tx = cx - tw / 2 - extents.x_bearing
        ty = cy - th / 2 - extents.y_bearing

        bw = tw + 4
        bh = th + 1
        bx = tx + extents.x_bearing - 2
        by = ty + extents.y_bearing - 1
        r = 1.5
        ctx.new_path()
        ctx.arc(bx + r, by + r, r, math.pi, 3 * math.pi / 2)
        ctx.arc(bx + bw - r, by + r, r, 3 * math.pi / 2, 2 * math.pi)
        ctx.arc(bx + bw - r, by + bh - r, r, 0, math.pi / 2)
        ctx.arc(bx + r, by + bh - r, r, math.pi / 2, math.pi)
        ctx.close_path()
        ctx.set_source_rgba(0, 0, 0, 0.7)
        ctx.fill()

        ctx.move_to(tx, ty)
        ctx.set_source_rgba(1, 1, 1, 0.95)
        ctx.show_text(text)

    return surface


def surface_to_pixbuf(surface: cairo.ImageSurface):
    from gi.repository import GdkPixbuf, GLib
    data = surface.get_data()
    return GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes(data),
        GdkPixbuf.Colorspace.RGB,
        True,
        8,
        surface.get_width(),
        surface.get_height(),
        surface.get_stride(),
    )
