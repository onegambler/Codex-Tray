import math
from pathlib import Path

import cairo
import gi

gi.require_version("GdkPixbuf", "2.0")

from ai_usage_tray.config import HIGH_THRESHOLD, ICON_SIZE, MEDIUM_THRESHOLD


def _mix(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


def _provider_tinted_color(base: tuple, remaining_fraction: float) -> tuple:
    if remaining_fraction >= HIGH_THRESHOLD:
        return base
    if remaining_fraction >= MEDIUM_THRESHOLD:
        return _mix(base, (0.90, 0.75, 0.05), 0.5)
    return _mix(base, (0.90, 0.20, 0.15), 0.7)


def render_icon(
    windows: list,
    base_color: tuple,
    show_pct: bool = True,
    warn: bool = False,
    error: bool = False,
) -> cairo.ImageSurface:
    """Render a tray icon with concentric rings.

    windows: list of UsageWindow (shortest window first) or remaining fractions.
    base_color: provider brand RGB tuple.
    """
    size = ICON_SIZE
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surface)
    ctx.set_antialias(cairo.ANTIALIAS_BEST)

    cx = cy = size / 2.0
    pad = 1.5
    max_radius = size / 2.0 - pad

    if warn:
        ctx.arc(cx, cy, max_radius, 0, 2 * math.pi)
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
        return surface

    if error:
        ctx.arc(cx, cy, max_radius, 0, 2 * math.pi)
        ctx.set_source_rgba(0.35, 0.35, 0.35, 0.9)
        ctx.fill()
        ctx.set_source_rgba(1, 1, 1, 0.95)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(size * 0.45)
        extents = ctx.text_extents("?")
        tx = cx - extents.width / 2 - extents.x_bearing
        ty = cy - extents.height / 2 - extents.y_bearing
        ctx.move_to(tx, ty)
        ctx.show_text("?")
        return surface

    # Background
    ctx.arc(cx, cy, max_radius, 0, 2 * math.pi)
    ctx.set_source_rgba(0.1, 0.1, 0.1, 0.85)
    ctx.fill_preserve()
    ctx.set_source_rgba(0.5, 0.5, 0.5, 0.25)
    ctx.set_line_width(1.0)
    ctx.stroke()

    # Normalize windows to remaining fractions
    fractions = []
    for w in windows:
        if hasattr(w, "remaining_percent"):
            fractions.append(max(0.0, min(1.0, w.remaining_percent / 100.0)))
        else:
            fractions.append(max(0.0, min(1.0, float(w))))

    if not fractions:
        fractions = [0.0]

    ring_count = len(fractions)
    ring_width = max(2.0, (max_radius - 4.0) / (ring_count + 0.5))
    start_angle = -math.pi / 2

    for i, frac in enumerate(fractions):
        radius = max_radius - (i * ring_width) - ring_width / 2
        if radius <= 2:
            break
        color = _provider_tinted_color(base_color, frac)
        sweep = 2 * math.pi * frac

        ctx.set_line_width(ring_width - 0.5)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.arc(cx, cy, radius, start_angle, start_angle + sweep)
        ctx.set_source_rgba(*color, 0.95)
        ctx.stroke()

    if show_pct and fractions:
        pct = int(round(fractions[0] * 100))
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


def write_icon_to_file(surface: cairo.ImageSurface, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    surface.write_to_png(str(path))
    return path
