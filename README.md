# AI Usage Tray

Linux system-tray monitor for AI coding assistant usage. Shows remaining usage limits at a glance for multiple providers, starting with [Codex CLI](https://github.com/openai/codex) and [OpenCode Go](https://opencode.ai/go).

## Features

- **Multi-provider** — add one or more providers; each gets its own tray icon.
- **Concentric rings** — each ring represents a usage window (5-hour, weekly, monthly); the center text shows the shortest-window remaining percentage.
- **Modern tray backend** — uses Ayatana/AppIndicator when available, falling back to the legacy `Gtk.StatusIcon` only when necessary.
- **Generic setup UI** — add and remove providers through a GTK settings dialog.
- **Local caching** — last known usage is persisted so icons show data immediately after restart.

## Install

### Debian / Ubuntu (one-click)

Download the latest `.deb` from [Releases](https://github.com/anomalyco/tray-app/releases/latest) and double-click to install.

### Other Linux distros

```bash
git clone https://github.com/anomalyco/tray-app.git
cd tray-app
./install.sh
```

## Prerequisites

System packages (installed automatically by `install.sh` where possible):

- `python3-gi`
- `python3-gi-cairo`
- `gir1.2-gtk-3.0`

Optional:

- `gir1.2-ayatanaappindicator3-0.1` or `gir1.2-appindicator3-0.1` (only if you enable AppIndicator mode)

### Provider setup

**Codex**

Install and log in to Codex CLI at least once:

```bash
npm install -g @openai/codex
codex
```

The tray app auto-detects `~/.codex/auth.json` on first run.

**OpenCode Go**

OpenCode Go quota is read from the OpenCode dashboard. Open the dashboard in your browser, copy the workspace ID from the URL (`/workspace/<id>/go`) and the value of the `auth` cookie, then add the provider in the tray settings dialog.

The tray also falls back to a local estimate from `~/.local/share/opencode/opencode.db` when dashboard credentials are not configured.

## Usage

```bash
ai-usage-tray
```

Run it in the background:

```bash
ai-usage-tray &
```

Right-click any icon for the menu, or left-click an AppIndicator icon to open its menu and select **Show Usage**.

### Environment overrides

Limit which configured providers are active:

```bash
AI_USAGE_TRAY_PROVIDERS=codex,opencode-go ai-usage-tray
```

Force the tray backend. The default is `statusicon` because AppIndicator menus render as black boxes on some desktops/panels:

```bash
AI_USAGE_TRAY_TRAY_BACKEND=appindicator ai-usage-tray   # or statusicon, auto
```

## What the popup shows

- **Usage bars** — remaining percentage for each provider window.
- **Session stats** — total tokens, weekly tokens, session count.
- **Recent sessions** — last 5 sessions with title, token count, and date.
- **Last refreshed** — timestamp of the most recent successful fetch.

## Notes

- **Wayland / GNOME** — Ayatana/AppIndicator requires a compatible panel or the AppIndicator extension on vanilla GNOME. The legacy `Gtk.StatusIcon` fallback is kept for older desktops but is deprecated.
- **Logs** — written to `~/.cache/ai-usage-tray/ai-usage-tray.log`.
- **Config** — stored in `~/.config/ai-usage-tray/config.json` (mode `0600`).
- **Cache** — stored in `~/.cache/ai-usage-tray/usage-cache.json`.

## Development

```bash
git clone https://github.com/anomalyco/tray-app.git
cd tray-app
pip install -e .
ai-usage-tray
```

## Build

```bash
scripts/build-deb.sh <version>
```

Example: `scripts/build-deb.sh 0.2.0` produces `ai-usage-tray_0.2.0_all.deb`.

## License

[Unlicense](LICENSE) — public domain.
