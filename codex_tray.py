#!/usr/bin/env python3

import sys
import os
import warnings
import webbrowser
import signal
import logging
import threading
from datetime import datetime, timezone

signal.signal(signal.SIGINT, signal.SIG_DFL)

logging.basicConfig(
    filename=os.path.expanduser("~/.cache/codex-tray.log"),
    level=logging.INFO, format="%(asctime)s %(message)s",
)
LOG = logging.getLogger("codex-tray")

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gtk, GLib, Gdk

warnings.filterwarnings("ignore", message=".*StatusIcon.*deprecated.*")

glib_log_domains = ["Gdk", "Gdk-WARNING", "Gdk-CRITICAL"]
for dom in glib_log_domains:
    GLib.log_set_handler(dom, GLib.LogLevelFlags.LEVEL_CRITICAL | GLib.LogLevelFlags.LEVEL_WARNING, lambda *a: None)

from config import REFRESH_INTERVAL_SECONDS, USAGE_LIMIT_HOURS, AUTH_JSON
from usage_tracker import read_usage
from icon_renderer import render_icon, surface_to_pixbuf


class CodexTrayApp:
    def __init__(self):
        self.popup = None
        self.stats = None
        self.status_icon = Gtk.StatusIcon()
        self.status_icon.set_name("codex-tray")
        self.status_icon.set_tooltip_text("Codex Usage Monitor")
        self.status_icon.connect("activate", self.on_left_click)
        self.status_icon.connect("popup-menu", self.on_right_click)

        surface = render_icon(0.5, show_pct=False)
        pixbuf = surface_to_pixbuf(surface)
        self.status_icon.set_from_pixbuf(pixbuf)
        self.status_icon.set_visible(True)

        GLib.idle_add(self._first_refresh)
        LOG.info("Started")
        GLib.timeout_add_seconds(REFRESH_INTERVAL_SECONDS, self._on_timer)

    def _first_refresh(self):
        self.stats = self._fetch_stats()
        self._apply_stats(self.stats)
        self.status_icon.set_visible(True)
        if not self.stats.error:
            pct = max(0, 100 - int(self.stats.used_percent))
            LOG.info(f"Loaded: {pct}% remaining (5h), {self.stats.secondary_used}% (7d), {self.stats.thread_count} sessions")
        return False

    def _fetch_stats(self):
        try:
            return read_usage()
        except Exception as e:
            from usage_tracker import UsageStats
            LOG.warning(f"Fetch error: {e}")
            return UsageStats(error=str(e))

    def _apply_stats(self, stats):
        if stats.error and self.stats is not None:
            LOG.warning(f"Refresh failed, keeping data from {self.stats.last_refreshed or 'earlier'}")
            if self.popup and self.popup.get_visible():
                self._show_popup(self.stats)
            return

        self.stats = stats
        remaining = max(0.0, min(1.0, stats.remaining_hours / USAGE_LIMIT_HOURS))
        warn = stats.primary_limit or stats.secondary_limit
        surface = render_icon(remaining, warn=warn)
        pixbuf = surface_to_pixbuf(surface)
        self.status_icon.set_from_pixbuf(pixbuf)

        pct = max(0, 100 - int(stats.used_percent))
        parts = [f"Codex: {pct}% remaining (5h)"]
        parts.append(f"{max(0, 100 - stats.secondary_used)}% remaining (7d)")
        if stats.primary_limit:
            parts.append("5h limit reached!")
        elif stats.secondary_limit:
            parts.append("Weekly limit reached!")
        if stats.last_refreshed:
            parts.append(f"Updated: {stats.last_refreshed}")
        self.status_icon.set_tooltip_text("  ".join(parts))

        if self.popup and self.popup.get_visible():
            self._show_popup(stats)

    def _refresh_bg(self):
        threading.Thread(target=self._refresh_thread, daemon=True).start()

    def _refresh_thread(self):
        stats = self._fetch_stats()
        GLib.idle_add(lambda: (self._apply_stats(stats), False)[1])

    def _on_timer(self):
        self._refresh_bg()
        return True

    def on_left_click(self, *_args):
        if self.popup and self.popup.get_visible():
            self._hide_popup()
            return
        if self.stats:
            self._show_popup(self.stats)
        else:
            self._show_popup(self._fetch_stats())
        self._refresh_bg()

    def _hide_popup(self):
        if self.popup:
            self.popup.destroy()
            self.popup = None

    def _show_popup(self, stats):
        self._hide_popup()

        self.popup = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.popup.set_decorated(False)
        self.popup.set_resizable(False)
        self.popup.set_border_width(0)
        self.popup.set_default_size(360, -1)
        self.popup.set_position(Gtk.WindowPosition.NONE)
        self.popup.set_type_hint(Gdk.WindowTypeHint.DROPDOWN_MENU)

        self.popup.connect("destroy", lambda *a: setattr(self, "popup", None))
        self.popup.connect("focus-out-event", lambda w, e: self._hide_popup())
        self.popup.connect("key-press-event", lambda w, e: self._hide_popup() if e.keyval == Gdk.keyval_from_name("Escape") else None)
        self.popup.set_keep_above(True)

        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.OUT)
        self.popup.add(frame)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_top(8)
        vbox.set_margin_bottom(8)
        frame.add(vbox)

        if stats.error:
            lbl = Gtk.Label(label="API unavailable — showing local data", xalign=0)
            lbl.get_style_context().add_class("dim-label")
            vbox.pack_start(lbl, False, False, 0)
            vbox.pack_start(Gtk.Separator(), False, False, 4)
            grid = Gtk.Grid()
            grid.set_column_spacing(12)
            grid.set_row_spacing(2)
            items = [
                ("Total tokens", f"{stats.total_tokens:,}"),
                ("Weekly tokens", f"{stats.weekly_tokens:,}"),
                ("Sessions", str(stats.thread_count)),
            ]
            for row, (lbl_text, val_text) in enumerate(items):
                lbl = Gtk.Label(label=lbl_text, xalign=0)
                lbl.get_style_context().add_class("dim-label")
                val = Gtk.Label(label=val_text, xalign=1)
                grid.attach(lbl, 0, row, 1, 1)
                grid.attach(val, 1, row, 1, 1)
            vbox.pack_start(grid, False, False, 0)
            btn = Gtk.Button(label="Retry")
            btn.connect("clicked", lambda *a: self._refresh_bg())
            vbox.pack_start(btn, False, False, 0)
            self._finish_popup(vbox)
            return

        plan_label = f"ChatGPT {stats.plan_type.title()}" if stats.plan_type else "Codex"
        header_box = Gtk.Box(spacing=0)
        header = Gtk.Label()
        header.set_markup(f"<b>Codex Usage</b>  —  {plan_label}")
        header.set_xalign(0)
        header_box.pack_start(header, True, True, 0)
        close_btn = Gtk.Button(label="\u2715")
        close_btn.set_relief(Gtk.ReliefStyle.NONE)
        close_btn.set_focus_on_click(False)
        close_btn.connect("clicked", lambda *a: self._hide_popup())
        header_box.pack_end(close_btn, False, False, 0)
        vbox.pack_start(header_box, False, False, 2)

        vbox.pack_start(Gtk.Separator(), False, False, 4)

        def _format_reset(ts: int) -> str:
            if not ts:
                return ""
            secs = max(0, (datetime.fromtimestamp(ts, tz=timezone.utc) - datetime.now(timezone.utc)).total_seconds())
            if secs <= 0:
                return "  resets now"
            h = int(secs // 3600)
            m = int((secs % 3600) // 60)
            if h > 24:
                return f"  resets in {h//24}d {h%24}h"
            return f"  resets in {h}h {m}m"

        def _bar_row(name: str, used_pct: float, reset_ts: int) -> Gtk.Box:
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            label = Gtk.Label(label=name, xalign=0)
            label.get_style_context().add_class("dim-label")
            row.pack_start(label, False, False, 0)

            bar_box = Gtk.Box(spacing=6)
            bar = Gtk.LevelBar()
            bar.set_min_value(0)
            bar.set_max_value(1)
            remaining_frac = max(0.0, min(1.0, 1 - used_pct / 100))
            bar.set_value(remaining_frac)
            bar.set_size_request(200, -1)
            bar.add_offset_value("low", 0.25)
            bar.add_offset_value("high", 0.75)
            bar_box.pack_start(bar, False, False, 0)

            remaining = max(0, int(round(100 - used_pct)))
            pct_lbl = Gtk.Label()
            pct_lbl.set_markup(f"<b>{remaining}%</b> left")
            pct_lbl.set_xalign(0)
            pct_lbl.set_size_request(60, -1)
            bar_box.pack_start(pct_lbl, False, False, 0)

            reset_lbl = Gtk.Label(label=_format_reset(reset_ts), xalign=0)
            reset_lbl.get_style_context().add_class("dim-label")
            bar_box.pack_start(reset_lbl, False, False, 0)

            row.pack_start(bar_box, False, False, 0)
            return row

        vbox.pack_start(_bar_row("5-hour rolling window", stats.used_percent, stats.reset_at), False, False, 4)
        vbox.pack_start(_bar_row("Weekly (7d rolling)", stats.secondary_used, stats.secondary_reset_at), False, False, 4)

        vbox.pack_start(Gtk.Separator(), False, False, 4)

        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(2)

        items = [
            ("Total tokens", f"{stats.total_tokens:,}"),
            ("Weekly tokens", f"{stats.weekly_tokens:,}"),
            ("Sessions", str(stats.thread_count)),
        ]
        for row, (lbl_text, val_text) in enumerate(items):
            lbl = Gtk.Label(label=lbl_text, xalign=0)
            lbl.get_style_context().add_class("dim-label")
            val = Gtk.Label(label=val_text, xalign=1)
            grid.attach(lbl, 0, row, 1, 1)
            grid.attach(val, 1, row, 1, 1)
        vbox.pack_start(grid, False, False, 0)

        if stats.primary_limit or stats.secondary_limit:
            vbox.pack_start(Gtk.Separator(), False, False, 4)
            warn = Gtk.Label()
            if stats.primary_limit:
                warn.set_markup('<span foreground="red"><b>5-hour limit reached!</b></span>')
            else:
                warn.set_markup('<span foreground="red"><b>Weekly limit reached!</b></span>')
            vbox.pack_start(warn, False, False, 0)

        if stats.sessions:
            vbox.pack_start(Gtk.Separator(), False, False, 4)
            recent = Gtk.Label()
            recent.set_markup("<b>Recent Sessions</b>")
            recent.set_xalign(0)
            vbox.pack_start(recent, False, False, 0)

            for s in stats.sessions[:5]:
                t = s["title"][:42]
                tok = s["tokens"]
                d = s["date"]
                txt = f"  {t}  {d}  {tok:,} tok"
                lbl = Gtk.Label(label=txt, xalign=0, ellipsize=True)
                lbl.get_style_context().add_class("dim-label")
                vbox.pack_start(lbl, False, False, 0)

        self._finish_popup(vbox)

    def _finish_popup(self, vbox):
        vbox.pack_start(Gtk.Separator(), False, False, 4)

        if self.stats and self.stats.last_refreshed:
            refreshed_lbl = Gtk.Label(label=f"Last refreshed: {self.stats.last_refreshed}", xalign=0)
            refreshed_lbl.get_style_context().add_class("dim-label")
            vbox.pack_start(refreshed_lbl, False, False, 0)

        btn_box = Gtk.Box(spacing=6)

        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.connect("clicked", lambda *a: self._refresh_bg())
        btn_box.pack_start(refresh_btn, False, False, 0)

        dash_btn = Gtk.Button(label="Open Dashboard")
        dash_btn.connect("clicked", lambda *a: self._open_dashboard())
        btn_box.pack_start(dash_btn, False, False, 0)

        quit_btn = Gtk.Button(label="Quit")
        quit_btn.connect("clicked", lambda *a: self._quit())
        btn_box.pack_end(quit_btn, False, False, 0)

        vbox.pack_start(btn_box, False, False, 0)
        self._position_popup()
        self.popup.show_all()

    def _position_popup(self):
        popup = self.popup
        if not popup:
            return

        display = Gdk.Display.get_default()
        result = self.status_icon.get_geometry()
        if result and result[0]:
            rect = result[2]
            monitor = display.get_monitor_at_point(rect.x, rect.y)
            monitor_geo = monitor.get_geometry()
            min_h, pref_h = popup.get_preferred_height()
            popup_height = max(pref_h, 300)

            if rect.y + rect.height > monitor_geo.y + monitor_geo.height // 2:
                px = rect.x
                py = rect.y - popup_height - 4
            else:
                px = rect.x
                py = rect.y + rect.height + 4
        else:
            monitor = display.get_primary_monitor()
            if not monitor:
                monitor = display.get_monitor(0)
            geo = monitor.get_geometry()
            px = geo.x + geo.width - 380
            py = geo.y + geo.height - 320

        popup.move(max(0, int(px)), max(0, int(py)))

    def _open_dashboard(self):
        webbrowser.open("https://chatgpt.com/codex/settings/usage")
        self._hide_popup()

    def on_right_click(self, _icon, _button, _time):
        menu = Gtk.Menu()

        refresh_item = Gtk.ImageMenuItem(label="_Refresh", use_underline=True)
        refresh_item.connect("activate", lambda *a: self._refresh_bg())
        menu.append(refresh_item)

        dash_item = Gtk.ImageMenuItem(label="_Open Dashboard", use_underline=True)
        dash_item.connect("activate", lambda *a: self._open_dashboard())
        menu.append(dash_item)

        menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.ImageMenuItem(label="_Quit", use_underline=True)
        quit_item.connect("activate", lambda *a: self._quit())
        menu.append(quit_item)

        menu.show_all()
        menu.popup(None, None, Gtk.StatusIcon.position_menu, self.status_icon, _button, _time)

    def _quit(self):
        self._hide_popup()
        LOG.info("Stopped")
        Gtk.main_quit()


def main():
    Gtk.init(sys.argv)

    if not AUTH_JSON.exists():
        dialog = Gtk.MessageDialog(
            parent=None,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            message_format="Codex CLI Login Required",
        )
        dialog.format_secondary_text(
            "This tray app needs Codex CLI to be installed and logged in.\n\n"
            "1. Install Codex CLI:\n"
            "   npm install -g @openai/codex\n\n"
            "2. Log in:\n"
            "   codex\n\n"
            "3. After logging in, restart this app."
        )
        dialog.run()
        dialog.destroy()
        return 1

    CodexTrayApp()
    Gtk.main()


if __name__ == "__main__":
    main()
