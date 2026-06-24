#!/usr/bin/env python3

import logging
import os
import signal
import sys
import threading
import warnings
from datetime import datetime, timezone

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GLib", "2.0")

from gi.repository import Gtk, Gdk, GLib

warnings.filterwarnings("ignore", message=".*StatusIcon.*deprecated.*")


def _gdk_log_handler(_domain, _level, _message):
    return GLib.LogWriterOutput.HANDLED


for _dom in ("Gdk", "Gdk-WARNING", "Gdk-CRITICAL"):
    GLib.log_set_handler(_dom, GLib.LogLevelFlags.LEVEL_CRITICAL | GLib.LogLevelFlags.LEVEL_WARNING, _gdk_log_handler)


signal.signal(signal.SIGINT, signal.SIG_DFL)

from ai_usage_tray.config import (
    APP_NAME,
    APP_SLUG,
    CACHE_DIR,
    LOG_FILE,
    PROVIDER_COLORS,
    REFRESH_INTERVAL_SECONDS,
)
from ai_usage_tray.icon_renderer import render_icon, surface_to_pixbuf, write_icon_to_file
from ai_usage_tray.providers.base import BaseProvider, ProviderUsage
from ai_usage_tray.providers.registry import instantiate_provider
from ai_usage_tray.settings import Settings
from ai_usage_tray.setup_dialog import SetupDialog
from ai_usage_tray import cache


def _get_indicator_module():
    for mod_name in ("AyatanaAppIndicator3", "AppIndicator3"):
        try:
            gi.require_version(mod_name, "0.1")
            return __import__("gi.repository." + mod_name, fromlist=[mod_name])
        except Exception:
            continue
    return None


AppIndicator = _get_indicator_module()
if AppIndicator:
    Indicator = AppIndicator.Indicator
    IndicatorCategory = AppIndicator.IndicatorCategory
    IndicatorStatus = AppIndicator.IndicatorStatus


def _use_appindicator() -> bool:
    backend = os.environ.get("AI_USAGE_TRAY_TRAY_BACKEND", "statusicon").lower()
    if backend == "appindicator":
        return AppIndicator is not None
    if backend == "auto":
        return AppIndicator is not None
    return False


LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
LOG = logging.getLogger(APP_SLUG)


def _format_reset(ts: int) -> str:
    if not ts:
        return ""
    secs = max(0, (datetime.fromtimestamp(ts, tz=timezone.utc) - datetime.now(timezone.utc)).total_seconds())
    if secs <= 0:
        return "  resets now"
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    if h > 24:
        return f"  resets in {h // 24}d {h % 24}h"
    return f"  resets in {h}h {m}m"


class ProviderIcon:
    def __init__(self, controller, index: int, provider: BaseProvider, initial_usage: ProviderUsage | None = None):
        self.controller = controller
        self.index = index
        self.provider = provider
        self.usage = initial_usage or ProviderUsage(provider_id=provider.id, provider_name=provider.name)
        self.indicator = None
        self.status_icon = None
        self.popup = None
        self._refreshing = False
        self._icon_name = f"{provider.id}-{index}"
        self._icon_path = CACHE_DIR / "icons" / f"{self._icon_name}.png"

        self._ensure_icon(self.usage)

        if _use_appindicator():
            self._build_appindicator()
        else:
            self._build_statusicon()

    def _build_appindicator(self):
        self.indicator = Indicator.new(
            f"{APP_SLUG}-{self.provider.id}-{self.index}",
            self._icon_name,
            IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_icon_theme_path(str(self._icon_path.parent))
        self.indicator.set_title(self.provider.name)
        self.indicator.set_status(IndicatorStatus.ACTIVE)
        self._menu = self._build_menu()
        self.indicator.set_menu(self._menu)
        self._update_label()

    def _build_statusicon(self):
        self.status_icon = Gtk.StatusIcon()
        self.status_icon.set_name(f"{APP_SLUG}-{self.provider.id}-{self.index}")
        self.status_icon.set_tooltip_text(self.provider.name)
        self.status_icon.connect("activate", self._on_left_click)
        self.status_icon.connect("popup-menu", self._on_right_click)
        self._update_statusicon_image()
        self.status_icon.set_visible(True)

    def _build_menu(self):
        menu = Gtk.Menu()

        self._show_item = Gtk.MenuItem(label="Show Usage")
        self._show_item.connect("activate", self._on_show_usage)
        menu.append(self._show_item)

        refresh_item = Gtk.MenuItem(label="Refresh")
        refresh_item.connect("activate", lambda _i: self.refresh())
        menu.append(refresh_item)

        settings_item = Gtk.MenuItem(label="Settings...")
        settings_item.connect("activate", lambda _i: self.controller.open_settings())
        menu.append(settings_item)

        menu.append(Gtk.SeparatorMenuItem())

        remove_item = Gtk.MenuItem(label="Remove Provider")
        remove_item.connect("activate", self._on_remove)
        menu.append(remove_item)

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda _i: self.controller.quit())
        menu.append(quit_item)

        menu.show_all()
        return menu

    def _on_show_usage(self, _item):
        self._show_popup()
        self.refresh()

    def _on_remove(self, _item):
        self.controller.remove_provider(self.index)

    def _on_left_click(self, *_args):
        self._show_popup()
        self.refresh()

    def _on_right_click(self, _icon, button, time):
        menu = self._build_menu()
        menu.popup(None, None, Gtk.StatusIcon.position_menu, self.status_icon, button, time)

    def refresh(self):
        if self._refreshing:
            return
        self._refreshing = True
        threading.Thread(target=self._refresh_thread, daemon=True).start()

    def _refresh_thread(self):
        try:
            usage = self.provider.fetch_usage()
            GLib.idle_add(self._apply_usage, usage)
        except Exception as e:
            LOG.warning(f"Refresh thread error for {self.provider.id}: {e}")
            GLib.idle_add(lambda: setattr(self, "_refreshing", False))

    def _apply_usage(self, usage: ProviderUsage):
        try:
            self.usage = usage
            self._ensure_icon(usage)

            if self.indicator:
                self.indicator.set_icon_theme_path(str(self._icon_path.parent))
                self.indicator.set_icon_full(self._icon_name, self.provider.name)
                self._update_label()
            elif self.status_icon:
                self._update_statusicon_image()
                self.status_icon.set_tooltip_text(self._build_tooltip())

            if self.popup and self.popup.get_visible():
                self._show_popup()

            self.controller.on_provider_updated(self.index, usage)
        except Exception as e:
            LOG.exception(f"Failed to apply usage for {self.provider.id}: {e}")
        finally:
            self._refreshing = False
        return False

    def _ensure_icon(self, usage: ProviderUsage):
        color = PROVIDER_COLORS.get(self.provider.id, self.provider.default_icon_color)
        warn = any(w.limit_reached for w in usage.windows)
        error = bool(usage.error) and not usage.windows
        surface = render_icon(usage.windows, color, warn=warn, error=error)
        write_icon_to_file(surface, self._icon_path)

    def _update_statusicon_image(self):
        color = PROVIDER_COLORS.get(self.provider.id, self.provider.default_icon_color)
        warn = any(w.limit_reached for w in self.usage.windows)
        error = bool(self.usage.error) and not self.usage.windows
        surface = render_icon(self.usage.windows, color, warn=warn, error=error)
        pixbuf = surface_to_pixbuf(surface)
        self.status_icon.set_from_pixbuf(pixbuf)

    def _update_label(self):
        if not self.usage.windows:
            self.indicator.set_label("", "")
            return
        pct = int(round(self.usage.windows[0].remaining_percent))
        self.indicator.set_label(f"{pct}%", "100%")

    def _build_tooltip(self) -> str:
        parts = [self.provider.name]
        if self.usage.error:
            parts.append(f"Error: {self.usage.error}")
        if self.usage.note:
            parts.append(f"({self.usage.note})")
        for w in self.usage.windows:
            parts.append(f"{w.label}: {int(w.remaining_percent)}%")
        if self.usage.last_refreshed:
            parts.append(f"Updated: {self.usage.last_refreshed}")
        return "  ".join(parts)

    def _show_popup(self):
        try:
            self._do_show_popup()
        except Exception as e:
            LOG.exception(f"Failed to show popup for {self.provider.id}: {e}")

    def _do_show_popup(self):
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
        self.popup.connect(
            "key-press-event",
            lambda w, e: self._hide_popup() if e.keyval == Gdk.keyval_from_name("Escape") else None,
        )
        self.popup.set_keep_above(True)
        self.popup.set_accept_focus(True)
        self.popup.set_focus_on_map(True)
        self.popup.set_skip_taskbar_hint(True)
        self.popup.set_skip_pager_hint(True)

        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.OUT)
        self.popup.add(frame)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_top(8)
        vbox.set_margin_bottom(8)
        frame.add(vbox)

        usage = self.usage

        plan_label = f" — {GLib.markup_escape_text(usage.plan_type.title())}" if usage.plan_type else ""
        header_box = Gtk.Box(spacing=0)
        header = Gtk.Label()
        header.set_markup(f"<b>{GLib.markup_escape_text(self.provider.name)}</b>{plan_label}")
        header.set_xalign(0)
        header_box.pack_start(header, True, True, 0)
        close_btn = Gtk.Button(label="\u2715")
        close_btn.set_relief(Gtk.ReliefStyle.NONE)
        close_btn.set_focus_on_click(False)
        close_btn.connect("clicked", lambda *a: self._hide_popup())
        header_box.pack_end(close_btn, False, False, 0)
        vbox.pack_start(header_box, False, False, 2)
        vbox.pack_start(Gtk.Separator(), False, False, 4)

        if usage.error:
            err_lbl = Gtk.Label()
            err_lbl.set_markup(f'<span foreground="red">{GLib.markup_escape_text(usage.error)}</span>')
            err_lbl.set_xalign(0)
            err_lbl.set_line_wrap(True)
            vbox.pack_start(err_lbl, False, False, 0)

        if usage.note:
            note_lbl = Gtk.Label(label=f"({usage.note})")
            note_lbl.get_style_context().add_class("dim-label")
            note_lbl.set_xalign(0)
            vbox.pack_start(note_lbl, False, False, 0)

        for w in usage.windows:
            vbox.pack_start(self._bar_row(w), False, False, 4)

        if usage.windows:
            vbox.pack_start(Gtk.Separator(), False, False, 4)

        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(2)
        items = [
            ("Total tokens", f"{usage.total_tokens:,}"),
            ("Weekly tokens", f"{usage.weekly_tokens:,}"),
            ("Sessions", str(usage.session_count)),
        ]
        for row, (lbl_text, val_text) in enumerate(items):
            lbl = Gtk.Label(label=lbl_text, xalign=0)
            lbl.get_style_context().add_class("dim-label")
            val = Gtk.Label(label=val_text, xalign=1)
            grid.attach(lbl, 0, row, 1, 1)
            grid.attach(val, 1, row, 1, 1)
        vbox.pack_start(grid, False, False, 0)

        if any(w.limit_reached for w in usage.windows):
            vbox.pack_start(Gtk.Separator(), False, False, 4)
            warn = Gtk.Label()
            warn.set_markup('<span foreground="red"><b>Usage limit reached!</b></span>')
            vbox.pack_start(warn, False, False, 0)

        if usage.sessions:
            vbox.pack_start(Gtk.Separator(), False, False, 4)
            recent = Gtk.Label()
            recent.set_markup("<b>Recent Sessions</b>")
            recent.set_xalign(0)
            vbox.pack_start(recent, False, False, 0)
            for s in usage.sessions[:5]:
                t = s.get("title", "Untitled")[:42]
                tok = s.get("tokens", 0)
                d = s.get("date", "")
                txt = f"  {t}  {d}  {tok:,} tok"
                lbl = Gtk.Label(label=txt, xalign=0, ellipsize=True)
                lbl.get_style_context().add_class("dim-label")
                vbox.pack_start(lbl, False, False, 0)

        vbox.pack_start(Gtk.Separator(), False, False, 4)

        if usage.last_refreshed:
            refreshed_lbl = Gtk.Label(label=f"Last refreshed: {usage.last_refreshed}", xalign=0)
            refreshed_lbl.get_style_context().add_class("dim-label")
            vbox.pack_start(refreshed_lbl, False, False, 0)

        btn_box = Gtk.Box(spacing=6)

        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.connect("clicked", lambda *a: self.refresh())
        btn_box.pack_start(refresh_btn, False, False, 0)

        dash_btn = Gtk.Button(label="Open Dashboard")
        dash_btn.connect("clicked", lambda *a: self._open_dashboard())
        btn_box.pack_start(dash_btn, False, False, 0)

        quit_btn = Gtk.Button(label="Quit")
        quit_btn.connect("clicked", lambda *a: self.controller.quit())
        btn_box.pack_end(quit_btn, False, False, 0)

        vbox.pack_start(btn_box, False, False, 0)

        self._position_popup()
        self.popup.show_all()
        self.popup.present_with_time(Gdk.CURRENT_TIME)
        self.popup.grab_focus()

    def _bar_row(self, w) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        label = Gtk.Label(label=w.label, xalign=0)
        label.get_style_context().add_class("dim-label")
        row.pack_start(label, False, False, 0)

        bar_box = Gtk.Box(spacing=6)
        bar = Gtk.LevelBar()
        bar.set_min_value(0)
        bar.set_max_value(1)
        remaining_frac = max(0.0, min(1.0, w.remaining_percent / 100))
        bar.set_value(remaining_frac)
        bar.set_size_request(200, -1)
        bar.add_offset_value("low", 0.25)
        bar.add_offset_value("high", 0.75)
        bar_box.pack_start(bar, False, False, 0)

        remaining = max(0, int(round(w.remaining_percent)))
        pct_lbl = Gtk.Label()
        pct_lbl.set_markup(f"<b>{remaining}%</b> left")
        pct_lbl.set_xalign(0)
        pct_lbl.set_size_request(60, -1)
        bar_box.pack_start(pct_lbl, False, False, 0)

        reset_lbl = Gtk.Label(label=_format_reset(w.reset_at), xalign=0)
        reset_lbl.get_style_context().add_class("dim-label")
        bar_box.pack_start(reset_lbl, False, False, 0)

        row.pack_start(bar_box, False, False, 0)
        return row

    def _position_popup(self):
        popup = self.popup
        if not popup:
            return

        display = Gdk.Display.get_default()

        if self.status_icon:
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
                popup.move(max(0, int(px)), max(0, int(py)))
                return

        # AppIndicator / fallback: position near pointer.
        try:
            seat = display.get_default_seat()
            pointer = seat.get_pointer()
            screen = display.get_default_screen()
            px, py = pointer.get_position(screen)
            popup.move(max(0, int(px) - 180), max(0, int(py) - 50))
        except Exception:
            monitor = display.get_primary_monitor() or display.get_monitor(0)
            geo = monitor.get_geometry()
            popup.move(geo.x + geo.width - 380, geo.y + geo.height - 320)

    def _open_dashboard(self):
        url = self.provider.dashboard_url()
        if url:
            import webbrowser

            webbrowser.open(url)
        self._hide_popup()

    def _hide_popup(self):
        if self.popup:
            self.popup.destroy()
            self.popup = None

    def destroy(self):
        self._hide_popup()
        if self.indicator:
            self.indicator.set_status(IndicatorStatus.PASSIVE)
        if self.status_icon:
            self.status_icon.set_visible(False)


class ControlIcon:
    """Tray icon shown when no providers are configured."""

    def __init__(self, controller):
        self.controller = controller
        self.indicator = None
        self.status_icon = None

        if _use_appindicator():
            self.indicator = Indicator.new(
                f"{APP_SLUG}-control",
                "utilities-system-monitor",
                IndicatorCategory.APPLICATION_STATUS,
            )
            self.indicator.set_title(APP_NAME)
            self.indicator.set_status(IndicatorStatus.ACTIVE)
            self.indicator.set_menu(self._build_menu())
        else:
            self.status_icon = Gtk.StatusIcon()
            self.status_icon.set_name(f"{APP_SLUG}-control")
            self.status_icon.set_tooltip_text(APP_NAME)
            self.status_icon.set_from_icon_name("utilities-system-monitor")
            self.status_icon.connect("activate", self._on_activate)
            self.status_icon.connect("popup-menu", self._on_right_click)
            self.status_icon.set_visible(True)

    def _build_menu(self):
        menu = Gtk.Menu()

        add_item = Gtk.MenuItem(label="Add Provider...")
        add_item.connect("activate", lambda _i: self.controller.open_settings())
        menu.append(add_item)

        refresh_item = Gtk.MenuItem(label="Refresh All")
        refresh_item.connect("activate", lambda _i: self.controller.refresh_all())
        menu.append(refresh_item)

        settings_item = Gtk.MenuItem(label="Settings...")
        settings_item.connect("activate", lambda _i: self.controller.open_settings())
        menu.append(settings_item)

        menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda _i: self.controller.quit())
        menu.append(quit_item)

        menu.show_all()
        return menu

    def _on_activate(self, *_args):
        self.controller.open_settings()

    def _on_right_click(self, _icon, button, time):
        menu = self._build_menu()
        menu.popup(None, None, Gtk.StatusIcon.position_menu, self.status_icon, button, time)

    def destroy(self):
        if self.indicator:
            self.indicator.set_status(IndicatorStatus.PASSIVE)
        if self.status_icon:
            self.status_icon.set_visible(False)


class TrayController:
    def __init__(self):
        self.settings = Settings()
        self.provider_icons: list[ProviderIcon] = []
        self.control_icon: ControlIcon | None = None
        self._setup_dialog = None
        self._timer_id = None

        self._load_providers()

        if not self.provider_icons:
            self.control_icon = ControlIcon(self)

        GLib.timeout_add_seconds(REFRESH_INTERVAL_SECONDS, self._on_timer)
        LOG.info("Started %s", APP_NAME)

    def _load_providers(self):
        # Remove existing provider icons.
        for icon in self.provider_icons:
            icon.destroy()
        self.provider_icons = []

        env_filter = self.settings.provider_ids_from_env()
        for idx, cfg in enumerate(self.settings.providers):
            type_id = cfg.get("type")
            if env_filter is not None and type_id not in env_filter:
                continue
            try:
                provider = instantiate_provider(type_id, cfg)
            except Exception as e:
                LOG.warning(f"Failed to instantiate provider {type_id}: {e}")
                continue
            icon = ProviderIcon(self, idx, provider)
            self.provider_icons.append(icon)
            icon.refresh()

    def _on_timer(self):
        self.refresh_all()
        return True

    def refresh_all(self):
        for icon in self.provider_icons:
            icon.refresh()

    def open_settings(self):
        if self._setup_dialog is None:
            self._setup_dialog = SetupDialog(self.settings, on_changed=self._on_settings_changed)
        self._setup_dialog.show()

    def _on_settings_changed(self):
        # Rebuild provider icons from config.
        for icon in self.provider_icons:
            icon.destroy()
        self.provider_icons = []

        if self.control_icon:
            self.control_icon.destroy()
            self.control_icon = None

        self._load_providers()

        if not self.provider_icons and not self.control_icon:
            self.control_icon = ControlIcon(self)

    def remove_provider(self, index: int):
        self.settings.remove_provider(index)
        self._on_settings_changed()

    def on_provider_updated(self, index: int, usage: ProviderUsage):
        # Persist cache on each update.
        try:
            usages = [icon.usage for icon in self.provider_icons]
            cache.save_cache(usages)
        except Exception as e:
            LOG.warning(f"Failed to save cache: {e}")

    def quit(self):
        for icon in self.provider_icons:
            icon.destroy()
        if self.control_icon:
            self.control_icon.destroy()
        LOG.info("Stopped %s", APP_NAME)
        Gtk.main_quit()


def main():
    Gtk.init(sys.argv)

    # Load cached usage so initial icons are not empty.
    cached = cache.load_cache()
    cache_by_id = {u.provider_id: u for u in cached}

    controller = TrayController()

    # Apply cached usage to icons before first refresh.
    for icon in controller.provider_icons:
        if icon.provider.id in cache_by_id:
            icon._apply_usage(cache_by_id[icon.provider.id])

    Gtk.main()


if __name__ == "__main__":
    main()
