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


def _remaining_fraction(window) -> float:
    if hasattr(window, "remaining_percent"):
        return max(0.0, min(1.0, window.remaining_percent / 100.0))
    return max(0.0, min(1.0, float(window)))


def _display_percent(windows: list) -> int:
    if not windows:
        return 0
    return int(round(_remaining_fraction(windows[0]) * 100))


def _badge_level(windows: list) -> str | None:
    for window in windows[1:]:
        remaining = _remaining_fraction(window)
        if getattr(window, "limit_reached", False) or remaining < MEDIUM_THRESHOLD:
            return "low"
    for window in windows[1:]:
        if _remaining_fraction(window) < HIGH_THRESHOLD:
            return "medium"
    return None


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
    fractions = [_remaining_fraction(w) for w in windows]

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
        pct = _display_percent(windows)
        text = str(pct)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        font_size = size * (0.58 if pct >= 100 else 0.66)
        max_text_width = size * 0.76
        while True:
            ctx.set_font_size(font_size)
            extents = ctx.text_extents(text)
            if extents.width <= max_text_width or font_size <= size * 0.42:
                break
            font_size -= 1
        tw = extents.width
        th = extents.height
        tx = cx - tw / 2 - extents.x_bearing
        ty = cy - th / 2 - extents.y_bearing

        ctx.arc(cx, cy, size * 0.18, 0, 2 * math.pi)
        ctx.set_source_rgba(0, 0, 0, 0.6)
        ctx.fill()

        ctx.move_to(tx, ty)
        ctx.set_source_rgba(1, 1, 1, 0.95)
        ctx.show_text(text)

    badge = _badge_level(windows)
    if badge:
        bx = size * 0.83
        by = size * 0.17
        br = size * 0.12
        color = (0.90, 0.20, 0.15) if badge == "low" else (0.90, 0.75, 0.05)
        ctx.arc(bx, by, br + 1.0, 0, 2 * math.pi)
        ctx.set_source_rgba(0, 0, 0, 0.9)
        ctx.fill()
        ctx.arc(bx, by, br, 0, 2 * math.pi)
        ctx.set_source_rgba(*color, 0.98)
        ctx.fill()

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
