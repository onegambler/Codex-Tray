import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ai_usage_tray.providers.registry import list_provider_types
from ai_usage_tray.settings import Settings


class SetupDialog:
    def __init__(self, settings: Settings, on_changed=None):
        self.settings = settings
        self.on_changed = on_changed
        self.window = None

    def show(self, parent=None):
        if self.window:
            self.window.present()
            return

        self.window = Gtk.Window(title="AI Usage Tray — Settings")
        self.window.set_default_size(420, 280)
        self.window.set_border_width(12)
        if parent:
            self.window.set_transient_for(parent)
            self.window.set_modal(True)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.window.add(vbox)

        header = Gtk.Label()
        header.set_markup("<b>Configured Providers</b>")
        header.set_xalign(0)
        vbox.pack_start(header, False, False, 0)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.listbox)
        vbox.pack_start(scrolled, True, True, 0)

        self._refresh_list()

        btn_box = Gtk.Box(spacing=6)
        add_btn = Gtk.Button(label="Add Provider...")
        add_btn.connect("clicked", self._on_add)
        btn_box.pack_start(add_btn, False, False, 0)

        close_btn = Gtk.Button(label="Close")
        close_btn.connect("clicked", self._on_close)
        btn_box.pack_end(close_btn, False, False, 0)

        vbox.pack_start(btn_box, False, False, 0)

        self.window.connect("destroy", lambda *a: setattr(self, "window", None))
        self.window.show_all()

    def _refresh_list(self):
        for child in self.listbox.get_children():
            self.listbox.remove(child)

        providers = self.settings.providers
        if not providers:
            row = Gtk.ListBoxRow()
            lbl = Gtk.Label(label="No providers configured.")
            lbl.set_sensitive(False)
            row.add(lbl)
            self.listbox.add(row)
        else:
            for idx, cfg in enumerate(providers):
                row = Gtk.ListBoxRow()
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                hbox.set_margin_start(8)
                hbox.set_margin_end(8)
                hbox.set_margin_top(6)
                hbox.set_margin_bottom(6)

                type_id = cfg.get("type", "unknown")
                name = next(
                    (p["name"] for p in list_provider_types() if p["id"] == type_id),
                    type_id,
                )
                lbl = Gtk.Label(label=name)
                lbl.set_xalign(0)
                hbox.pack_start(lbl, True, True, 0)

                remove_btn = Gtk.Button(label="Remove")
                remove_btn.connect("clicked", lambda _b, i=idx: self._on_remove(i))
                hbox.pack_start(remove_btn, False, False, 0)

                row.add(hbox)
                self.listbox.add(row)

        self.listbox.show_all()

    def _on_remove(self, index: int):
        self.settings.remove_provider(index)
        self._refresh_list()
        if self.on_changed:
            self.on_changed()

    def _on_add(self, _btn):
        AddProviderDialog(self.settings, on_added=self._on_added).show(self.window)

    def _on_added(self):
        self._refresh_list()
        if self.on_changed:
            self.on_changed()

    def _on_close(self, _btn):
        self.window.destroy()


class AddProviderDialog:
    def __init__(self, settings: Settings, on_added=None):
        self.settings = settings
        self.on_added = on_added
        self.window = None
        self.fields_box = None
        self.type_combo = None
        self.entries: dict[str, Gtk.Entry] = {}

    def show(self, parent=None):
        self.window = Gtk.Window(title="Add Provider")
        self.window.set_default_size(360, -1)
        self.window.set_border_width(12)
        if parent:
            self.window.set_transient_for(parent)
            self.window.set_modal(True)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.window.add(vbox)

        type_box = Gtk.Box(spacing=6)
        type_box.pack_start(Gtk.Label(label="Provider:"), False, False, 0)
        self.type_combo = Gtk.ComboBoxText()
        for p in list_provider_types():
            self.type_combo.append(p["id"], p["name"])
        self.type_combo.set_active(0)
        self.type_combo.connect("changed", self._on_type_changed)
        type_box.pack_start(self.type_combo, True, True, 0)
        vbox.pack_start(type_box, False, False, 0)

        self.fields_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.pack_start(self.fields_box, False, False, 0)

        self._render_fields()

        btn_box = Gtk.Box(spacing=6)
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _b: self.window.destroy())
        btn_box.pack_end(cancel_btn, False, False, 0)
        add_btn = Gtk.Button(label="Add")
        add_btn.connect("clicked", self._on_save)
        btn_box.pack_end(add_btn, False, False, 0)
        vbox.pack_start(btn_box, False, False, 0)

        self.window.show_all()

    def _on_type_changed(self, _combo):
        self._render_fields()

    def _render_fields(self):
        for child in self.fields_box.get_children():
            self.fields_box.remove(child)
        self.entries.clear()

        type_id = self.type_combo.get_active_id()
        if not type_id:
            return

        provider_types = list_provider_types()
        info = next((p for p in provider_types if p["id"] == type_id), None)
        if not info:
            return

        for field in info["schema"]:
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            lbl = Gtk.Label()
            lbl.set_markup(f"<b>{field['label']}</b>")
            lbl.set_xalign(0)
            row.pack_start(lbl, False, False, 0)

            entry = Gtk.Entry()
            if field.get("type") == "password":
                entry.set_visibility(False)
                entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
            self.entries[field["key"]] = entry
            row.pack_start(entry, False, False, 0)

            if field.get("help"):
                help_lbl = Gtk.Label(label=field["help"])
                help_lbl.set_xalign(0)
                help_lbl.set_line_wrap(True)
                help_lbl.get_style_context().add_class("dim-label")
                row.pack_start(help_lbl, False, False, 0)

            self.fields_box.pack_start(row, False, False, 0)

        self.fields_box.show_all()

    def _on_save(self, _btn):
        type_id = self.type_combo.get_active_id()
        if not type_id:
            return

        config = {}
        provider_types = list_provider_types()
        info = next((p for p in provider_types if p["id"] == type_id), None)
        if info:
            for field in info["schema"]:
                key = field["key"]
                value = self.entries.get(key, Gtk.Entry()).get_text().strip()
                if field.get("required") and not value:
                    self._show_error(f"{field['label']} is required.")
                    return
                config[key] = value

        self.settings.add_provider(type_id, config)
        self.window.destroy()
        if self.on_added:
            self.on_added()

    def _show_error(self, message: str):
        dialog = Gtk.MessageDialog(
            parent=self.window,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            message_format=message,
        )
        dialog.run()
        dialog.destroy()
